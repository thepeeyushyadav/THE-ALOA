import time
import sys
# Importing core functions
from features.feature_4.core import *

def loading_animation(task_name):
    """Displays a simple loading animation in English."""
    print(f"   ⏳ {task_name}", end="", flush=True)
    for _ in range(3):
        time.sleep(0.3)
        print(".", end="", flush=True)
    print(" Done. ✅")

def run():
    print("\n" + "█"*70)
    print(" 🎓 ALOA LECTURE NOTE GENERATOR (v2.0)")
    print("█"*70)
    print(" System: Ready to process YouTube Educational Content.")
    print(" Outputs: Markdown (.md) and PDF (.pdf)")

    while True:
        # 1. Input Loop
        print("-" * 60)
        url = input("[ALOA] 🔗 Paste YouTube Link (or type 'exit' to go back): ").strip()
        
        if url.lower() in ['exit', 'back', '0']:
            print("[ALOA] Returning to Main Menu...")
            break
        
        if not url: continue

        # 2. Extract ID
        video_id = get_video_id(url)
        if not video_id:
            print("   ❌ Error: Invalid YouTube URL. Please try again.")
            continue
            
        print(f"   🆔 Video ID Detected: {video_id}")

        # 3. Fetch Transcript
        print("   📥 Fetching Transcript...", end="")
        transcript = fetch_transcript(video_id)
        
        if "ERROR" in transcript:
            print(f"\n   ❌ {transcript}")
            continue
        else:
            print(" Success.")
            print(f"   📄 Transcript Length: {len(transcript)} characters.")

        # 4. Generate Notes (AI)
        loading_animation("AI Professor is analyzing the lecture")
        
        notes = generate_structured_notes(transcript)
        
        # Error Checks
        if "AI PROCESSING ERROR" in notes:
            print(f"\n   ❌ {notes}")
            continue

        if "NOT_EDUCATIONAL" in notes:
            print("\n   ⚠️ ALERT: AI detected this is NOT an educational video.")
            print("   Skipping note generation to maintain quality.")
            continue

        # 5. Save Files
        file_title = input("\n   📝 Enter a filename for these notes (e.g., Python_Basics): ").strip()
        if not file_title: file_title = "Lecture_Notes"
        
        print("   💾 Saving files...", end="")
        md_file, pdf_file, status = save_notes_to_file(file_title, notes)
        
        if status != "Success":
             print(f"\n   ⚠️ Warning: {status}")
        else:
             print(" Done.")

        # 6. Final Report
        print("\n" + "="*60)
        print(f" ✅ NOTES GENERATED SUCCESSFULLY")
        print(f" 📂 Markdown File: {md_file}")
        print(f" 📄 PDF Document : {pdf_file}")
        print("="*60)