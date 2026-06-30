"""
ocr/extractor.py
"""

import os
import json
from google import genai
from llama_parse import LlamaParse
from software_services.service_services import ServiceService

def extract_prescription_data(image_path: str) -> dict:
    """
    Extracts text from a prescription image and matches services against the database.
    
    Returns:
        dict: {
            "extracted_text": str,
            "services_mentioned": list of str
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
        
    # 2. Extract text using LlamaParse or fallback to Gemini Multimodal OCR
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
            # load_data returns a list of Document objects
            documents = parser.load_data(image_path)
            if documents:
                extracted_text = "\n".join([doc.text for doc in documents])
        except Exception as e:
            print(f"[Extractor] LlamaParse failed: {e}. Falling back to Gemini OCR...")
            
    # Fallback to Gemini Multimodal OCR if LlamaParse is not configured or fails
    if not extracted_text:
        print("[Extractor] Using Gemini Multimodal for OCR...")
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return {
                "extracted_text": "",
                "services_mentioned": []
            }
            
        try:
            from PIL import Image
            img = Image.open(image_path)
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    "Perform full text OCR on this image. Extract all handwritten and printed text in Arabic and English exactly as written.",
                    img
                ]
            )
            extracted_text = response.text.strip()
        except Exception as e:
            print(f"[Extractor] Gemini OCR failed: {e}")
            return {
                "extracted_text": "",
                "services_mentioned": []
            }
            
    # 3. Match extracted tests against the laboratory's available services list
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key or not extracted_text:
        return {
            "extracted_text": extracted_text,
            "services_mentioned": []
        }
        
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are a medical laboratory assistant. 
        Analyze the extracted text from a prescription below and identify if any of the available lab services are requested.
        
        Available Services in our Laboratory:
        {json.dumps(available_services, ensure_ascii=False)}
        
        Extracted Prescription Text:
        ---
        {extracted_text}
        ---
        
        Return a JSON object containing:
        - services_mentioned: A list of service names from the "Available Services" list that are mentioned in the text. Do not return any other names. Only return exact matches from the list.
        
        Return ONLY valid JSON. Do not wrap the JSON in markdown code formatting (like ```json).
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt]
        )
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        data = json.loads(text)
        return {
            "extracted_text": extracted_text,
            "services_mentioned": data.get("services_mentioned", [])
        }
    except Exception as e:
        print(f"[Extractor] Service matching failed: {e}")
        return {
            "extracted_text": extracted_text,
            "services_mentioned": []
        }
