import cv2
import numpy as np
import pytesseract
import mss
import google.generativeai as genai
import json
import time

# --- CONFIGURATION ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

import os

# KEYS — Feature 5 dedicated Gemini keys (3-key rotation)
API_KEYS = [v for v in [
    os.environ.get("GEMINI_API_KEY_F5_1", ""),
    os.environ.get("GEMINI_API_KEY_F5_2", ""),
    os.environ.get("GEMINI_API_KEY_F5_3", ""),
] if v]
if not API_KEYS:
    API_KEYS = [""]
current_key_index = 0

def configure_genai():
    global current_key_index
    try:
        genai.configure(api_key=API_KEYS[current_key_index])
    except: pass
configure_genai()

def rotate_api_key():
    global current_key_index
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    configure_genai()
    print(f"\n ♻️  Switching Key...")

# --- CORE FUNCTIONS ---

def capture_screen():
    with mss.mss() as sct:
        # Monitor 1 capture
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        img_np = np.array(screenshot)
        
        # Convert to Grayscale
        gray_image = cv2.cvtColor(img_np, cv2.COLOR_BGRA2GRAY)
        
        # FIX: Sirf Image return kar rahe hain (Tuple nahi)
        return gray_image

def extract_text_with_coords(image):
    try:
        if image is None: return None, None

        # Simple Threshold (Black & White) - Best for Text
        _, thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        data = pytesseract.image_to_data(thresh, output_type=pytesseract.Output.DICT)
        full_text = " ".join([word for word in data['text'] if word.strip() != ""])
        
        return full_text, data
    except Exception as e:
        print(f"Vision Error: {e}")
        return None, None

def get_ai_answer(context_text):
    max_retries = len(API_KEYS) + 1
    attempts = 0
    while attempts < max_retries:
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            prompt = f"""
            Quiz Solver. 
            TEXT: "{context_text}"
            FORMAT (Strict JSON): {{"correct_option_text": "Answer Text", "confidence": "High"}}
            """
            response = model.generate_content(prompt)
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                rotate_api_key(); attempts += 1; time.sleep(1)
            elif "404" in str(e):
                try: 
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(prompt)
                    return json.loads(response.text.replace("```json", "").replace("```", "").strip())
                except: rotate_api_key(); attempts += 1
            else: return {"error": str(e)}
    return {"error": "Keys Exhausted"}

def find_coordinates_of_text(target_text, ocr_data):
    if not target_text: return None
    target_words = target_text.split()
    if not target_words: return None
    
    # Clean logic
    search_word = target_words[0].lower().strip().replace(".", "").replace(")", "").replace('"', "").replace("'", "")
    
    n_boxes = len(ocr_data['text'])
    for i in range(n_boxes):
        detected_word = ocr_data['text'][i].lower().strip().replace(".", "").replace(")", "").replace('"', "").replace("'", "")
        
        if search_word in detected_word and len(detected_word) > 1:
            x, y, w, h = (ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i])
            return (x + w // 2, y + h // 2)
            
    return None