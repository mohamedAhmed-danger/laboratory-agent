

import sys
import os
import time
import argparse
import pandas as pd

# Ensure project root is on the path
project_dir = os.path.abspath(os.path.dirname(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from dotenv import load_dotenv
load_dotenv()

from app import app, db
from models.models import Laboratory, LabService, BundleService
from sqlalchemy import text
from knowledge.schemas import KnowledgeGenerationRequest, EntityType, VectorMetadata
from knowledge.generator import generate_knowledge
from knowledge.embedding import generate_embedding
from knowledge.vector_store import upsert_vector, ensure_vector_table

DEFAULT_EXCEL_NAME = "Price_List_with_Preparation (1).xlsx"


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def clean_value(val):
    if pd.isna(val) or val is None:
        return ""
    val_str = str(val).strip()
    return "" if val_str.lower() in ["nan", "none", "n/a", "null"] else val_str


def clean_price(val):
    try:
        if pd.isna(val) or val is None:
            return 0.0
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def get_field(obj, *names, default=None):
    """Try several possible attribute names on the generated-knowledge object,
    so this script keeps working even if knowledge/schemas.py uses
    `alias_names` instead of `aliases`, etc."""
    for n in names:
        if hasattr(obj, n):
            val = getattr(obj, n)
            if val:
                return val
    return default


def as_csv(val):
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val) if val is not None else ""


def generate_knowledge_with_backoff(req, max_attempts=5):
    for attempt in range(1, max_attempts + 1):
        try:
            gen = generate_knowledge(req)
            desc = get_field(gen, "description", default="")
            if gen and desc and "للمساعدة في التشخيص الطبي وتقييم الوظائف الحيوية" not in desc:
                return gen
        except Exception as e:
            wait = attempt * 2
            print(f"   ⚠️ API rate limit/error (attempt {attempt}/{max_attempts}): {e}. Retrying in {wait}s...", flush=True)
            time.sleep(wait)

    # last-ditch attempt, accept whatever comes back (even fallback text)
    try:
        return generate_knowledge(req)
    except Exception as e:
        print(f"   ❌ Failed to generate knowledge after {max_attempts} attempts: {e}", flush=True)
        return None


# ══════════════════════════════════════════════════════════════════════════
# DB reset
# ══════════════════════════════════════════════════════════════════════════

def reset_database_and_sequences():
    with app.app_context():
        print("--- RESETTING LABSERVICES & KNOWLEDGE VECTORS TABLES ---", flush=True)
        db.create_all()
        try:
            db.session.execute(text("ALTER TABLE labservices ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT now();"))
            db.session.execute(text("ALTER TABLE labservices ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now();"))
            db.session.execute(text("ALTER TABLE bundles ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT now();"))
            db.session.execute(text("ALTER TABLE bundles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now();"))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Notice on column migration: {e}", flush=True)

        try:
            db.session.execute(text("TRUNCATE TABLE bundle_services CASCADE;"))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Notice on bundle_services truncate: {e}", flush=True)

        try:
            db.session.execute(text("TRUNCATE TABLE labservices RESTART IDENTITY CASCADE;"))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Notice on labservices truncate: {e}", flush=True)

        try:
            ensure_vector_table()
            from knowledge.utils import vector_session
            with vector_session() as session:
                session.execute(text("TRUNCATE TABLE knowledge_vectors;"))
                session.commit()
            print("Successfully truncated knowledge_vectors table.", flush=True)
        except Exception as e:
            print(f"Notice on vector table truncate: {e}", flush=True)

        print("Database tables and primary key sequences reset to 1.", flush=True)


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Rebuild LabService knowledge from an Excel price list.")
    parser.add_argument("excel_path", nargs="?", default=None, help="Path to the price-list .xlsx file")
    parser.add_argument("--resume", action="store_true",
                         help="Skip the destructive reset step and skip tests already present in the DB")
    parser.add_argument("--sheet", default=0, help="Sheet name or index to read (default: first sheet)")
    args = parser.parse_args()

    excel_path = args.excel_path or os.path.join(project_dir, DEFAULT_EXCEL_NAME)

    print("=== STARTING KNOWLEDGE REBUILD ===", flush=True)
    if not os.path.exists(excel_path):
        print(f"Error: File '{excel_path}' not found!", flush=True)
        print("Pass the correct path as an argument, e.g.:", flush=True)
        print(f'  python {os.path.basename(__file__)} "Price_List_with_Preparation (1).xlsx"', flush=True)
        return

    if args.resume:
        print("--resume passed: skipping destructive reset.", flush=True)
    else:
        reset_database_and_sequences()

    with app.app_context():
        lab_org = Laboratory.query.first()
        if not lab_org:
            lab_org = Laboratory(id=1, name="معامل مختبر الاسكندرية", address="الاسكندرية", info="معمل تحاليل")
            db.session.add(lab_org)
            db.session.commit()
        lab_org_id = lab_org.id

        existing_names = set()
        if args.resume:
            existing_names = {n for (n,) in db.session.query(LabService.name).all()}
            print(f"Found {len(existing_names)} tests already in DB — these will be skipped.", flush=True)

    df = pd.read_excel(excel_path, sheet_name=args.sheet)

    # Extract unique tests, preserving order
    unique_rows = []
    seen = set()
    for _, row in df.iterrows():
        name = clean_value(row.get("Test"))
        if name and name not in seen:
            seen.add(name)
            unique_rows.append(row)

    total_tests = len(unique_rows)
    print(f"Loaded {total_tests} unique lab tests from Excel.", flush=True)

    success_count = 0
    error_count = 0
    skipped_count = 0

    for idx, row in enumerate(unique_rows, 1):
        test_name = clean_value(row.get("Test"))

        if args.resume and test_name in existing_names:
            skipped_count += 1
            print(f"[{idx}/{total_tests}] [SKIP] '{test_name}' already exists.", flush=True)
            continue

        specimen = clean_value(row.get("Sample"))
        price = clean_price(row.get("Price"))
        prep_en = clean_value(row.get("Preparation (English)"))
        prep_ar = clean_value(row.get("التحضير المطلوب (عربي)"))

        instructions_parts = []
        if prep_ar:
            instructions_parts.append(prep_ar)
        if prep_en:
            instructions_parts.append(f"({prep_en})")
        patient_instructions = "\n".join(instructions_parts) if instructions_parts else "لا يوجد تحضير خاص."

        req = KnowledgeGenerationRequest(
            name=test_name,
            patient_instructions=patient_instructions,
            duration="24-48 ساعة",
            price=price,
            entity_type=EntityType.LAB,
        )

        print(f"[{idx}/{total_tests}] Generating knowledge for: '{test_name}'...", flush=True)
        gen = generate_knowledge_with_backoff(req)

        if not gen:
            error_count += 1
            print(f"[{idx}/{total_tests}] [ERROR] Skipping '{test_name}' due to repeated LLM error.", flush=True)
            continue

        description = get_field(gen, "description", default=test_name)
        aliases = get_field(gen, "aliases", "alias_names", default=[test_name])
        keywords = get_field(gen, "keywords", default=[test_name])
        search_text = get_field(gen, "search_text", default=test_name)

        with app.app_context():
            lab_entity = LabService(
                laboratory_id=lab_org_id,
                name=test_name,
                price=price,
                specimen=specimen or None,
                durations="24-48 ساعة",
                patient_instructions=patient_instructions,
                description=description,
                alias_names=as_csv(aliases),
                keywords=as_csv(keywords),
                search_text=search_text,
            )
            db.session.add(lab_entity)
            db.session.commit()
            assigned_id = lab_entity.id

            try:
                embedding = generate_embedding(test_name, gen)
                metadata = VectorMetadata(id=assigned_id, type=EntityType.LAB, name=test_name)
                upsert_vector(metadata, embedding)
            except Exception as vec_err:
                print(f"   ⚠️ Vector upsert failed for '{test_name}': {vec_err}", flush=True)

        success_count += 1
        print(f"[{idx}/{total_tests}] [SUCCESS ID={assigned_id}] '{test_name}' -> {str(description)[:65]}...", flush=True)

        time.sleep(0.8)  # basic rate-limit pacing

    print("\n==========================================", flush=True)
    print("=== REBUILD COMPLETE ===", flush=True)
    print(f" Total Tests:            {total_tests}", flush=True)
    print(f" Successfully Processed: {success_count}", flush=True)
    print(f" Skipped (resume):       {skipped_count}", flush=True)
    print(f" Errors:                 {error_count}", flush=True)
    print("==========================================", flush=True)


if __name__ == "__main__":
    main()