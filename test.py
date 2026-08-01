# -*- coding: utf-8 -*-
"""
test_cases.py — runs the full manual QA test matrix (all 27 scenarios) against
run_agent as ONE continuous conversation, since several scenarios depend on
earlier context (booking flow -> after-booking -> re-book, context switching,
follow-up questions relying on client.summary, etc).

It prints each turn to the console AND saves a full transcript to a timestamped
.md file in the current directory, since the full run is long.

Usage:
    python test_cases.py             # run everything, fresh client state
    python test_cases.py --keep      # don't wipe previous test client state first
"""

import sys
import argparse
import traceback
from datetime import datetime

from app import app, db
from service.message_processor import IncomingMessage, run_agent
from models.models import Page, Client

TEST_SENDER_ID = "qa_test_runner"
TEST_PLATFORM_NAME = "test"

# ── The full scenario matrix, in execution order ────────────────────────────
# Each item: (section title, notes-or-None, [messages...])
# A "message" can contain \n for a single multi-line message (e.g. one-shot booking).
SCENARIOS = [
    ("1) Direct Conversation", None, [
        "السلام عليكم", "صباح الخير", "مساء الخير", "عاملين ايه",
        "شكرا", "تسلم", "تمام", "باي", "مع السلامة",
    ]),
    ("2) Inquiry (Single Lab)", None, [
        "عايز اعرف سعر CBC", "CBC", "صورة دم", "صوره الدم",
        "complete blood count", "cbc test",
        "عايز اعرف التحضير بتاع CBC", "العينة المطلوبة ل CBC", "النتيجة بتطلع امتى",
    ]),
    ("3) Inquiry (Typos)", None, [
        "cbb", "cbp", "cbccc", "fertin", "ferrtin",
        "vit d", "vitamin d", "thyriod", "tshh",
    ]),
    ("4) Arabic Misspellings", None, [
        "فيرتين", "فيريتين", "فيتامين د", "فيتامن د",
        "الغدة", "صوره دم", "صورة الدم", "سكر",
    ]),
    ("5) Multi Lab", None, [
        "عايز اعرف سعر CBC و Ferritin", "CBC + Vitamin D", "CBC و TSH",
        "سكر وتراكمي", "Ferritin و Iron profile",
    ]),
    ("6) Mixed Arabic + English", None, [
        "عايز CBC", "احجز ferritin", "عايز Vitamin D", "احجز tsh",
    ]),
    ("7) Booking Flow", None, [
        "عايز احجز CBC", "محمد احمد", "01234567890", "بكرة الساعة 5", "تمام",
    ]),
    ("8) Booking in one message", None, [
        "عايز احجز CBC\nاسمي محمد\n01234567890\nبكرة الساعة 5",
    ]),
    ("9) Booking with multiple labs", None, [
        "عايز احجز CBC و Ferritin",
    ]),
    ("10) Relative Dates", None, [
        "بكرة", "بعد بكرة", "السبت", "الأحد الجاي", "الاسبوع الجاي", "النهاردة",
    ]),
    ("11) Confirmation", None, [
        "ايوه", "تمام", "موافق", "اكيد", "لا", "مش موافق",
    ]),
    ("12) Complaint", None, [
        "الخدمة سيئة", "المعمل اتأخر", "النتيجة اتأخرت", "الاستقبال وحش",
    ]),
    ("13) Complaint continuation", None, [
        "الخدمة سيئة", "الاستقبال اتعامل معايا بطريقة وحشة",
    ]),
    ("14) Unknown Lab", None, [
        "تحليل سوبر مان", "abcxyz", "تحليل مش موجود",
    ]),
    ("15) Ambiguous", "Expected: bot should ask the user to clarify.", [
        "عايز تحليل دم", "عايز تحليل للسكر", "تحليل الغدة",
    ]),
    ("16) Follow-up Questions", "Expected: bot should use conversation summary for context.", [
        "عايز اعرف سعر CBC",  # priming question so the follow-ups have something to refer to
        "وسعره كام؟", "وبيطلع امتى؟", "طب والعينة؟",
    ]),
    ("17) Context Switching", "Expected: should end up completing the booking.", [
        "عايز احجز CBC", "بكام؟", "اسمي محمد", "012...",
    ]),
    ("18) Multiple intents", None, [
        "عايز اعرف سعر CBC ولو مناسب احجزه",
    ]),
    ("19) After Booking", "Expected: should NOT create a new booking.", [
        "تمام",
    ]),
    ("20) Re-book", "Expected: should start a NEW booking flow.", [
        "عايز احجز Ferritin",
    ]),
    ("21) Long Messages", None, [
        "السلام عليكم\nأنا عندي أنيميا والدكتور كتبلي CBC و Ferritin و Vitamin D "
        "وعايز أعرف الأسعار ولو مناسبة هحجز بكرة.",
    ]),
    ("22) OCR Text", "Expected: should start a booking, as if this came from OCR extraction.", [
        "CBC\nFerritin\nVitamin D\nTSH",
    ]),
    ("23) Stress Test", None, [
        "CBC CBC CBC CBC CBC", "؟؟؟؟؟؟", "........", "🙂🙂🙂", "هههههههههه",
    ]),
    ("24) Empty", None, [
        "",
    ]),
    ("25) Numbers only", None, [
        "12345", "555555",
    ]),
    ("26) Emoji only", None, [
        "❤️", "👍", "😂",
    ]),
    ("27) English only", None, [
        "Hi", "Book CBC", "Price of Ferritin", "Thank you",
    ]),
]


def reset_test_client(page):
    """Delete any prior test-runner client so each run starts with clean summary/state."""
    existing = Client.query.filter_by(
        sender_id=TEST_SENDER_ID, page_id=page.page_id, platform_id=page.platform_id
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        print(f"🧹 Cleared previous test client state (sender_id={TEST_SENDER_ID}).\n")


def run_all(keep_state: bool):
    with app.app_context():
        page = Page.query.first()
        if not page:
            print("⚠️  No Page found in DB. Run seed_test_data.py first.")
            sys.exit(1)

        if not keep_state:
            reset_test_client(page)

        transcript_lines = [
            f"# QA Test Run — {datetime.now().isoformat(timespec='seconds')}",
            f"page_id={page.page_id} platform_id={page.platform_id}",
            "",
        ]

        for title, note, messages in SCENARIOS:
            header = f"\n{'=' * 70}\n{title}\n{'=' * 70}"
            print(header)
            transcript_lines.append(f"\n## {title}")
            if note:
                print(f"📝 {note}")
                transcript_lines.append(f"> {note}")

            for text in messages:
                display_text = text if text.strip() else "(empty message)"
                print(f"\n👤 You: {display_text}")
                transcript_lines.append(f"\n**You:** {display_text}")

                msg = IncomingMessage(
                    sender_id=TEST_SENDER_ID,
                    page_id=page.page_id,
                    platform_id=page.platform_id,
                    msg_type="text",
                    text=text,
                    platform_name=TEST_PLATFORM_NAME,
                )
                try:
                    reply, ticket_bytes = run_agent(msg)
                except Exception:
                    reply = None
                    print("❌ EXCEPTION while processing this message:")
                    traceback.print_exc()
                    transcript_lines.append("**Bot:** ❌ EXCEPTION (see console/logs)")
                    continue

                print(f"🤖 Bot: {reply}")
                transcript_lines.append(f"**Bot:** {reply}")
                if ticket_bytes:
                    print("📎 (booking ticket PDF/image returned)")
                    transcript_lines.append("_(booking ticket returned)_")

        out_path = f"qa_test_transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(transcript_lines))
        print(f"\n\n✅ Full run complete. Transcript saved to: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Run the full QA test scenario matrix")
    parser.add_argument("--keep", action="store_true", help="Don't reset test client state before running")
    args = parser.parse_args()
    run_all(keep_state=args.keep)


if __name__ == "__main__":
    main()