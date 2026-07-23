"""
duplicate_checker.py
Detects duplicate Labs/Bundles before knowledge generation runs.

Checks, in order:
1. Exact name match (normalized).
2. Alias match (against alias_names already stored).
3. Fuzzy match (trigram similarity via pg_trgm, falls back to difflib
   if pg_trgm isn't installed).

Requires the `pg_trgm` extension on the MAIN database for best results:
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
"""

import difflib
import logging

from sqlalchemy import text

from .schemas import DuplicateCheckResult, EntityType
from .utils import main_session, normalize_text

logger = logging.getLogger(__name__)

FUZZY_MATCH_THRESHOLD = 0.80

TABLE_BY_TYPE = {
    EntityType.LAB: "labs",
    EntityType.BUNDLE: "bundles",
}


def _exact_match(session, table: str, normalized_name: str):
    row = session.execute(
        text(f"SELECT id, name FROM {table} WHERE lower(regexp_replace(name, '[^a-zA-Z0-9]+', ' ', 'g')) = :n"),
        {"n": normalized_name},
    ).fetchone()
    return row


def _alias_match(session, table: str, normalized_name: str):
    # alias_names assumed to be a Postgres text[] or jsonb array column
    row = session.execute(
        text(f"""
            SELECT id, name FROM {table}
            WHERE EXISTS (
                SELECT 1 FROM unnest(alias_names) AS alias
                WHERE lower(regexp_replace(alias, '[^a-zA-Z0-9]+', ' ', 'g')) = :n
            )
        """),
        {"n": normalized_name},
    ).fetchone()
    return row


def _fuzzy_match_pg_trgm(session, table: str, name: str):
    try:
        row = session.execute(
            text(f"""
                SELECT id, name, similarity(name, :name) AS score
                FROM {table}
                ORDER BY score DESC
                LIMIT 1
            """),
            {"name": name},
        ).fetchone()
        return row
    except Exception as e:
        logger.warning("pg_trgm fuzzy match unavailable (%s), falling back to difflib", e)
        return None


def _fuzzy_match_python(session, table: str, name: str):
    rows = session.execute(text(f"SELECT id, name FROM {table}")).fetchall()
    best_row, best_score = None, 0.0
    for row in rows:
        score = difflib.SequenceMatcher(None, name.lower(), row.name.lower()).ratio()
        if score > best_score:
            best_row, best_score = row, score
    return (best_row.id, best_row.name, best_score) if best_row else None


def check_duplicate(name: str, entity_type: EntityType) -> DuplicateCheckResult:
    """Main entry point. Returns a DuplicateCheckResult."""
    table = TABLE_BY_TYPE[entity_type]
    normalized_name = normalize_text(name)

    with main_session() as session:
        # 1. Exact match
        row = _exact_match(session, table, normalized_name)
        if row:
            return DuplicateCheckResult(is_duplicate=True, matched_id=row.id, matched_name=row.name, score=1.0)

        # 2. Alias match
        row = _alias_match(session, table, normalized_name)
        if row:
            return DuplicateCheckResult(is_duplicate=True, matched_id=row.id, matched_name=row.name, score=0.99)

        # 3. Fuzzy match
        fuzzy = _fuzzy_match_pg_trgm(session, table, name)
        if fuzzy is None:
            fuzzy = _fuzzy_match_python(session, table, name)

        if fuzzy:
            matched_id, matched_name, score = fuzzy
            if score >= FUZZY_MATCH_THRESHOLD:
                return DuplicateCheckResult(
                    is_duplicate=True, matched_id=matched_id, matched_name=matched_name, score=round(score, 2)
                )

    return DuplicateCheckResult(is_duplicate=False)