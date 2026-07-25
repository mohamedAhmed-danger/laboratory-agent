"""
utils.py
Shared helper functions for the Knowledge Pipeline.
"""

import os
import re
import unicodedata
import warnings
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Database engines
# ---------------------------------------------------------------------------
MAIN_DATABASE_URL = os.environ.get("MAIN_DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI") or "postgresql://postgres:Mo162534@localhost:5432/laboratory_db"
VECTOR_DATABASE_URL = os.environ.get("VECTOR_DATABASE_URL") or MAIN_DATABASE_URL

if MAIN_DATABASE_URL.startswith("postgresql://"):
    MAIN_DATABASE_URL = MAIN_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
if VECTOR_DATABASE_URL.startswith("postgresql://"):
    VECTOR_DATABASE_URL = VECTOR_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

main_engine = create_engine(MAIN_DATABASE_URL, pool_pre_ping=True, future=True)
vector_engine = create_engine(VECTOR_DATABASE_URL, pool_pre_ping=True, future=True)

MainSession = sessionmaker(bind=main_engine, future=True)
VectorSession = sessionmaker(bind=vector_engine, future=True)


@contextmanager
def main_session():
    """Yields a session bound to the main app database."""
    try:
        from flask import current_app
        if current_app:
            from models.models import db
            yield db.session
            return
    except Exception:
        pass

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
    """Lowercases, strips accents/punctuation, and collapses whitespace."""
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
    Returns a configured google.genai Client or legacy genai module.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    try:
        from google import genai
        if api_key:
            return genai.Client(api_key=api_key)
        return genai.Client()
    except Exception:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            return genai