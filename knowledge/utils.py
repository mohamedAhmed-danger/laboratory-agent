"""
utils.py
Shared helper functions for the Knowledge Pipeline.

Holds:
- Two separate SQLAlchemy engines (main app DB vs. pgvector DB),
  as requested: they may be the same physical Postgres server or
  two different servers, but they are ALWAYS opened as two
  independent engines/connections.
- Text normalization helpers used by the duplicate checker.
- A small Gemini client helper.
"""

import os
import re
import unicodedata
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Database engines
# ---------------------------------------------------------------------------
# MAIN_DATABASE_URL -> normal Postgres DB (labs, bundles, etc.)
# VECTOR_DATABASE_URL -> Postgres + pgvector extension.
# These can point to the same physical server or different ones, but the
# pipeline ALWAYS treats them as two separate engines/connections, never
# a shared session, so the vector store logic stays decoupled from the
# main app DB.

MAIN_DATABASE_URL = os.environ["MAIN_DATABASE_URL"]
VECTOR_DATABASE_URL = os.environ["VECTOR_DATABASE_URL"]

main_engine = create_engine(MAIN_DATABASE_URL, pool_pre_ping=True, future=True)
vector_engine = create_engine(VECTOR_DATABASE_URL, pool_pre_ping=True, future=True)

MainSession = sessionmaker(bind=main_engine, future=True)
VectorSession = sessionmaker(bind=vector_engine, future=True)


@contextmanager
def main_session():
    """Yields a session bound to the main app database."""
    session = MainSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def vector_session():
    """Yields a session bound to the pgvector database."""
    session = VectorSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Text normalization (used by duplicate_checker.py)
# ---------------------------------------------------------------------------
def normalize_text(text: str) -> str:
    """
    Lowercases, strips accents/punctuation, and collapses whitespace.
    e.g. "  CBC - Complete Blood Count! " -> "cbc complete blood count"
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Gemini client helper
# ---------------------------------------------------------------------------
def get_gemini_client():
    """
    Returns a configured google-generativeai module ready to call.
    Requires GEMINI_API_KEY in the environment.
    """
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai