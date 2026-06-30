"""
ocr/classifier.py
"""

import os
import json
from google import genai
from PIL import Image

def classify_prescription(image_path: str) -> dict:
    """
    Classifies an image as a medical prescription or spam using the google-genai SDK.
    
    Returns:
        dict: {
            "classification": "prescription" | "spam",
            "confidence": float (0.0 to 1.0),
            "reason": str
        }
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return {
            "classification": "spam",
            "confidence": 0.0,
            "reason": "Gemini API key is not configured in the environment variables (GEMINI_API_KEY or GOOGLE_API_KEY)."
        }
    
    try:
        img = Image.open(image_path)
    except Exception as e:
        return {
            "classification": "spam",
            "confidence": 0.0,
            "reason": f"Failed to load image: {str(e)}"
        }

    # Classification Prompt
    prompt = """
    Analyze the provided image of a document.
    You need to classify it as either:
    1. "prescription" (a doctor's hand-written or printed medical prescription, laboratory test request form, or official medical diagnosis listing tests/services).
    2. "spam" (general chat, greeting images, photos, general text, spam messages, or anything that is NOT a laboratory test request or medical prescription).
    
    Return a JSON object with the following fields:
    - classification: "prescription" or "spam"
    - confidence: a float between 0.0 and 1.0 indicating your confidence in this classification.
    - reason: a brief explanation in English or Arabic of why you chose this classification.
    
    Return ONLY valid JSON. Do not wrap the JSON in markdown code formatting (like ```json).
    """

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, img]
        )
        
        # Clean response text from formatting wrappers
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
            "classification": data.get("classification", "spam"),
            "confidence": float(data.get("confidence", 0.5)),
            "reason": data.get("reason", "")
        }
    except Exception as e:
        print(f"[Classifier] Error: {e}")
        return {
            "classification": "spam",
            "confidence": 0.5,
            "reason": f"Exception during classification: {str(e)}"
        }
