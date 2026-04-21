"""
╔══════════════════════════════════════════════════════════════════╗
║  ALOA RESUME ENGINE — Feature 9 Core (v1.0)                     ║
║  Profile Management · LLM Integration · ATS Analysis             ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import re
import copy
import time
import html as html_mod
import urllib.request
import urllib.error
import warnings
import webbrowser
import subprocess

warnings.filterwarnings("ignore")

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# ══════════════════════════════════════════════════════════
# API KEYS (same pattern as Feature 6)
# ══════════════════════════════════════════════════════════

GEMINI_API_KEY_1 = os.environ.get("GEMINI_API_KEY_1", "")
GEMINI_API_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = "openrouter/auto"
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-flash-latest"]

# ══════════════════════════════════════════════════════════
# DIRECTORIES
# ══════════════════════════════════════════════════════════

FEATURE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(FEATURE_DIR, "profiles")
OUTPUT_DIR = os.path.join(FEATURE_DIR, "output")


def ensure_dirs():
    """Create profiles and output directories if they don't exist."""
    os.makedirs(PROFILES_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════
# EMPTY PROFILE SCHEMA
# ══════════════════════════════════════════════════════════

EMPTY_PROFILE = {
    "personal": {
        "full_name": "",
        "title": "",
        "email": "",
        "phone": "",
        "location": "",
        "linkedin": "",
        "github": "",
        "portfolio": "",
        "website": ""
    },
    "summary": "",
    "skills": [],
    "experience": [],
    "education": [],
    "projects": [],
    "certifications": [],
    "achievements": [],
    "strengths": [],
    "courses": [],
    "volunteer": []
}


def create_empty_profile():
    """Return a deep copy of the empty profile template."""
    return copy.deepcopy(EMPTY_PROFILE)


# ══════════════════════════════════════════════════════════
# PROFILE I/O
# ══════════════════════════════════════════════════════════

def save_profile(profile, filename=None):
    """Save profile to JSON file. Returns the file path."""
    ensure_dirs()
    if not filename:
        name = profile.get("personal", {}).get("full_name", "untitled").strip()
        name = re.sub(r'[^a-zA-Z0-9_\- ]', '', name).replace(' ', '_').lower()
        filename = f"{name}_resume.json" if name else "untitled_resume.json"
    if not filename.endswith(".json"):
        filename += ".json"
    path = os.path.join(PROFILES_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    return path


def load_profile(filename):
    """Load profile from JSON file."""
    if not filename.endswith(".json"):
        filename += ".json"
    path = os.path.join(PROFILES_DIR, filename)
    if not os.path.isfile(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_profiles():
    """List all saved profile filenames."""
    ensure_dirs()
    return [f for f in os.listdir(PROFILES_DIR) if f.endswith('.json')]


def get_profile_status(profile):
    """
    Returns a dict mapping section name -> (has_data, count_or_length, emoji).
    Used to show which sections are filled in the edit menu.
    """
    status = {}
    p = profile.get("personal", {})
    has_personal = bool(p.get("full_name"))
    status["Personal Info"] = (has_personal, p.get("full_name", "Empty"), "✅" if has_personal else "⬜")

    summ = profile.get("summary", "")
    status["Summary"] = (bool(summ), f"{len(summ.split())} words" if summ else "Empty", "✅" if summ else "⬜")

    exp = profile.get("experience", [])
    status["Experience"] = (bool(exp), f"{len(exp)} job(s)" if exp else "Empty", "✅" if exp else "⬜")

    edu = profile.get("education", [])
    status["Education"] = (bool(edu), f"{len(edu)} entry(s)" if edu else "Empty", "✅" if edu else "⬜")

    proj = profile.get("projects", [])
    status["Projects"] = (bool(proj), f"{len(proj)} project(s)" if proj else "Empty", "✅" if proj else "⬜")

    skills = profile.get("skills", [])
    status["Skills"] = (bool(skills), f"{len(skills)} skill(s)" if skills else "Empty", "✅" if skills else "⬜")

    certs = profile.get("certifications", [])
    status["Certifications"] = (bool(certs), f"{len(certs)} cert(s)" if certs else "Empty", "✅" if certs else "⬜")

    ach = profile.get("achievements", [])
    status["Achievements"] = (bool(ach), f"{len(ach)} item(s)" if ach else "Empty", "✅" if ach else "⬜")

    strengths = profile.get("strengths", [])
    status["Strengths"] = (bool(strengths), f"{len(strengths)} item(s)" if strengths else "Empty", "✅" if strengths else "⬜")

    return status


# ══════════════════════════════════════════════════════════
# LLM INTEGRATION
# ══════════════════════════════════════════════════════════

def _call_gemini(prompt, system_prompt=""):
    """Call Gemini API. Tries multiple keys and models."""
    if genai is None:
        return None

    for key in [GEMINI_API_KEY_1, GEMINI_API_KEY_2]:
        genai.configure(api_key=key)
        for model_name in GEMINI_MODELS:
            try:
                model = genai.GenerativeModel(
                    model_name,
                    system_instruction=system_prompt if system_prompt else None
                )
                response = model.generate_content(prompt)
                if response and response.text:
                    return response.text
            except Exception as e:
                err = str(e).lower()
                if '429' in err or 'quota' in err or 'rate' in err:
                    continue
                continue
    return None


def _call_openrouter(prompt, system_prompt=""):
    """Call OpenRouter API as fallback. Always available."""
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://aloa-agent.local",
            "X-Title": "ALOA Resume Engine",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = json.dumps({
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "max_tokens": 4096,
        }).encode('utf-8')

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body, headers=headers, method='POST'
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result['choices'][0]['message']['content']
    except Exception as e:
        return f"[LLM ERROR] {str(e)}"


def call_llm(prompt, system_prompt=""):
    """Call LLM: tries Gemini first, falls back to OpenRouter."""
    result = _call_gemini(prompt, system_prompt)
    if result and not result.startswith("[LLM ERROR]"):
        return result
    return _call_openrouter(prompt, system_prompt)


# ══════════════════════════════════════════════════════════
# AI EXTRACTION — Brain Dump → Structured Profile
# ══════════════════════════════════════════════════════════

EXTRACTION_SYSTEM = """You are a resume data extraction AI for the ALOA assistant. 
You extract structured information from raw text (LinkedIn bios, old resumes, career descriptions) and return it as a clean JSON object.
You MUST return ONLY valid JSON with no markdown formatting, no code fences, and no explanation."""

EXTRACTION_PROMPT_TEMPLATE = """Extract ALL information from the following raw text and return it as a valid JSON object.

The JSON MUST follow this EXACT schema:
{{
    "personal": {{
        "full_name": "string",
        "title": "string (professional title/role)",
        "email": "string",
        "phone": "string",
        "location": "string (city, state/country)",
        "linkedin": "string (URL or username)",
        "github": "string (URL or username)",
        "portfolio": "string (URL)",
        "website": "string (URL)"
    }},
    "summary": "string (2-4 sentence professional summary — write one if not explicitly stated)",
    "skills": [
        {{"name": "string", "category": "string (Languages/Frameworks/Tools/Databases/Soft Skills/Other)", "proficiency": 75}}
    ],
    "experience": [
        {{
            "title": "string (job title)",
            "company": "string",
            "location": "string",
            "start_date": "string (e.g. Jun 2024)",
            "end_date": "string (e.g. Present)",
            "bullets": ["string (action-oriented, starting with strong verb, include metrics if possible)"]
        }}
    ],
    "education": [
        {{
            "degree": "string (e.g. Bachelor of Science)",
            "field": "string (e.g. Computer Science)",
            "institution": "string",
            "location": "string",
            "start_date": "string",
            "end_date": "string",
            "gpa": "string",
            "coursework": ["string"]
        }}
    ],
    "projects": [
        {{
            "name": "string",
            "technologies": ["string"],
            "date": "string",
            "link": "string",
            "bullets": ["string (what was built, impact, technologies used)"]
        }}
    ],
    "certifications": [
        {{"name": "string", "issuer": "string", "date": "string", "link": "string"}}
    ],
    "achievements": ["string"],
    "strengths": ["string"],
    "courses": [
        {{"name": "string", "provider": "string"}}
    ],
    "volunteer": [
        {{"role": "string", "organization": "string", "bullets": ["string"]}}
    ]
}}

Rules:
- Extract as much information as possible from the text
- For skills proficiency, estimate 1-100 based on context (default 75 if uncertain)
- Make bullet points action-oriented, starting with strong verbs
- If information is not available, use empty string "" or empty array []
- Generate a professional summary if one isn't explicitly provided
- Return ONLY the JSON object, nothing else

───────────────────
RAW TEXT:
{raw_text}
───────────────────"""


def extract_profile_from_text(raw_text):
    """
    Use AI to extract a structured resume profile from raw text.
    Returns a profile dict or None on failure.
    """
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(raw_text=raw_text)
    response = call_llm(prompt, system_prompt=EXTRACTION_SYSTEM)

    if not response or response.startswith("[LLM ERROR]"):
        return None

    # Try to parse JSON from the response
    try:
        # Remove markdown code fences if present
        cleaned = response.strip()
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.strip()

        profile = json.loads(cleaned)

        # Merge with empty profile to ensure all keys exist
        base = create_empty_profile()
        for key in base:
            if key in profile:
                base[key] = profile[key]
        return base
    except json.JSONDecodeError:
        # Try to find JSON in the response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                profile = json.loads(json_match.group())
                base = create_empty_profile()
                for key in base:
                    if key in profile:
                        base[key] = profile[key]
                return base
            except json.JSONDecodeError:
                pass
        return None


# ══════════════════════════════════════════════════════════
# AI — Professional Summary Generator
# ══════════════════════════════════════════════════════════

def generate_summary(profile, target_role=""):
    """Generate a professional summary from profile data."""
    context = json.dumps(profile, indent=2)
    role_hint = f" targeting the role of '{target_role}'" if target_role else ""

    prompt = f"""Based on this resume profile data, write a compelling 2-4 sentence professional summary{role_hint}.

The summary should:
- Start with a strong descriptor (e.g., "Results-driven...", "Detail-oriented...")  
- Mention years of experience and key domain expertise
- Highlight 2-3 top skills or achievements
- Be written in third person without pronouns (no "I", "he", "she")
- Be suitable for the top of a professional resume

Profile Data:
{context}

Return ONLY the summary text, nothing else."""

    result = call_llm(prompt)
    if result and not result.startswith("[LLM ERROR]"):
        return result.strip().strip('"').strip("'")
    return ""


# ══════════════════════════════════════════════════════════
# AI — Bullet Point Rewriter (STAR Format)
# ══════════════════════════════════════════════════════════

def rewrite_bullet(bullet, job_context=""):
    """Rewrite a resume bullet point to be more impactful using STAR format."""
    prompt = f"""Rewrite this resume bullet point to be more impactful and results-oriented.

Original: {bullet}
Job Context: {job_context if job_context else 'General'}

Rules:
- Start with a strong action verb
- Include quantified metrics/results if possible (even estimated)
- Follow STAR format (Situation, Task, Action, Result) compressed into one bullet
- Keep it to 1-2 lines maximum
- Do NOT use first person pronouns

Return ONLY the rewritten bullet point, nothing else."""

    result = call_llm(prompt)
    if result and not result.startswith("[LLM ERROR]"):
        return result.strip().strip('•').strip('-').strip().strip('"')
    return bullet


# ══════════════════════════════════════════════════════════
# ATS ANALYSIS ENGINE
# ══════════════════════════════════════════════════════════

ATS_SYSTEM = """You are an expert ATS (Applicant Tracking System) analyzer and career coach for the ALOA assistant.
You analyze resumes against job descriptions with extreme precision."""

ATS_PROMPT_TEMPLATE = """Analyze this resume against the job description and provide a detailed ATS assessment.

═══ RESUME DATA ═══
{resume_json}

═══ JOB DESCRIPTION ═══
{jd_text}

Provide your analysis in this EXACT format (keep the labels exactly as shown):

ATS_SCORE: <number 0-100>

MATCHING_KEYWORDS: <comma-separated list of keywords found in BOTH the resume and JD>

MISSING_KEYWORDS: <comma-separated list of important JD keywords that are MISSING from the resume>

WEAK_BULLETS:
1. "<original bullet>" → "<improved version>"
2. "<original bullet>" → "<improved version>"

STRENGTHS:
1. <what the resume does well relative to this JD>
2. <another strength>

RECOMMENDATIONS:
1. <specific actionable improvement>
2. <specific actionable improvement>
3. <specific actionable improvement>
4. <specific actionable improvement>
5. <specific actionable improvement>"""


def analyze_ats(profile, job_description):
    """
    Analyze resume profile against a job description.
    Returns a dict with score, matching/missing keywords, recommendations.
    """
    resume_json = json.dumps(profile, indent=2)
    prompt = ATS_PROMPT_TEMPLATE.format(
        resume_json=resume_json,
        jd_text=job_description
    )
    response = call_llm(prompt, system_prompt=ATS_SYSTEM)

    if not response or response.startswith("[LLM ERROR]"):
        return {"error": response or "AI analysis failed."}

    # Parse the response
    result = {
        "raw_response": response,
        "score": 0,
        "matching_keywords": [],
        "missing_keywords": [],
        "weak_bullets": [],
        "strengths": [],
        "recommendations": []
    }

    # Extract ATS score
    score_match = re.search(r'ATS_SCORE:\s*(\d+)', response)
    if score_match:
        result["score"] = int(score_match.group(1))

    # Extract matching keywords
    mk_match = re.search(r'MATCHING_KEYWORDS:\s*(.+?)(?:\n\n|\nMISSING)', response, re.DOTALL)
    if mk_match:
        kws = mk_match.group(1).strip()
        result["matching_keywords"] = [k.strip() for k in kws.split(',') if k.strip()]

    # Extract missing keywords
    miss_match = re.search(r'MISSING_KEYWORDS:\s*(.+?)(?:\n\n|\nWEAK)', response, re.DOTALL)
    if miss_match:
        kws = miss_match.group(1).strip()
        result["missing_keywords"] = [k.strip() for k in kws.split(',') if k.strip()]

    # Extract weak bullets
    wb_match = re.search(r'WEAK_BULLETS:\s*(.+?)(?:\n\n|\nSTRENGTHS)', response, re.DOTALL)
    if wb_match:
        bullets_text = wb_match.group(1).strip()
        result["weak_bullets"] = [b.strip() for b in bullets_text.split('\n') if b.strip() and b.strip()[0].isdigit()]

    # Extract strengths
    str_match = re.search(r'STRENGTHS:\s*(.+?)(?:\n\n|\nRECOMMENDATIONS)', response, re.DOTALL)
    if str_match:
        items = str_match.group(1).strip()
        result["strengths"] = [s.strip() for s in items.split('\n') if s.strip() and s.strip()[0].isdigit()]

    # Extract recommendations
    rec_match = re.search(r'RECOMMENDATIONS:\s*(.+?)$', response, re.DOTALL)
    if rec_match:
        items = rec_match.group(1).strip()
        result["recommendations"] = [r.strip() for r in items.split('\n') if r.strip() and r.strip()[0].isdigit()]

    return result


# ══════════════════════════════════════════════════════════
# RESUME GENERATION — HTML Output
# ══════════════════════════════════════════════════════════

def generate_resume_html(profile, template_name="ats_classic"):
    """
    Generate a resume HTML document from the profile using the specified template.
    Returns the HTML string.
    """
    from features.feature_9.templates import (
        render_ats_classic,
        render_modern_professional,
        render_creative_twocolumn,
    )

    renderers = {
        "ats_classic": render_ats_classic,
        "modern_professional": render_modern_professional,
        "creative_twocolumn": render_creative_twocolumn,
    }

    renderer = renderers.get(template_name, render_ats_classic)
    return renderer(profile)


def save_resume_html(html_content, profile, template_name="ats_classic"):
    """Save the generated HTML to a file. Returns the file path."""
    ensure_dirs()
    name = profile.get("personal", {}).get("full_name", "resume").strip()
    name = re.sub(r'[^a-zA-Z0-9_\- ]', '', name).replace(' ', '_').lower()
    filename = f"{name}_{template_name}.html" if name else f"resume_{template_name}.html"
    path = os.path.join(OUTPUT_DIR, filename)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    return path


def open_in_browser(filepath):
    """Open an HTML file in the default browser."""
    try:
        abs_path = os.path.abspath(filepath)
        webbrowser.open(f'file:///{abs_path.replace(os.sep, "/")}')
        return True
    except Exception:
        return False


def open_in_editor(filepath):
    """Open a file in the default editor (Windows)."""
    try:
        os.startfile(filepath)
        return True
    except Exception:
        try:
            subprocess.Popen(['notepad', filepath])
            return True
        except Exception:
            return False


def try_convert_to_pdf(html_path):
    """
    Attempt to convert HTML to PDF using available libraries.
    Returns (success, pdf_path_or_error).
    """
    pdf_path = html_path.rsplit('.', 1)[0] + '.pdf'

    # Method 1: weasyprint
    try:
        from weasyprint import HTML as WeasyHTML  # type: ignore
        WeasyHTML(filename=html_path).write_pdf(pdf_path)
        return True, pdf_path
    except ImportError:
        pass
    except Exception as e:
        pass

    # Method 2: pdfkit
    try:
        import pdfkit  # type: ignore
        pdfkit.from_file(html_path, pdf_path)
        return True, pdf_path
    except ImportError:
        pass
    except Exception:
        pass

    return False, "No PDF converter available. Use browser Print → Save as PDF (Ctrl+P)."


# ══════════════════════════════════════════════════════════
# LINKEDIN PDF IMPORT
# ══════════════════════════════════════════════════════════

def extract_text_from_pdf(pdf_path):
    """
    Extract raw text from a PDF file (e.g. LinkedIn profile export).
    Returns the extracted text string, or None on failure.
    """
    # Try PyPDF2 first
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: try pdfminer.six if available
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract  # type: ignore
        text = pdfminer_extract(pdf_path)
        if text and text.strip():
            return text
    except ImportError:
        pass
    except Exception:
        pass

    return None
