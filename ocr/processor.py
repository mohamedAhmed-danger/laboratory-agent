"""
ocr/processor.py

Orchestrates the OCR pipeline using a SINGLE Gemini multimodal call.

Old flow  (2 API calls):
    classify_prescription()  →  extract_prescription_data()

New flow  (1 API call):
    analyze_prescription()  →  route based on process_success flag

Routing:
    process_success = True  (overall_confidence >= 70)
        → save Inquiry as REVIEWED
        → return success=True  → LangGraph agent replies automatically

    process_success = False (overall_confidence < 70)  AND  is_prescription = True
        → save Inquiry as PENDING for manual doctor review
        → return success=False → static "waiting for doctor" reply

    is_spam = True
        → do NOT save Inquiry
        → return success=False, classified_as="spam"
"""

import os
import logging
from ocr.classifier import analyze_prescription
from software_services.inquiry_services import InquiryService

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 70          # must match ocr/classifier.py


def process_prescription_ocr(
    image_path: str,
    phone_number: str,
    comes_from: str,
    laboratory_id: int = 1,
) -> dict:
    """
    Main entry-point called by service/message_processor.py.

    Args:
        image_path:     Absolute path to the downloaded prescription image.
        phone_number:   Sender's phone number (may be empty for FB users).
        comes_from:     Origin string, e.g. "Facebook:<sender_id>:<page_id>".
        laboratory_id:  ID of the laboratory record (default: 1).

    Returns:
        dict with keys:
            success         bool
            classified_as   "prescription" | "spam"
            confidence      int   (0-100)
            extracted_text  str
            services_mentioned list[str]
            inquiry_id      int | None
            message         str
    """
    # ── Single Gemini call ────────────────────────────────────────────────────
    ocr = analyze_prescription(image_path)

    is_prescription    = ocr.get("is_prescription", False)
    is_spam            = ocr.get("is_spam", True)
    overall_confidence = ocr.get("overall_confidence", 0)
    process_success    = ocr.get("process_success", False)
    labs               = ocr.get("labs", [])
    unknown_items      = ocr.get("unknown_items", [])
    notes              = ocr.get("notes", "")

    logger.info(
        "[OCR Processor] is_prescription=%s | confidence=%s | process_success=%s",
        is_prescription, overall_confidence, process_success,
    )

    # ── Spam / non-prescription ───────────────────────────────────────────────
    if not is_prescription:
        return {
            "success":            False,
            "classified_as":      "spam",
            "confidence":         overall_confidence,
            "extracted_text":     "",
            "services_mentioned": [],
            "inquiry_id":         None,
            "message":            f"Document rejected — not a prescription. {notes}",
        }

    # ── Build extracted text from labs ───────────────────────────────────────
    lab_lines = []
    for lab in labs:
        line = lab.get("standardized_name") or lab.get("matched_text", "")
        if line:
            lab_lines.append(line)

    if unknown_items:
        lab_lines.append("Unreadable items: " + ", ".join(unknown_items))

    extracted_text  = "\n".join(lab_lines)
    services_str    = ", ".join(
        lab.get("standardized_name") or lab.get("matched_text", "")
        for lab in labs
        if lab.get("standardized_name") or lab.get("matched_text")
    ) or None
    filename = os.path.basename(image_path)

    # ── High confidence → automated flow ─────────────────────────────────────
    if process_success:
        from models.models import Status
        db_result = InquiryService.save_inquiry(
            laboratory_id=laboratory_id,
            phone_number=phone_number,
            comes_from=comes_from,
            prescription_img=filename,
            ocr_extracted_text=extracted_text,
            confidence_score=overall_confidence / 100.0,
            services_mentioned=services_str,
            status=Status.REVIEWED,
        )
        return {
            "success":            True,
            "classified_as":      "prescription",
            "confidence":         overall_confidence,
            "extracted_text":     extracted_text,
            "services_mentioned": [
                lab.get("standardized_name") or lab.get("matched_text", "")
                for lab in labs
            ],
            "inquiry_id": (
                db_result.inquiry.id
                if db_result.success and db_result.inquiry
                else None
            ),
            "message": (
                f"Prescription parsed successfully "
                f"(confidence={overall_confidence}%)."
            ),
        }

    # ── Low confidence → manual doctor review ────────────────────────────────
    db_result = InquiryService.save_inquiry(
        laboratory_id=laboratory_id,
        phone_number=phone_number,
        comes_from=comes_from,
        prescription_img=filename,
        ocr_extracted_text=(
            "[Low Confidence — Waiting for Manual Review]\n" + extracted_text
        ),
        confidence_score=overall_confidence / 100.0,
        services_mentioned=None,
    )
    return {
        "success":            False,
        "classified_as":      "prescription",
        "confidence":         overall_confidence,
        "extracted_text":     "",
        "services_mentioned": [],
        "inquiry_id": (
            db_result.inquiry.id
            if db_result.success and db_result.inquiry
            else None
        ),
        "message": (
            f"Prescription saved for manual review "
            f"(confidence={overall_confidence}% < threshold {CONFIDENCE_THRESHOLD}%)."
        ),
    }
