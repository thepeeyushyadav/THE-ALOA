import os
import sys
import warnings
import re

# --- 1. SETUP & DEPENDENCY CHECK ---
warnings.filterwarnings("ignore")
os.environ["GRPC_VERBOSITY"] = "ERROR"

try:
    import google.generativeai as genai
    from fpdf import FPDF

    # --- youtube-transcript-api v1.x (new instance-based API) ---
    from youtube_transcript_api import YouTubeTranscriptApi

except ImportError as e:
    print(f"\n[CRITICAL ERROR] Library Missing: {e}")
    print("Run: pip install google-generativeai youtube-transcript-api fpdf2")
    sys.exit()

# Load Gemini API key from env var
API_KEY = os.environ.get("GEMINI_API_KEY_1", "")
genai.configure(api_key=API_KEY)

# Model preference order (gemini-2.0-flash is stable and widely available)
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-flash-latest"]

# Create a reusable API instance (youtube-transcript-api v1.x)
ytt_api = YouTubeTranscriptApi()

# --- 3. CORE FUNCTIONS ---

def get_video_id(url):
    """Extracts the 11-character Video ID from a YouTube URL."""
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return None

def fetch_transcript(video_id):
    """
    Fetches the transcript using youtube-transcript-api v1.x.
    Tries English first, then Hindi, then falls back to any available transcript.
    """
    try:
        # Try common languages first (en, hi)
        try:
            transcript = ytt_api.fetch(video_id, languages=["en", "hi"])
        except Exception:
            # Fallback: get the first available transcript
            transcript_list = ytt_api.list(video_id)
            first_transcript = next(iter(transcript_list))
            transcript = first_transcript.fetch()

        # FetchedTranscript is iterable, each snippet has .text attribute
        full_text = " ".join([snippet.text for snippet in transcript])
        return full_text

    except Exception as e:
        error_msg = str(e)
        if "Subtitles are disabled" in error_msg or "TranscriptsDisabled" in error_msg:
            return "ERROR: Subtitles are disabled for this video."
        if "cookies" in error_msg or "IpBlocked" in error_msg or "RequestBlocked" in error_msg:
            return "ERROR: YouTube blocked access (Try a different video)."
        return f"ERROR: {error_msg}"

def generate_structured_notes(transcript):
    """Generates notes using Gemini AI. Tries multiple model versions as fallback."""
    prompt = f"""
Act as an Expert Professor. Analyze this transcript and create structured notes.

TRANSCRIPT START:
{transcript[:30000]}
TRANSCRIPT END.

INSTRUCTIONS:
1. If NOT educational, output ONLY "NOT_EDUCATIONAL".
2. Format as Markdown:
   # [Title]
   ### 🎯 Core Concept
   ### 📖 Detailed Breakdown
   ### ⚙️ Workflow / Steps
   ### 🚀 Applications
   ### 📝 Summary
"""

    last_error = None
    for model_name in GEMINI_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = e
            continue  # Try next model

    return f"AI PROCESSING ERROR: {last_error}"

def save_notes_to_file(title, content):
    """Saves to MD and PDF."""
    clean_title = "".join(x for x in title if x.isalnum() or x in " _-")
    if not clean_title:
        clean_title = "Lecture_Notes"

    md_filename = f"{clean_title}.md"
    pdf_filename = f"{clean_title}.pdf"  # FIX: was 'filename' (undefined variable)

    # Save Markdown
    with open(md_filename, "w", encoding="utf-8") as f:
        f.write(content)

    # Save PDF
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        safe_content = content.encode('latin-1', 'replace').decode('latin-1')
        for line in safe_content.split('\n'):
            pdf.multi_cell(0, 8, line)
        pdf.output(pdf_filename, 'F')  # FIX: was 'filename' (undefined variable)
    except Exception as e:
        return md_filename, None, f"Error saving PDF: {e}"

    return md_filename, pdf_filename, "Success"