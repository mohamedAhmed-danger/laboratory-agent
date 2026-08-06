from collections import defaultdict

from sqlalchemy import bindparam, text

from knowledge.schemas import EntityType
from knowledge.utils import main_session
from search.schemas import SearchResult


TABLE_BY_TYPE = {
    EntityType.LAB: "labservices",
    EntityType.BUNDLE: "bundles",
}


def _fetch_rows(results: list[SearchResult]) -> dict:

    grouped = defaultdict(list)

    for result in results:
        grouped[result.type].append(result.id)

    rows = {}

    with main_session() as session:

        for entity_type, ids in grouped.items():

            table = TABLE_BY_TYPE[entity_type]

            if entity_type == EntityType.LAB:
                query = text(f"""
                    SELECT
                        id,
                        name,
                        description,
                        price,
                        specimen,
                        durations,
                        patient_instructions
                    FROM {table}
                    WHERE id IN :ids
                """).bindparams(bindparam("ids", expanding=True))

            else:
                query = text(f"""
                    SELECT
                        id,
                        name,
                        description,
                        price,
                        patient_instructions
                    FROM {table}
                    WHERE id IN :ids
                """).bindparams(bindparam("ids", expanding=True))

            result_rows = session.execute(
                query,
                {"ids": ids},
            ).mappings()

            for row in result_rows:
                rows[(entity_type, row["id"])] = dict(row)

    return rows


def build_context(results: list[SearchResult]) -> str:

    rows = _fetch_rows(results)

    sections = []

    for result in results:

        row = rows.get((result.type, result.id))

        if row is None:
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

    return "\n\n" + ("\n\n").join(sections)