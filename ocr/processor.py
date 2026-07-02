"""
ocr/processor.py
"""

import os
from ocr.classifier import classify_prescription
from ocr.extractor import extract_prescription_data
from software_services.inquiry_services import InquiryService

def process_prescription_ocr(image_path: str, phone_number: str, comes_from: str, laboratory_id: int = 1) -> dict:
    """
    Orchestrates the classification, extraction, and database persistence:
    
    1. Classifies the document.
    2. If the document is classified as a prescription:
       - Extracts full text, detects mentioned laboratory services, and calculates extraction confidence score.
       - If extraction confidence >= 70%:
         - Saves the inquiry into the database with PENDING status.
         - Returns a success status (success=True) to route to the LangGraph Agent.
       - If extraction confidence < 70%:
         - Saves the inquiry into the database with PENDING status for manual doctor review.
         - Returns success=False to route to the static reply.
    3. If classified as spam, rejects the document.
    
    Returns:
        dict: Process result dictionary.
    """
    # 1. Classify image
    classification_result = classify_prescription(image_path)
    is_prescription = classification_result.get("classification") == "prescription"
    reason = classification_result.get("reason", "")
    
    if is_prescription:
        # 2. Extract prescription data (this returns extraction text, matches, and extraction confidence!)
        extraction_result = extract_prescription_data(image_path)
        extracted_text = extraction_result.get("extracted_text", "")
        services_mentioned = extraction_result.get("services_mentioned", [])
        extraction_confidence = extraction_result.get("confidence_score", 0.0)
        
        # Format services as comma-separated string for DB storage
        services_str = ", ".join(services_mentioned) if services_mentioned else None
        filename = os.path.basename(image_path)
        
        if extraction_confidence >= 0.70:
            from models.models import Status
            # 3. Save Inquiry to the database (High Confidence) - status=REVIEWED as it is handled automatically
            db_result = InquiryService.save_inquiry(
                laboratory_id=laboratory_id,
                phone_number=phone_number,
                comes_from=comes_from,
                prescription_img=filename,
                ocr_extracted_text=extracted_text,
                confidence_score=extraction_confidence,
                services_mentioned=services_str,
                status=Status.REVIEWED
            )
            
            return {
                "success": True,
                "classified_as": "prescription",
                "confidence": extraction_confidence, # Represents extraction confidence
                "reason": reason,
                "extracted_text": extracted_text,
                "services_mentioned": services_mentioned,
                "inquiry_id": db_result.inquiry.id if db_result.success and db_result.inquiry else None,
                "message": "Prescription parsed successfully with high extraction confidence."
            }
        else:
            # 3. Save Inquiry to the database (Low Confidence - Waiting for manual review)
            db_result = InquiryService.save_inquiry(
                laboratory_id=laboratory_id,
                phone_number=phone_number,
                comes_from=comes_from,
                prescription_img=filename,
                ocr_extracted_text="[Low Confidence Extraction - Waiting for Manual Review]",
                confidence_score=extraction_confidence, # Represents extraction confidence
                services_mentioned=None
            )
            
            return {
                "success": False,
                "classified_as": "prescription",
                "confidence": extraction_confidence, # Represents extraction confidence
                "reason": reason,
                "extracted_text": "",
                "services_mentioned": [],
                "inquiry_id": db_result.inquiry.id if db_result.success and db_result.inquiry else None,
                "message": f"Prescription saved for manual review due to low extraction confidence ({int(extraction_confidence*100)}%)."
            }
    else:
        return {
            "success": False,
            "classified_as": "spam",
            "confidence": 0.0,
            "reason": reason,
            "extracted_text": "",
            "services_mentioned": [],
            "inquiry_id": None,
            "message": f"Document rejected. Classified as spam."
        }
