"""
updater.py
Saves approved knowledge into PostgreSQL (main app DB).
Runs only AFTER administrator approval — never before.
"""

import json
import logging

from sqlalchemy import text

from .schemas import ApprovedKnowledge, EntityType
from .utils import main_session

logger = logging.getLogger(__name__)

TABLE_BY_TYPE = {
    EntityType.LAB: "labservices",
    EntityType.BUNDLE: "bundles",
}


def update_knowledge(approved: ApprovedKnowledge) -> None:
    """
    Updates the Lab/Bundle row with description, keywords, alias_names,
    and search_text. Assumes keywords/alias_names are Postgres text[]
    columns; adjust the cast if yours are jsonb instead.
    """
    table = TABLE_BY_TYPE[approved.entity_type]

    with main_session() as session:
        session.execute(
            text(f"""
                UPDATE {table}
                SET description = :description,
                    keywords = :keywords,
                    alias_names = :aliases,
                    search_text = :search_text,
                    updated_at = now()
                WHERE id = :id
            """),
            {
                "description": approved.description,
                "keywords": approved.keywords,
                "aliases": approved.aliases,
                "search_text": approved.search_text,
                "id": approved.entity_id,
            },
        )
    logger.info("Updated %s id=%s with approved knowledge.", table, approved.entity_id)


def update_knowledge_jsonb(approved: ApprovedKnowledge) -> None:
    """
    Variant for schemas where keywords/alias_names are stored as jsonb
    instead of text[]. Use this instead of update_knowledge() if that's
    your column type.
    """
    table = TABLE_BY_TYPE[approved.entity_type]

    with main_session() as session:
        session.execute(
            text(f"""
                UPDATE {table}
                SET description = :description,
                    keywords = CAST(:keywords AS jsonb),
                    alias_names = CAST(:aliases AS jsonb),
                    search_text = :search_text,
                    updated_at = now()
                WHERE id = :id
            """),
            {
                "description": approved.description,
                "keywords": json.dumps(approved.keywords),
                "aliases": json.dumps(approved.aliases),
                "search_text": approved.search_text,
                "id": approved.entity_id,
            },
        )
    logger.info("Updated %s id=%s (jsonb) with approved knowledge.", table, approved.entity_id)