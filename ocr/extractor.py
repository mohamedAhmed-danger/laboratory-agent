"""
ocr/extractor.py
"""

import os
import json
from google import genai
from PIL import Image
from llama_parse import LlamaParse
from software_services.service_services import ServiceService

def extract_prescription_data(image_path: str) -> dict:
    """
    Extracts text from a prescription image and matches services against the database.
    Also returns an extraction confidence score indicating how clear and readable the text/image is.
    
    Returns:
        dict: {
            "extracted_text": str,
            "services_mentioned": list of str,
            "confidence_score": float
        }
    """
    # 1. Fetch available services from the database to perform entity matching
    available_services = []
    try:
        pagination, _ = ServiceService.get_all_services(page=1, per_page=1000)
        if pagination and pagination.items:
            available_services = [s.name for s in pagination.items]
    except Exception as e:
        print(f"[Extractor] Error fetching services from DB: {e}")
        
    # 2. Extract text using LlamaParse (if available)
    extracted_text = ""
    llama_key = os.environ.get("LLAMA_CLOUD_API_KEY")
    
    if llama_key:
        try:
            print("[Extractor] Using LlamaParse for OCR...")
            parser = LlamaParse(
                api_key=llama_key,
                result_type="markdown",
                language="ar"
            )
            documents = parser.load_data(image_path)
            if documents:
                extracted_text = "\n".join([doc.text for doc in documents])
        except Exception as e:
            print(f"[Extractor] LlamaParse failed: {e}. Falling back to Gemini OCR...")
            
    # Open the image using PIL
    try:
        img = Image.open(image_path)
    except Exception as e:
        print(f"[Extractor] Failed to open image: {e}")
        return {
            "extracted_text": "",
            "services_mentioned": [],
            "confidence_score": 0.0
        }

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[Extractor] Gemini API key not configured.")
        return {
            "extracted_text": extracted_text,
            "services_mentioned": [],
            "confidence_score": 0.5 if extracted_text else 0.0
        }

    client = genai.Client(api_key=api_key)

    # 3. Use Gemini Multimodal to perform OCR if LlamaParse is not used, or to match services and evaluate extraction confidence
    try:
        if not extracted_text:
            print("[Extractor] Using Gemini Multimodal for full OCR extraction...")
            # Ask Gemini to do full OCR and match services in one step
            prompt = f"""
            Perform full text OCR on this image. Extract all handwritten and printed text in Arabic and English exactly as written.
            Then, identify if any of the available laboratory services are requested.
            Also, evaluate the quality/readability of the prescription image and output an extraction confidence score between 0.0 and 1.0 indicating how certain you are of the text and service names.
            
            Available Services in our Laboratory:
            {json.dumps(available_services, ensure_ascii=False)}
            
            Return a JSON object containing the following keys:
            - extracted_text: string (the full raw text transcription)
            - services_mentioned: list of strings (exact matches from the "Available Services" list)
            - confidence_score: float (between 0.0 and 1.0 indicating your confidence in the OCR extraction quality and matched services)
            
            Return ONLY valid JSON. Do not wrap the JSON in markdown formatting.
            """
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, img]
            )
            text_res = response.text.strip()
        else:
            print("[Extractor] LlamaParse text obtained. Using Gemini to match services and evaluate confidence...")
            # We already have LlamaParse text, ask Gemini to match services and check confidence against the image
            prompt = f"""
            Analyze the provided prescription image and the pre-extracted text below.
            Identify if any of the available laboratory services are requested.
            Evaluate the quality of the pre-extracted text against the image, and output an extraction confidence score between 0.0 and 1.0 indicating how certain you are of the OCR extraction quality and the matched services.
            
            Available Services in our Laboratory:
            {json.dumps(available_services, ensure_ascii=False)}
            
            Pre-extracted Prescription Text:
            ---
            {extracted_text}
            ---
            
            Return a JSON object containing the following keys:
            - services_mentioned: list of strings (exact matches from the "Available Services" list)
            - confidence_score: float (between 0.0 and 1.0 indicating your confidence in the OCR extraction quality and matched services)
            
            Return ONLY valid JSON. Do not wrap the JSON in markdown formatting.
            """
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, img]
            )
            text_res = response.text.strip()

        # Clean JSON formatting code fences
        if text_res.startswith("```json"):
            text_res = text_res[7:]
        if text_res.startswith("```"):
            text_res = text_res[3:]
        if text_res.endswith("```"):
            text_res = text_res[:-3]
        text_res = text_res.strip()
        
        data = json.loads(text_res)
        
        # If we had LlamaParse text, keep it as the extracted_text, otherwise use Gemini's OCR
        final_extracted_text = extracted_text if extracted_text else data.get("extracted_text", "")
        
        return {
            "extracted_text": final_extracted_text,
            "services_mentioned": data.get("services_mentioned", []),
            "confidence_score": float(data.get("confidence_score", 0.5))
        }

    except Exception as e:
        print(f"[Extractor] Gemini call failed: {e}")
        return {
            "extracted_text": extracted_text,
            "services_mentioned": [],
            "confidence_score": 0.5 if extracted_text else 0.0
        }
