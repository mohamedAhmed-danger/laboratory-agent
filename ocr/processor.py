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
    2. If the document is classified as a prescription with confidence >= 70%:
       - Extracts full text and detects mentioned laboratory services.
       - Saves the inquiry into the database.
       - Returns a success status and metadata.
    3. If confidence is low or classified as spam, rejects the document.
    
    Returns:
        dict: Process result dictionary.
    """
    # 1. Classify image
    classification_result = classify_prescription(image_path)
    is_prescription = classification_result.get("classification") == "prescription"
    confidence = classification_result.get("confidence", 0.0)
    reason = classification_result.get("reason", "")
    
    if is_prescription and confidence >= 0.70:
        # 2. Extract prescription data
        extraction_result = extract_prescription_data(image_path)
        extracted_text = extraction_result.get("extracted_text", "")
        services_mentioned = extraction_result.get("services_mentioned", [])
        
        # Format services as comma-separated string for DB storage
        services_str = ", ".join(services_mentioned) if services_mentioned else None
        
        # 3. Save Inquiry to the database
        filename = os.path.basename(image_path)
        
        db_result = InquiryService.save_inquiry(
            laboratory_id=laboratory_id,
            phone_number=phone_number,
            comes_from=comes_from,
            prescription_img=filename,
            ocr_extracted_text=extracted_text,
            confidence_score=confidence,
            services_mentioned=services_str
        )
        
        return {
            "success": True,
            "classified_as": "prescription",
            "confidence": confidence,
            "reason": reason,
            "extracted_text": extracted_text,
            "services_mentioned": services_mentioned,
            "inquiry_id": db_result.inquiry.id if db_result.success and db_result.inquiry else None,
            "message": "Prescription processed and saved successfully."
        }
    else:
        return {
            "success": False,
            "classified_as": classification_result.get("classification", "spam"),
            "confidence": confidence,
            "reason": reason,
            "extracted_text": "",
            "services_mentioned": [],
            "inquiry_id": None,
            "message": f"Document rejected. Classified as {classification_result.get('classification')} with {int(confidence*100)}% confidence."
        }
