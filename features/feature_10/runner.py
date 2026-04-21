"""
╔══════════════════════════════════════════════════════════════════╗
║  ALOA RADAR — Feature 10 Runner (v3.0)                          ║
║  Daily Intelligence Brief — Resume-Aware · Professional Report  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import time
from datetime import datetime

from features.feature_10.core import (
    load_watchlist,
    save_watchlist,
    build_brief,
    load_cache,
    extract_pdf_text,
    DEFAULT_WATCHLIST,
    REPORT_SECTIONS,
)

# ── ANSI Colours ──────────────────────────────────────────
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
DIM     = "\033[2m"
BOLD    = "\033[1m"
MAGENTA = "\033[95m"
BLUE    = "\033[94m"
WHITE   = "\033[97m"
RESET   = "\033[0m"

# Section → (icon, display label, color)
SECTION_META = {
    "CURRENT AFFAIRS":   ("📌", "CURRENT AFFAIRS",    YELLOW),
    "TECH NEWS":         ("🔬", "TECH NEWS",           CYAN),
    "TRENDING TECH":     ("🚀", "TRENDING TECH",       GREEN),
    "GENERAL KNOWLEDGE": ("💡", "GENERAL KNOWLEDGE",   MAGENTA),
    "SUGGESTIONS":       ("🎯", "SUGGESTIONS FOR YOU", RED),
}


# ──────────────────────────────────────────────────────────
#  UI HELPERS
# ──────────────────────────────────────────────────────────

def cprint(text, color=""):
    print(f"{color}{text}{RESET}")


def safe_input(prompt="  ➤ "):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def show_progress(text, steps=8, delay=0.45):
    print(f"\n   {text}", end="", flush=True)
    for _ in range(steps):
        time.sleep(delay)
        print(".", end="", flush=True)
    print()


def _section(icon, title, color=CYAN):
    print()
    cprint(f"  {icon}  {BOLD}{title}{RESET}", color)
    cprint("  " + "─" * 54, DIM)


def _item(n, title, meta=""):
    t = title[:68] + ("…" if len(title) > 68 else "")
    cprint(f"   {n}. {t}", WHITE)
    if meta:
        cprint(f"      {meta}", DIM)


def _wrap_print(text, indent="     ", width=65, color=DIM):
    """Word-wrap a paragraph and print it."""
    words = text.split()
    line  = indent
    for word in words:
        if len(line) + len(word) + 1 > width:
            cprint(line, color)
            line = indent + word + " "
        else:
            line += word + " "
    if line.strip():
        cprint(line, color)


def _time_greeting():
    h = datetime.now().hour
    if h < 12:
        return "Good morning"
    elif h < 17:
        return "Good afternoon"
    else:
        return "Good evening"


# ──────────────────────────────────────────────────────────
#  PROFESSIONAL INTELLIGENCE REPORT DISPLAY
# ──────────────────────────────────────────────────────────

def _display_report(report, watchlist=None):
    """
    Render the structured 5-section intelligence report in a professional format.
    `report` is a dict {section_name: text} as returned by ai_generate_report().
    """
    if not report:
        return

    wl        = watchlist or {}
    user_name = wl.get("user_name", "").strip()
    today     = datetime.now().strftime("%B %d, %Y")

    print()
    cprint("  " + "━" * 58, CYAN)
    header = f"  🧠  ALOA INTELLIGENCE REPORT"
    if user_name:
        header += f"  —  {user_name}"
    cprint(header, CYAN + BOLD)
    cprint(f"       {today}", DIM)
    cprint("  " + "━" * 58, CYAN)

    for section_key in REPORT_SECTIONS:
        content = report.get(section_key, "").strip()
        if not content:
            continue

        icon, label, color = SECTION_META.get(
            section_key, ("•", section_key, WHITE)
        )

        print()
        cprint(f"  {icon}  {BOLD}{label}{RESET}", color)
        print()

        if section_key == "SUGGESTIONS":
            # Try to split numbered suggestions onto separate lines
            # Handles "1. ... 2. ... 3. ..." run together
            import re
            parts = re.split(r'(?<=[.!?])\s+(?=\d+\.)', content)
            if len(parts) <= 1:
                parts = re.split(r'\s+(?=\d+\.)', content)
            for part in parts:
                part = part.strip()
                if part:
                    _wrap_print(part, indent="     ", width=65, color="")
                    print()
        else:
            _wrap_print(content, indent="     ", width=65, color="")

    print()
    cprint("  " + "━" * 58, CYAN)


# ──────────────────────────────────────────────────────────
#  BRIEF DISPLAY  (raw feed sections)
# ──────────────────────────────────────────────────────────

def display_brief(brief, watchlist=None):
    """Render the full Radar brief — feeds first, report last."""
    wl        = watchlist or {}
    user_name = wl.get("user_name", "").strip()

    print()
    cprint("  ╔══════════════════════════════════════════════════════════╗", CYAN)
    cprint(f"  ║  📡 ALOA RADAR — {brief.get('date', 'Today'):<42}║", CYAN)

    if user_name:
        greeting = f"{_time_greeting()}, {user_name}! Here's what's happening."
        cprint(f"  ║  {greeting:<58}║", DIM)

    if brief.get("from_cache"):
        ts = brief.get("cached_at", "")
        try:
            t = datetime.fromisoformat(ts).strftime("%I:%M %p")
            cprint(f"  ║  {'↻ Cached at ' + t + '  —  Press [R] to refresh':<58}║", DIM)
        except Exception:
            pass

    cprint("  ╚══════════════════════════════════════════════════════════╝", CYAN)

    # ── Hacker News ───────────────────────────────────────
    hn = brief.get("hackernews", [])
    if hn:
        _section("🔥", "HACKER NEWS", YELLOW)
        for i, s in enumerate(hn[:5], 1):
            _item(i, s["title"],
                  meta=f"⬆ {s['score']} pts  |  💬 {s['comments']} comments")

    # ── Company Radar ─────────────────────────────────────
    co_news = brief.get("company_news", [])
    if co_news:
        _section("🏢", "COMPANY RADAR", BLUE)
        by_company: dict = {}
        for item in co_news:
            by_company.setdefault(item["company"], []).append(item)
        n = 1
        for company, items in by_company.items():
            cprint(f"\n     ── {company} {'─' * max(0, 42 - len(company))}", YELLOW)
            for item in items[:2]:
                _item(n, item["title"])
                n += 1

    # ── GitHub Trending ───────────────────────────────────
    gh = brief.get("github", [])
    if gh:
        _section("🐙", "GITHUB TRENDING", GREEN)
        for i, r in enumerate(gh[:5], 1):
            stars = f"  ⭐ +{r['stars_today']} today" if r.get("stars_today") else ""
            _item(i, r["name"],
                  meta=f"{r.get('description', '')[:60]}{stars}")

    # ── Dev.to ────────────────────────────────────────────
    devto = brief.get("devto", [])
    if devto:
        _section("📰", "DEV.TO — FOR YOUR STACK", MAGENTA)
        for i, a in enumerate(devto[:5], 1):
            tag_label = f"[{a.get('tag', '')}]  " if a.get("tag") else ""
            _item(i, a["title"],
                  meta=f"{tag_label}by {a['author']}  |  ❤️  {a['reactions']}")

    # ── Reddit ────────────────────────────────────────────
    reddit = brief.get("reddit", [])
    if reddit:
        _section("👾", "REDDIT HOT", RED)
        for i, p in enumerate(reddit[:5], 1):
            _item(i, p["title"],
                  meta=f"r/{p['subreddit']}  |  ⬆ {p['score']}")

    # ── PyPI Tracker ──────────────────────────────────────
    pkgs = brief.get("packages", [])
    if pkgs:
        _section("📦", "PACKAGE TRACKER", BLUE)
        for i, pkg in enumerate(pkgs, 1):
            _item(i, pkg["package"],
                  meta=f"Latest: v{pkg['latest']}  →  {pkg['url']}")

    # ── AI Intelligence Report ────────────────────────────
    report = brief.get("report")
    if report:
        _display_report(report, watchlist=wl)

    print()
    cprint("  ──────────────────────────────────────────────────────", DIM)
    cprint(
        f"  [{GREEN}R{RESET}] Refresh   "
        f"[{YELLOW}W{RESET}] Edit Profile   "
        f"[{RED}0{RESET}] Back",
        ""
    )
    print()


# ──────────────────────────────────────────────────────────
#  RESUME SETUP  (optional step)
# ──────────────────────────────────────────────────────────

def _pick_pdf_file():
    """
    Open a native Windows file-picker dialog filtered to PDFs.
    Falls back to manual path input if tkinter is unavailable.
    Returns the selected path string, or "" if cancelled.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()          # hide the empty Tk root window
        root.attributes("-topmost", True)   # bring picker to front

        path = filedialog.askopenfilename(
            title="Select your Resume PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        root.destroy()
        return path or ""

    except Exception:
        # tkinter not available — ask manually
        cprint("  ℹ️  File picker unavailable. Enter path manually.", DIM)
        return safe_input("  ➤ Full path to PDF: ")


def _setup_resume(wl):
    """
    Optionally collect the user's resume.
    Asks whether to upload PDF, paste text, clear, or skip.
    Updates wl["resume_text"] in-place.
    """
    has_resume = bool(wl.get("resume_text", "").strip())
    print()
    cprint("  ── RESUME  (Optional — enhances AI suggestions) ──────", CYAN)
    print()

    if has_resume:
        chars = len(wl["resume_text"])
        cprint(f"  ✅ Resume on file: {chars} characters", GREEN)
    else:
        cprint("  ℹ️  No resume on file.", DIM)

    cprint("  [A] Upload from PDF path", "")
    cprint("  [B] Paste resume text", "")
    cprint("  [C] Clear existing resume", "")
    cprint("  [S] Skip", DIM)
    print()

    choice = safe_input("  ➤ Choice: ").strip().upper()

    if choice == "A":
        # Try to open native Windows file picker
        path = _pick_pdf_file()
        if not path:
            cprint("  ⚠️  No file selected. Skipped.", YELLOW)
            return wl
        if os.path.isfile(path):
            show_progress("  📄 Extracting resume from PDF", steps=4, delay=0.4)
            text = extract_pdf_text(path)
            if text:
                wl["resume_text"] = text
                cprint(f"\n  ✅ Extracted {len(text)} characters from: {os.path.basename(path)}", GREEN)
            else:
                cprint("\n  ❌ Could not extract text from PDF. Try pasting instead.", RED)
        else:
            cprint("  ⚠️  File not found. Skipped.", YELLOW)

    elif choice == "B":
        cprint("  Paste your resume text below.", DIM)
        cprint("  Type 'DONE' on a new line when finished.", DIM)
        print()
        lines = []
        while True:
            try:
                line = input("  ")
            except (EOFError, KeyboardInterrupt):
                break
            if line.strip().upper() == "DONE":
                break
            lines.append(line)
        text = "\n".join(lines).strip()
        if text:
            wl["resume_text"] = text[:5000]
            cprint(f"\n  ✅ Resume saved ({len(text)} chars).", GREEN)
        else:
            cprint("\n  ⚠️  Empty input. Skipped.", YELLOW)

    elif choice == "C":
        wl["resume_text"] = ""
        cprint("  🗑️  Resume cleared.", RED)

    # S or anything else → skip
    return wl


# ──────────────────────────────────────────────────────────
#  WATCHLIST / PROFILE SETUP FLOW
# ──────────────────────────────────────────────────────────

def setup_watchlist_flow(existing=None):
    """Full interactive profile setup."""
    wl = (existing or DEFAULT_WATCHLIST).copy()

    print()
    cprint("  ╔══════════════════════════════════════════════════════════╗", CYAN)
    cprint("  ║  ⚙️   RADAR PROFILE SETUP                                ║", CYAN)
    cprint("  ║  Your details power a fully personalized intel brief.   ║", CYAN)
    cprint("  ╚══════════════════════════════════════════════════════════╝", CYAN)
    print()
    cprint("  Press Enter to keep current value for any field.", DIM)
    print()

    def _ask(label, key, hint=""):
        cur = wl.get(key, "")
        if isinstance(cur, list):
            cur = ", ".join(cur)
        cprint(f"  {label}", BOLD + WHITE)
        if hint:
            cprint(f"      e.g.  {hint}", DIM)
        if cur:
            cprint(f"      Current: {cur}", DIM)
        return safe_input("  ➤ ")

    # ── Personal Info ─────────────────────────────────────
    cprint("  ── WHO YOU ARE ───────────────────────────────────────", CYAN)
    print()

    val = _ask("[1] Your Name", "user_name", "Priyanshu, Rahul, Ananya...")
    if val:
        wl["user_name"] = val
    print()

    val = _ask("[2] Your Role / Goal",
               "current_role",
               "CS Student, Python Developer, ML Engineer, Fresher...")
    if val:
        wl["current_role"] = val
    print()

    # ── Tech & Interests ──────────────────────────────────
    cprint("  ── YOUR TECH ─────────────────────────────────────────", CYAN)
    print()

    val = _ask("[3] Tech Stack",
               "tech_stack",
               "Python, React, FastAPI, Node.js, Java, ML...")
    if val:
        wl["tech_stack"] = [t.strip() for t in val.split(",") if t.strip()]
    print()

    val = _ask("[4] Watch Keywords",
               "keywords",
               "internship, hackathon, LLM, AI jobs, placement, salary...")
    if val:
        wl["keywords"] = [k.strip() for k in val.split(",") if k.strip()]
    print()

    # ── Company Tracker ───────────────────────────────────
    cprint("  ── COMPANIES TO WATCH ────────────────────────────────", CYAN)
    print()

    val = _ask("[5] Target Companies",
               "target_companies",
               "TCS, Infosys, Google, OpenAI, Wipro, Microsoft...")
    if val:
        wl["target_companies"] = [c.strip() for c in val.split(",") if c.strip()]
    print()

    # ── Sources ───────────────────────────────────────────
    cprint("  ── SOURCES ────────────────────────────────────────────", CYAN)
    print()

    val = _ask("[6] Subreddits",
               "subreddits",
               "Python, webdev, learnprogramming, cscareerquestions...")
    if val:
        wl["subreddits"] = [s.strip().lstrip("r/") for s in val.split(",") if s.strip()]
    print()

    val = _ask("[7] PyPI Packages to version-track",
               "packages",
               "fastapi, langchain, openai, numpy, requests...")
    if val:
        wl["packages"] = [p.strip().lower() for p in val.split(",") if p.strip()]
    print()

    # ── Optional Resume ───────────────────────────────────
    cprint("  ── RESUME (OPTIONAL) ─────────────────────────────────", CYAN)
    print()
    cprint("  Your resume lets ALOA give you career-specific suggestions.", DIM)
    cprint("  Stored locally on your machine only.", DIM)
    print()

    include = safe_input("  ➤ Set up resume now? [y/N]: ").lower()
    if include == "y":
        wl = _setup_resume(wl)

    save_watchlist(wl)
    print()
    cprint("  ✅ Profile saved! Your next brief will be fully personalized.", GREEN)
    return wl


# ──────────────────────────────────────────────────────────
#  FETCH + DISPLAY
# ──────────────────────────────────────────────────────────

def _fetch_and_show(watchlist, force_refresh=False):
    """Load from cache or fetch fresh, then display."""
    if not force_refresh:
        cached = load_cache()
        if cached:
            cached["from_cache"] = True
            display_brief(cached, watchlist=watchlist)
            _brief_actions(watchlist)
            return

    show_progress("  📡 Fetching your personalized intel brief")
    brief = build_brief(watchlist, force_refresh=force_refresh)

    empty = not any(brief.get(k) for k in
                    ("hackernews", "company_news", "devto", "github", "reddit"))
    if empty:
        print()
        cprint("  ❌ Could not reach any sources. Check your internet connection.", RED)
        return

    display_brief(brief, watchlist=watchlist)
    _brief_actions(watchlist)


def _brief_actions(watchlist):
    """Handle in-brief keystroke commands."""
    while True:
        choice = safe_input("  Action: ").strip().upper()
        if choice == "R":
            _fetch_and_show(watchlist, force_refresh=True)
            break
        elif choice == "W":
            print()
            new_wl = setup_watchlist_flow(watchlist)
            watchlist.update(new_wl)
            cprint("\n  ⚠️  Profile updated. Use [2] to refresh your brief.", YELLOW)
            break
        else:
            break


# ──────────────────────────────────────────────────────────
#  RESUME QUICK-UPDATE  (from main menu option)
# ──────────────────────────────────────────────────────────

def update_resume_flow(watchlist):
    """Standalone resume update without going through full watchlist setup."""
    print()
    cprint("  ╔══════════════════════════════════════════════════════════╗", CYAN)
    cprint("  ║  📄 UPDATE RESUME                                        ║", CYAN)
    cprint("  ╚══════════════════════════════════════════════════════════╝", CYAN)
    wl = _setup_resume(watchlist)
    save_watchlist(wl)
    watchlist.update(wl)
    cprint("\n  ⚠️  Resume updated. Use [2] to refresh your brief.", YELLOW)


# ──────────────────────────────────────────────────────────
#  MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────

def run():
    """Feature 10 — ALOA Radar entry point."""
    print()
    print("═" * 60)
    cprint("        📡  ALOA RADAR  —  Your Daily Intel Brief", CYAN + BOLD)
    print("═" * 60)

    watchlist = load_watchlist()

    if watchlist is None:
        print()
        cprint("  👋 First time here! Let's build your personal Radar profile.", YELLOW)
        cprint("  It only takes 2 minutes.", DIM)
        watchlist = setup_watchlist_flow()

    name_label = watchlist.get("user_name", "")
    has_resume = bool(watchlist.get("resume_text", "").strip())

    if name_label:
        print()
        cprint(f"  {_time_greeting()}, {name_label}.", CYAN)
        if has_resume:
            cprint("  📄 Resume on file — AI suggestions are fully personalized.", DIM)
        else:
            cprint("  💡 Tip: Upload your resume via [4] for smarter suggestions.", DIM)

    while True:
        print()
        cprint("  ─────────────────────────────────────────────────────", DIM)
        cprint(f"  [{GREEN}1{RESET}] 📡 View Today's Brief", "")
        cprint(f"  [{CYAN}2{RESET}] 🔄 Force Refresh  (ignore cache)", "")
        cprint(f"  [{YELLOW}3{RESET}] ⚙️  Edit Profile & Watchlist", "")
        cprint(f"  [{MAGENTA}4{RESET}] 📄 Update Resume", "")
        cprint(f"  [{RED}0{RESET}] ←  Back to Main Menu", "")
        print()

        choice = safe_input().upper()

        if choice == "1":
            _fetch_and_show(watchlist, force_refresh=False)
        elif choice == "2":
            _fetch_and_show(watchlist, force_refresh=True)
        elif choice == "3":
            watchlist = setup_watchlist_flow(watchlist)
            cprint("\n  ⚠️  Profile updated. Use [2] to refresh.", YELLOW)
        elif choice == "4":
            update_resume_flow(watchlist)
        elif choice == "0":
            break
        else:
            cprint("  ⚠️  Invalid choice.", YELLOW)
