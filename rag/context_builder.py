from sqlalchemy import text

from knowledge.schemas import EntityType
from knowledge.utils import main_session
from search.schemas import SearchResult


TABLE_BY_TYPE = {
    EntityType.LAB: "labservices",
    EntityType.BUNDLE: "bundles",
}


def _fetch_row(result: SearchResult):

    table = TABLE_BY_TYPE[result.type]

    if result.type == EntityType.LAB:
        query = f"""
        SELECT
            name,
            description,
            price,
            specimen,
            durations,
            patient_instructions
        FROM {table}
        WHERE id=:id
        """
    else:
        query = f"""
        SELECT
            name,
            description,
            price,
            patient_instructions
        FROM {table}
        WHERE id=:id
        """

    with main_session() as session:
        row = session.execute(
            text(query),
            {"id": result.id}
        ).fetchone()

    if row is None:
        return None

    return dict(row._mapping)


def build_context(results: list[SearchResult]) -> str:

    sections = []

    for result in results:

        row = _fetch_row(result)

        if not row:
            continue

        block = []

        block.append(f"Name: {row['name']}")

        if row.get("description"):
            block.append(f"Description: {row['description']}")

        if row.get("price") is not None:
            block.append(f"Price: {row['price']}")

        if row.get("specimen"):
            block.append(f"Specimen: {row['specimen']}")

        if row.get("durations"):
            block.append(f"Duration: {row['durations']}")

        if row.get("patient_instructions"):
            block.append(
                f"Patient Instructions: {row['patient_instructions']}"
            )

        sections.append("\n".join(block))

    return "\n\n------------------------\n\n".join(sections)