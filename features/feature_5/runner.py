import time
import os
import pyautogui
from features.feature_5.core import *

pyautogui.FAILSAFE = True

def run():
    print("\n" + "█"*70)
    print(" 🤖 ALOA EXAM PILOT (SEMI-AUTO FIXED)")
    print("█"*70)
    print(" [INFO] AI Clicks Answer -> YOU click Next.")
    
    if not os.path.exists(pytesseract.pytesseract.tesseract_cmd):
        print("❌ Tesseract not found.")
        return

    input("\n[ALOA] Press ENTER to Start 10s Timer...")
    
    print("\n⏳ Starting in 10 Seconds. Switch to Quiz!")
    for i in range(10, 0, -1):
        print(f" {i}...", end=" ", flush=True)
        time.sleep(1)
    print("\n🚀 LAUNCHING!")

    while True:
        try:
            print("\n" + "-"*40)
            
            # --- 1. SCAN ---
            print(" 👁️  Scanning...", end="", flush=True)
            gray_img = capture_screen() # Ab ye sahi image dega
            full_text, ocr_data = extract_text_with_coords(gray_img)
            
            if not full_text or len(full_text) < 5:
                print(" ⚠️ Empty Screen. Retrying in 2s...")
                time.sleep(2)
                continue
            print(" Done.")

            # --- 2. SOLVE ---
            print(" 🧠 Solving...", end="", flush=True)
            ai_result = get_ai_answer(full_text)
            
            if "error" in ai_result:
                print(f" ❌ {ai_result['error']}")
                time.sleep(2)
                continue
            print(" Done.")

            # --- 3. CLICK ANSWER ---
            answer_text = ai_result.get('correct_option_text', "")
            print(f" 💡 Answer: {answer_text}")
            
            if answer_text:
                coords = find_coordinates_of_text(answer_text, ocr_data)
                if coords:
                    print(f" 🎯 Clicking Answer at {coords}")
                    pyautogui.moveTo(coords[0], coords[1], duration=0.4)
                    pyautogui.click()
                else:
                    print(" ⚠️ Answer Coordinates not found.")
            
            # --- 4. USER TURN ---
            print("\n ✅ Answer Clicked.")
            print(" 👉 Please Click 'NEXT' manually.")
            print(" ⏳ Waiting 10 seconds...", end="", flush=True)
            
            for i in range(10, 0, -1):
                time.sleep(1)
                print(".", end="", flush=True)
            print(" Ready!")

        except pyautogui.FailSafeException:
            print("\n🛑 STOPPED BY USER.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)