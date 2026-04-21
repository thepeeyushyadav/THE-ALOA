"""
╔══════════════════════════════════════════════════════════════════╗
║  ALOA RESUME ENGINE — Feature 9 Runner (v1.0)                   ║
║  Interactive CLI: Collect → Edit → Generate → Analyze            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import json

from features.feature_9.core import (
    create_empty_profile,
    save_profile,
    load_profile,
    list_profiles,
    get_profile_status,
    extract_profile_from_text,
    extract_text_from_pdf,
    generate_summary,
    rewrite_bullet,
    analyze_ats,
    generate_resume_html,
    save_resume_html,
    open_in_browser,
    open_in_editor,
    try_convert_to_pdf,
    ensure_dirs,
    PROFILES_DIR,
)


# ──────────────────────────────────────────────────────────
# UI HELPERS (ANSI Colors)
# ──────────────────────────────────────────────────────────

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
WHITE = "\033[97m"
RESET = "\033[0m"


def cprint(text, color=""):
    print(f"{color}{text}{RESET}")


def show_progress(text, steps=3, delay=0.4):
    print(f"   {text}", end="", flush=True)
    for _ in range(steps):
        time.sleep(delay)
        print(".", end="", flush=True)
    print()


def print_divider():
    print("─" * 58)


def print_boxed(lines, color=CYAN):
    width = max(len(line) for line in lines) + 4
    print(f"{color}  ┌{'─' * width}┐{RESET}")
    for line in lines:
        padded = line.ljust(width - 2)
        print(f"{color}  │  {padded}│{RESET}")
    print(f"{color}  └{'─' * width}┘{RESET}")


def safe_input(prompt="  ➤ "):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def ats_score_bar(score):
    """Return a visual progress bar for ATS score."""
    filled = int(score / 5)
    empty = 20 - filled
    if score >= 75:
        color = GREEN
    elif score >= 50:
        color = YELLOW
    else:
        color = RED
    bar = "█" * filled + "░" * empty
    return f"{color}{bar} {score}%{RESET}"


# ──────────────────────────────────────────────────────────
# DATA COLLECTION — Brain Dump Mode
# ──────────────────────────────────────────────────────────

def collect_brain_dump():
    """
    Collects raw text from user and uses AI to extract structured profile.
    Returns a profile dict or None.
    """
    print()
    cprint("  ╔═══════════════════════════════════════════════════╗", CYAN)
    cprint("  ║   🧠 AI Brain Dump Mode                          ║", CYAN)
    cprint("  ║   Paste your resume, LinkedIn bio, or just       ║", CYAN)
    cprint("  ║   describe your career in plain text.            ║", CYAN)
    cprint("  ║                                                   ║", CYAN)
    cprint("  ║   The AI will extract everything automatically.  ║", CYAN)
    cprint("  ╚═══════════════════════════════════════════════════╝", CYAN)
    print()
    cprint("   Paste your text below (type 'DONE' on a new line when finished):", DIM)
    print()

    lines = []
    while True:
        try:
            line = input("   ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip().upper() == "DONE":
            break
        lines.append(line)

    raw_text = "\n".join(lines).strip()
    if not raw_text:
        cprint("   ⚠️  No text provided.", YELLOW)
        return None

    cprint(f"\n   📝 Received {len(raw_text)} characters of text.", DIM)
    show_progress("🤖 AI is extracting your profile data", steps=6, delay=0.5)

    profile = extract_profile_from_text(raw_text)

    if profile:
        name = profile.get("personal", {}).get("full_name", "Unknown")
        skills_count = len(profile.get("skills", []))
        exp_count = len(profile.get("experience", []))
        edu_count = len(profile.get("education", []))
        proj_count = len(profile.get("projects", []))

        cprint(f"\n   ✅ Profile extracted successfully!", GREEN)
        cprint(f"      Name:       {name}", DIM)
        cprint(f"      Skills:     {skills_count} found", DIM)
        cprint(f"      Experience: {exp_count} job(s)", DIM)
        cprint(f"      Education:  {edu_count} entry(s)", DIM)
        cprint(f"      Projects:   {proj_count} project(s)", DIM)
    else:
        cprint("   ❌ AI extraction failed. Try manual entry instead.", RED)

    return profile


# ──────────────────────────────────────────────────────────
# DATA COLLECTION — Manual Entry Helpers
# ──────────────────────────────────────────────────────────

def edit_personal_info(profile):
    """Edit personal information section."""
    p = profile.setdefault("personal", {})
    print()
    cprint("  ── Personal Information ──", CYAN + BOLD)
    print()

    fields = [
        ("full_name", "Full Name"),
        ("title", "Professional Title (e.g. Software Engineer)"),
        ("email", "Email"),
        ("phone", "Phone"),
        ("location", "Location (City, State/Country)"),
        ("linkedin", "LinkedIn (URL or username)"),
        ("github", "GitHub (URL or username)"),
        ("portfolio", "Portfolio URL"),
        ("website", "Website URL"),
    ]

    for key, label in fields:
        current = p.get(key, "")
        display = f" [{current}]" if current else ""
        val = safe_input(f"   {label}{display}: ")
        if val:
            p[key] = val
        # Keep existing if user presses Enter

    cprint("   ✅ Personal info updated.", GREEN)


def edit_summary(profile):
    """Edit or auto-generate professional summary."""
    print()
    cprint("  ── Professional Summary ──", CYAN + BOLD)
    current = profile.get("summary", "")
    if current:
        cprint(f"   Current: {current[:120]}...", DIM)

    print()
    cprint("   [1] Type your own summary", "")
    cprint("   [2] Auto-generate with AI 🤖", "")
    cprint("   [0] Keep current / Skip", "")
    choice = safe_input()

    if choice == "1":
        cprint("   Type your summary (type 'DONE' on a new line when finished):", DIM)
        lines = []
        while True:
            line = safe_input("   ")
            if line.upper() == "DONE":
                break
            lines.append(line)
        text = " ".join(lines).strip()
        if text:
            profile["summary"] = text
            cprint("   ✅ Summary updated.", GREEN)
    elif choice == "2":
        target = safe_input("   Target role (optional, press Enter to skip): ")
        show_progress("🤖 Generating professional summary", steps=4, delay=0.5)
        result = generate_summary(profile, target)
        if result:
            cprint(f"\n   Generated: {result}\n", DIM)
            cprint(f"   Use this summary? [{GREEN}Y{RESET}/{RED}n{RESET}]", "")
            if safe_input().lower() != 'n':
                profile["summary"] = result
                cprint("   ✅ Summary saved.", GREEN)
            else:
                cprint("   ℹ️  Discarded.", DIM)
        else:
            cprint("   ❌ AI generation failed.", RED)


def edit_experience(profile):
    """Edit work experience section."""
    experience = profile.setdefault("experience", [])

    while True:
        print()
        cprint("  ── Work Experience ──", CYAN + BOLD)
        if experience:
            for i, exp in enumerate(experience, 1):
                cprint(f"   {i}. {exp.get('title', 'Untitled')} @ {exp.get('company', '?')} ({exp.get('start_date', '?')} – {exp.get('end_date', '?')})", "")
                bullets = exp.get("bullets", [])
                cprint(f"      {len(bullets)} bullet point(s)", DIM)
        else:
            cprint("   (No experience added yet)", DIM)

        print()
        cprint("   [A] Add new job", "")
        cprint("   [E] Edit a job (enter number after E, e.g. E1)", "")
        cprint("   [D] Delete a job (enter number after D, e.g. D1)", "")
        cprint("   [0] Done with Experience", "")
        choice = safe_input().upper()

        if choice == "0" or choice == "":
            break
        elif choice == "A":
            job = _collect_single_experience()
            if job:
                experience.append(job)
                cprint("   ✅ Job added.", GREEN)
        elif choice.startswith("E") and len(choice) > 1:
            try:
                idx = int(choice[1:]) - 1
                if 0 <= idx < len(experience):
                    experience[idx] = _collect_single_experience(experience[idx])
                    cprint("   ✅ Job updated.", GREEN)
                else:
                    cprint("   ⚠️  Invalid number.", YELLOW)
            except ValueError:
                cprint("   ⚠️  Invalid input.", YELLOW)
        elif choice.startswith("D") and len(choice) > 1:
            try:
                idx = int(choice[1:]) - 1
                if 0 <= idx < len(experience):
                    removed = experience.pop(idx)
                    cprint(f"   🗑️  Deleted: {removed.get('title', '')} @ {removed.get('company', '')}", RED)
                else:
                    cprint("   ⚠️  Invalid number.", YELLOW)
            except ValueError:
                cprint("   ⚠️  Invalid input.", YELLOW)


def _collect_single_experience(existing=None):
    """Collect data for a single job entry."""
    e = existing or {}
    print()
    cprint("   --- Job Details ---", DIM)

    fields = [
        ("title", "Job Title"),
        ("company", "Company Name"),
        ("location", "Location"),
        ("start_date", "Start Date (e.g. Jun 2024)"),
        ("end_date", "End Date (e.g. Present)"),
    ]

    for key, label in fields:
        current = e.get(key, "")
        display = f" [{current}]" if current else ""
        val = safe_input(f"   {label}{display}: ")
        if val:
            e[key] = val

    # Bullet points
    bullets = e.get("bullets", [])
    cprint(f"\n   Bullet points ({len(bullets)} existing):", DIM)
    for i, b in enumerate(bullets, 1):
        cprint(f"   {i}. {b[:80]}{'...' if len(b) > 80 else ''}", DIM)

    cprint("   Add more bullets? (one per line, empty line to stop):", DIM)
    while True:
        b = safe_input("   • ")
        if not b:
            break
        bullets.append(b)
    e["bullets"] = bullets

    return e


def edit_education(profile):
    """Edit education section."""
    education = profile.setdefault("education", [])

    while True:
        print()
        cprint("  ── Education ──", CYAN + BOLD)
        if education:
            for i, edu in enumerate(education, 1):
                cprint(f"   {i}. {edu.get('degree', '')} in {edu.get('field', '')} — {edu.get('institution', '')} ({edu.get('end_date', '?')})", "")
        else:
            cprint("   (No education added yet)", DIM)

        print()
        cprint("   [A] Add  [D#] Delete  [0] Done", "")
        choice = safe_input().upper()

        if choice == "0" or choice == "":
            break
        elif choice == "A":
            edu = {}
            for key, label in [("degree", "Degree"), ("field", "Field of Study"),
                                ("institution", "Institution"), ("location", "Location"),
                                ("start_date", "Start Year"), ("end_date", "End Year"),
                                ("gpa", "GPA/CGPA (optional)")]:
                val = safe_input(f"   {label}: ")
                if val:
                    edu[key] = val

            cprint("   Relevant coursework (comma-separated, or Enter to skip):", DIM)
            cw = safe_input("   ")
            if cw:
                edu["coursework"] = [c.strip() for c in cw.split(",") if c.strip()]
            else:
                edu["coursework"] = []

            education.append(edu)
            cprint("   ✅ Education added.", GREEN)
        elif choice.startswith("D") and len(choice) > 1:
            try:
                idx = int(choice[1:]) - 1
                if 0 <= idx < len(education):
                    education.pop(idx)
                    cprint("   🗑️  Deleted.", RED)
            except ValueError:
                pass


def edit_projects(profile):
    """Edit projects section."""
    projects = profile.setdefault("projects", [])

    while True:
        print()
        cprint("  ── Projects ──", CYAN + BOLD)
        if projects:
            for i, proj in enumerate(projects, 1):
                techs = ", ".join(proj.get("technologies", []))
                cprint(f"   {i}. {proj.get('name', 'Untitled')} [{techs}]", "")
        else:
            cprint("   (No projects added yet)", DIM)

        print()
        cprint("   [A] Add  [D#] Delete  [0] Done", "")
        choice = safe_input().upper()

        if choice == "0" or choice == "":
            break
        elif choice == "A":
            proj = {}
            proj["name"] = safe_input("   Project Name: ")
            proj["date"] = safe_input("   Date (e.g. Feb 2024): ")
            proj["link"] = safe_input("   Link (optional): ")

            techs = safe_input("   Technologies (comma-separated): ")
            proj["technologies"] = [t.strip() for t in techs.split(",") if t.strip()]

            cprint("   Bullet points (one per line, empty to stop):", DIM)
            bullets = []
            while True:
                b = safe_input("   • ")
                if not b:
                    break
                bullets.append(b)
            proj["bullets"] = bullets

            projects.append(proj)
            cprint("   ✅ Project added.", GREEN)
        elif choice.startswith("D") and len(choice) > 1:
            try:
                idx = int(choice[1:]) - 1
                if 0 <= idx < len(projects):
                    projects.pop(idx)
                    cprint("   🗑️  Deleted.", RED)
            except ValueError:
                pass


def edit_skills(profile):
    """Edit skills section."""
    skills = profile.setdefault("skills", [])

    while True:
        print()
        cprint("  ── Skills ──", CYAN + BOLD)
        if skills:
            from features.feature_9.templates import _skills_by_category
            groups = _skills_by_category(skills)
            for cat, items in groups.items():
                names = ", ".join(s["name"] for s in items)
                cprint(f"   {cat}: {names}", "")
        else:
            cprint("   (No skills added yet)", DIM)

        print()
        cprint("   [A] Add skills  [C] Clear all  [0] Done", "")
        choice = safe_input().upper()

        if choice == "0" or choice == "":
            break
        elif choice == "A":
            cprint("   Category (e.g. Languages, Frameworks, Tools, Databases, Soft Skills):", DIM)
            category = safe_input("   Category: ") or "Other"
            cprint("   Skills (comma-separated):", DIM)
            names = safe_input("   Skills: ")
            if names:
                for name in names.split(","):
                    name = name.strip()
                    if name:
                        prof_str = safe_input(f"   Proficiency for '{name}' (1-100, default 75): ") or "75"
                        try:
                            prof = int(prof_str)
                        except ValueError:
                            prof = 75
                        skills.append({"name": name, "category": category, "proficiency": prof})
                cprint("   ✅ Skills added.", GREEN)
        elif choice == "C":
            cprint(f"   Clear all {len(skills)} skills? [y/N]", YELLOW)
            if safe_input().lower() == 'y':
                skills.clear()
                cprint("   🗑️  All skills cleared.", RED)


def edit_simple_list(profile, key, label):
    """Edit a simple list section (achievements, strengths)."""
    items = profile.setdefault(key, [])

    while True:
        print()
        cprint(f"  ── {label} ──", CYAN + BOLD)
        if items:
            for i, item in enumerate(items, 1):
                cprint(f"   {i}. {item}", "")
        else:
            cprint(f"   (No {label.lower()} added yet)", DIM)

        print()
        cprint("   [A] Add  [D#] Delete  [0] Done", "")
        choice = safe_input().upper()

        if choice == "0" or choice == "":
            break
        elif choice == "A":
            cprint(f"   Add {label.lower()} (one per line, empty to stop):", DIM)
            while True:
                item = safe_input("   • ")
                if not item:
                    break
                items.append(item)
            cprint("   ✅ Added.", GREEN)
        elif choice.startswith("D") and len(choice) > 1:
            try:
                idx = int(choice[1:]) - 1
                if 0 <= idx < len(items):
                    items.pop(idx)
                    cprint("   🗑️  Deleted.", RED)
            except ValueError:
                pass


def edit_certifications(profile):
    """Edit certifications section."""
    certs = profile.setdefault("certifications", [])

    while True:
        print()
        cprint("  ── Certifications ──", CYAN + BOLD)
        if certs:
            for i, c in enumerate(certs, 1):
                cprint(f"   {i}. {c.get('name', '')} — {c.get('issuer', '')}", "")
        else:
            cprint("   (No certifications added yet)", DIM)

        print()
        cprint("   [A] Add  [D#] Delete  [0] Done", "")
        choice = safe_input().upper()

        if choice == "0" or choice == "":
            break
        elif choice == "A":
            cert = {
                "name": safe_input("   Certification Name: "),
                "issuer": safe_input("   Issuing Organization: "),
                "date": safe_input("   Date (optional): "),
                "link": safe_input("   Credential Link (optional): "),
            }
            certs.append(cert)
            cprint("   ✅ Certification added.", GREEN)
        elif choice.startswith("D") and len(choice) > 1:
            try:
                idx = int(choice[1:]) - 1
                if 0 <= idx < len(certs):
                    certs.pop(idx)
                    cprint("   🗑️  Deleted.", RED)
            except ValueError:
                pass


# ──────────────────────────────────────────────────────────
# PROFILE EDIT MENU — Central Hub
# ──────────────────────────────────────────────────────────

def profile_edit_menu(profile):
    """Show the profile editing menu. Returns the (possibly modified) profile."""
    while True:
        print()
        print_divider()
        name = profile.get("personal", {}).get("full_name", "Untitled")
        cprint(f"  📋 Resume Profile: {BOLD}{name}{RESET}", CYAN)
        print_divider()

        status = get_profile_status(profile)
        section_map = {
            "1": ("Personal Info", edit_personal_info),
            "2": ("Summary", edit_summary),
            "3": ("Experience", edit_experience),
            "4": ("Education", edit_education),
            "5": ("Projects", edit_projects),
            "6": ("Skills", edit_skills),
            "7": ("Certifications", edit_certifications),
            "8": ("Achievements", lambda p: edit_simple_list(p, "achievements", "Achievements")),
            "9": ("Strengths", lambda p: edit_simple_list(p, "strengths", "Strengths")),
        }

        for key, (label, _) in section_map.items():
            if label in status:
                has_data, detail, emoji = status[label]
                cprint(f"   [{key}] {label:<18s} {emoji} ({detail})", "")
            else:
                cprint(f"   [{key}] {label}", "")

        print()
        print_divider()
        cprint(f"   [{GREEN}G{RESET}] 🎨 Generate Resume (choose template)", "")
        cprint(f"   [{GREEN}A{RESET}] 📊 Analyze Resume (ATS Score)", "")
        cprint(f"   [{CYAN}V{RESET}] 👁️  View Full Profile (JSON)", "")
        cprint(f"   [{CYAN}S{RESET}] 💾 Save Profile", "")
        cprint(f"   [{CYAN}O{RESET}] 📂 Open JSON in Editor", "")
        cprint(f"   [{RED}0{RESET}] ← Back to Feature Menu", "")
        print()

        choice = safe_input().upper()

        if choice == "0":
            # Auto-save before leaving
            path = save_profile(profile)
            cprint(f"   💾 Auto-saved: {os.path.basename(path)}", DIM)
            break
        elif choice in section_map:
            _, editor = section_map[choice]
            editor(profile)
        elif choice == "G":
            generate_resume_flow(profile)
        elif choice == "A":
            ats_analysis_flow(profile)
        elif choice == "V":
            print()
            cprint(json.dumps(profile, indent=2, ensure_ascii=False), DIM)
        elif choice == "S":
            path = save_profile(profile)
            cprint(f"   ✅ Saved: {path}", GREEN)
        elif choice == "O":
            path = save_profile(profile)
            open_in_editor(path)
            cprint(f"   📝 Opened in editor. Edit, save, then reload here.", DIM)
            cprint(f"   Press Enter when done editing...", DIM)
            safe_input()
            reloaded = load_profile(os.path.basename(path))
            if reloaded:
                profile.update(reloaded)
                cprint("   ✅ Profile reloaded from file.", GREEN)
        else:
            cprint("   ⚠️  Invalid choice.", YELLOW)

    return profile


# ──────────────────────────────────────────────────────────
# RESUME GENERATION FLOW
# ──────────────────────────────────────────────────────────

def generate_resume_flow(profile):
    """Interactive resume generation with template selection."""
    print()
    cprint("  ╔═══════════════════════════════════════════════════╗", GREEN)
    cprint("  ║       🎨 RESUME GENERATION                       ║", GREEN)
    cprint("  ╚═══════════════════════════════════════════════════╝", GREEN)
    print()

    cprint("   Choose a template:\n", "")
    cprint("   [1] 📄 ATS Classic", BOLD)
    cprint("       Single-column, clean, ATS-optimized.", DIM)
    cprint("       Best for: Tech, Engineering, FAANG applications.\n", DIM)

    cprint("   [2] 🎯 Modern Professional", BOLD)
    cprint("       Colored header, timeline layout, accent tags.", DIM)
    cprint("       Best for: Corporate, Consulting, Management.\n", DIM)

    cprint("   [3] 🎨 Creative Two-Column", BOLD)
    cprint("       Dark sidebar, skill bars, modern split layout.", DIM)
    cprint("       Best for: Marketing, Design, Creative roles.\n", DIM)

    cprint("   [A] Generate ALL 3 templates at once", BOLD)
    print()

    choice = safe_input()

    template_map = {
        "1": ("ats_classic", "ATS Classic"),
        "2": ("modern_professional", "Modern Professional"),
        "3": ("creative_twocolumn", "Creative Two-Column"),
    }

    if choice == "A":
        templates_to_gen = list(template_map.values())
    elif choice in template_map:
        templates_to_gen = [template_map[choice]]
    else:
        cprint("   ⚠️  Invalid choice. Cancelled.", YELLOW)
        return

    for template_key, template_name in templates_to_gen:
        show_progress(f"🎨 Generating {template_name}")
        html = generate_resume_html(profile, template_key)
        path = save_resume_html(html, profile, template_key)

        cprint(f"   ✅ {template_name} → {os.path.basename(path)}", GREEN)

        # Try PDF conversion
        pdf_ok, pdf_result = try_convert_to_pdf(path)
        if pdf_ok:
            cprint(f"   📄 PDF → {os.path.basename(pdf_result)}", GREEN)
        else:
            cprint(f"   ℹ️  {pdf_result}", DIM)

    # Open the last generated file in browser
    cprint(f"\n   Open in browser? [{GREEN}Y{RESET}/{RED}n{RESET}]", "")
    if safe_input().lower() != 'n':
        open_in_browser(path)
        cprint("   🌐 Opened in browser! Use Ctrl+P to save as PDF.", GREEN)

    print()
    cprint(f"   📁 Output folder: {os.path.dirname(path)}", DIM)


# ──────────────────────────────────────────────────────────
# ATS ANALYSIS FLOW
# ──────────────────────────────────────────────────────────

def ats_analysis_flow(profile):
    """Interactive ATS analysis against a job description."""
    print()
    cprint("  ╔═══════════════════════════════════════════════════╗", MAGENTA)
    cprint("  ║       📊 ATS RESUME ANALYZER                     ║", MAGENTA)
    cprint("  ╚═══════════════════════════════════════════════════╝", MAGENTA)
    print()
    cprint("   Paste the Job Description below (type 'DONE' on a new line when finished):", DIM)
    print()

    lines = []
    while True:
        try:
            line = input("   ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip().upper() == "DONE":
            break
        lines.append(line)

    jd_text = "\n".join(lines).strip()
    if not jd_text:
        cprint("   ⚠️  No job description provided.", YELLOW)
        return

    cprint(f"\n   📝 Received {len(jd_text)} characters.", DIM)
    show_progress("🤖 AI is analyzing your resume against the JD", steps=6, delay=0.6)

    result = analyze_ats(profile, jd_text)

    if result.get("error"):
        cprint(f"   ❌ {result['error']}", RED)
        return

    # ── Display Results ──
    print()
    print_divider()
    cprint("  📊 ATS ANALYSIS RESULTS", BOLD)
    print_divider()

    # Score bar
    score = result.get("score", 0)
    print()
    cprint(f"   ATS Match Score: {ats_score_bar(score)}", "")
    print()

    # Matching keywords
    matching = result.get("matching_keywords", [])
    if matching:
        cprint(f"   ✅ Matching Keywords ({len(matching)}):", GREEN)
        cprint(f"      {', '.join(matching[:20])}", DIM)
        print()

    # Missing keywords
    missing = result.get("missing_keywords", [])
    if missing:
        cprint(f"   ❌ Missing Keywords ({len(missing)}):", RED)
        cprint(f"      {', '.join(missing[:20])}", YELLOW)
        print()

    # Strengths
    strengths = result.get("strengths", [])
    if strengths:
        cprint("   💪 Strengths:", GREEN)
        for s in strengths[:5]:
            cprint(f"      {s}", DIM)
        print()

    # Weak bullets
    weak = result.get("weak_bullets", [])
    if weak:
        cprint("   ✏️  Bullet Improvements:", YELLOW)
        for w in weak[:5]:
            cprint(f"      {w}", DIM)
        print()

    # Recommendations
    recs = result.get("recommendations", [])
    if recs:
        cprint("   💡 Recommendations:", CYAN)
        for r in recs[:5]:
            cprint(f"      {r}", DIM)

    print()
    print_divider()

    # Offer to add missing skills
    if missing:
        print()
        cprint(f"   Add missing keywords to your skills? [{GREEN}Y{RESET}/{RED}n{RESET}]", "")
        if safe_input().lower() != 'n':
            skills = profile.setdefault("skills", [])
            existing_names = {s.get("name", "").lower() for s in skills}
            added = 0
            for kw in missing:
                if kw.lower() not in existing_names:
                    skills.append({"name": kw, "category": "Other", "proficiency": 70})
                    added += 1
            cprint(f"   ✅ Added {added} new skill(s) to your profile.", GREEN)


# ──────────────────────────────────────────────────────────
# LINKEDIN PDF IMPORT FLOW
# ──────────────────────────────────────────────────────────

def linkedin_pdf_import():
    """
    Import a LinkedIn profile PDF export.
    Extracts text from the PDF and feeds it through the AI brain dump engine.
    Returns a profile dict or None.
    """
    print()
    cprint("  ╔═══════════════════════════════════════════════════╗", BLUE)
    cprint("  ║   🔗 LinkedIn PDF Import                         ║", BLUE)
    cprint("  ║                                                   ║", BLUE)
    cprint("  ║   How to get your LinkedIn PDF:                  ║", BLUE)
    cprint("  ║   1. Go to your LinkedIn profile page            ║", BLUE)
    cprint("  ║   2. Click \"Resources\" button                    ║", BLUE)
    cprint("  ║   3. Click \"Save to PDF\"                         ║", BLUE)
    cprint("  ║   4. A PDF will download to your computer        ║", BLUE)
    cprint("  ║   5. Select that file below                      ║", BLUE)
    cprint("  ╚═══════════════════════════════════════════════════╝", BLUE)
    print()

    # Try tkinter file dialog first
    pdf_path = None
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        pdf_path = filedialog.askopenfilename(
            title="Select your LinkedIn PDF",
            filetypes=[
                ("PDF files", "*.pdf"),
                ("All files", "*.*")
            ]
        )
        root.destroy()
    except Exception:
        pass

    # Fallback: ask the user to type the path
    if not pdf_path:
        cprint("   Enter full path to your LinkedIn PDF:", DIM)
        pdf_path = safe_input("   Path: ").strip().strip('"').strip("'")

    if not pdf_path:
        cprint("   ⚠️  No file selected.", YELLOW)
        return None

    if not os.path.isfile(pdf_path):
        cprint(f"   ❌ File not found: {pdf_path}", RED)
        return None

    cprint(f"\n   📄 Reading: {os.path.basename(pdf_path)}", DIM)
    show_progress("📖 Extracting text from PDF", steps=3, delay=0.4)

    raw_text = extract_text_from_pdf(pdf_path)

    if not raw_text or len(raw_text.strip()) < 20:
        cprint("   ❌ Could not extract text from PDF.", RED)
        cprint("   ℹ️  Make sure PyPDF2 is installed: pip install PyPDF2", DIM)
        return None

    cprint(f"   ✅ Extracted {len(raw_text)} characters from PDF.", GREEN)
    show_progress("🤖 AI is building your profile from LinkedIn data", steps=6, delay=0.5)

    profile = extract_profile_from_text(raw_text)

    if profile:
        name = profile.get("personal", {}).get("full_name", "Unknown")
        skills_count = len(profile.get("skills", []))
        exp_count = len(profile.get("experience", []))
        edu_count = len(profile.get("education", []))
        proj_count = len(profile.get("projects", []))

        cprint(f"\n   ✅ LinkedIn profile imported successfully!", GREEN)
        cprint(f"      Name:       {name}", DIM)
        cprint(f"      Skills:     {skills_count} found", DIM)
        cprint(f"      Experience: {exp_count} job(s)", DIM)
        cprint(f"      Education:  {edu_count} entry(s)", DIM)
        cprint(f"      Projects:   {proj_count} project(s)", DIM)
    else:
        cprint("   ❌ AI extraction from LinkedIn data failed.", RED)

    return profile


# ──────────────────────────────────────────────────────────
# LOAD EXISTING PROFILE
# ──────────────────────────────────────────────────────────

def load_profile_flow():
    """Interactive profile loading."""
    profiles = list_profiles()

    if not profiles:
        cprint("   ℹ️  No saved profiles found.", DIM)
        return None

    print()
    cprint("  ── Saved Profiles ──", CYAN + BOLD)
    for i, name in enumerate(profiles, 1):
        cprint(f"   [{i}] {name}", "")
    print()

    choice = safe_input("   Select profile number: ")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(profiles):
            profile = load_profile(profiles[idx])
            if profile:
                cprint(f"   ✅ Loaded: {profiles[idx]}", GREEN)
                return profile
            else:
                cprint("   ❌ Failed to load profile.", RED)
        else:
            cprint("   ⚠️  Invalid number.", YELLOW)
    except ValueError:
        cprint("   ⚠️  Invalid input.", YELLOW)
    return None


# ──────────────────────────────────────────────────────────
# MAIN RUNNER
# ──────────────────────────────────────────────────────────

def run():
    print()
    cprint("  ╔══════════════════════════════════════════════════════════╗", CYAN)
    cprint("  ║       📄  ALOA RESUME ENGINE v1.0                      ║", CYAN)
    cprint("  ║       Generate · Analyze · Optimize                     ║", CYAN)
    cprint("  ╚══════════════════════════════════════════════════════════╝", CYAN)
    print()

    ensure_dirs()
    current_profile = None

    while True:
        print()
        print_divider()
        if current_profile:
            name = current_profile.get("personal", {}).get("full_name", "Untitled")
            cprint(f"  Active Profile: {BOLD}{name}{RESET}", GREEN)
        else:
            cprint("  No profile loaded.", DIM)
        print_divider()

        print()
        cprint("   [1] 🧠 Create New Resume (AI Brain Dump)", "")
        cprint("   [2] ✏️  Create New Resume (Manual Entry)", "")
        cprint("   [3] 🔗 Import from LinkedIn PDF", "")
        cprint("   [4] 📂 Load Existing Profile", "")
        if current_profile:
            cprint("   [5] 📝 Edit Current Profile", "")
            cprint("   [6] 🎨 Generate Resume (Choose Template)", "")
            cprint("   [7] 📊 Analyze Resume (ATS Score)", "")
        cprint("   [0] ← Back to Main Menu", "")
        print()

        choice = safe_input("  Select: ")

        # ── Back ──
        if choice == "0":
            if current_profile:
                path = save_profile(current_profile)
                cprint(f"   💾 Auto-saved: {os.path.basename(path)}", DIM)
            break

        # ── Brain Dump ──
        elif choice == "1":
            profile = collect_brain_dump()
            if profile:
                current_profile = profile
                path = save_profile(current_profile)
                cprint(f"   💾 Saved: {os.path.basename(path)}", GREEN)
                cprint(f"\n   Review and edit your profile now? [{GREEN}Y{RESET}/{RED}n{RESET}]", "")
                if safe_input().lower() != 'n':
                    current_profile = profile_edit_menu(current_profile)

        # ── Manual Entry ──
        elif choice == "2":
            current_profile = create_empty_profile()
            cprint("   📋 New blank profile created. Let's fill it in:", GREEN)
            edit_personal_info(current_profile)
            cprint(f"\n   Continue editing other sections? [{GREEN}Y{RESET}/{RED}n{RESET}]", "")
            if safe_input().lower() != 'n':
                current_profile = profile_edit_menu(current_profile)
            else:
                path = save_profile(current_profile)
                cprint(f"   💾 Saved: {os.path.basename(path)}", GREEN)

        # ── LinkedIn PDF Import ──
        elif choice == "3":
            profile = linkedin_pdf_import()
            if profile:
                current_profile = profile
                path = save_profile(current_profile)
                cprint(f"   💾 Saved: {os.path.basename(path)}", GREEN)
                cprint(f"\n   Review and edit your profile now? [{GREEN}Y{RESET}/{RED}n{RESET}]", "")
                if safe_input().lower() != 'n':
                    current_profile = profile_edit_menu(current_profile)

        # ── Load ──
        elif choice == "4":
            loaded = load_profile_flow()
            if loaded:
                current_profile = loaded

        # ── Edit ──
        elif choice == "5" and current_profile:
            current_profile = profile_edit_menu(current_profile)

        # ── Generate ──
        elif choice == "6" and current_profile:
            generate_resume_flow(current_profile)

        # ── Analyze ──
        elif choice == "7" and current_profile:
            ats_analysis_flow(current_profile)

        else:
            max_choice = "7" if current_profile else "4"
            cprint(f"   ⚠️  Invalid choice. Please select 0-{max_choice}.", YELLOW)

    print()
    cprint("  [ALOA] Returning to Main Menu...\n", DIM)
