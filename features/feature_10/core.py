"""
╔══════════════════════════════════════════════════════════════════╗
║  ALOA RADAR — Feature 10 Core Engine (v3.0)                     ║
║  Sources: HN · Dev.to · GitHub · Reddit · PyPI · Company News   ║
║  Intel: Resume-aware · 5-section Professional AI Report         ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import date, datetime

try:
    from bs4 import BeautifulSoup  # type: ignore[import]
    BS4_AVAILABLE = True
except ImportError:
    BeautifulSoup = None  # type: ignore[assignment,misc]
    BS4_AVAILABLE = False

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

FEATURE_DIR    = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR      = os.path.join(FEATURE_DIR, "cache")
ALOA_ROOT      = os.path.dirname(os.path.dirname(FEATURE_DIR))
WATCHLIST_PATH = os.path.join(ALOA_ROOT, "radar_watchlist.json")

DEFAULT_WATCHLIST = {
    "user_name":        "",
    "current_role":     "",
    "target_companies": [],
    "tech_stack":       ["Python", "JavaScript"],
    "keywords":         [],
    "subreddits":       ["programming", "Python", "webdev"],
    "packages":         [],
    "resume_text":      "",     # optional — enhances AI report quality
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

REDDIT_HEADERS = {
    "User-Agent": "ALOA-Radar/3.0 (personal developer intel brief)"
}

# Report section keys — must match exactly what we ask the AI to output
REPORT_SECTIONS = [
    "CURRENT AFFAIRS",
    "TECH NEWS",
    "TRENDING TECH",
    "GENERAL KNOWLEDGE",
    "SUGGESTIONS",
]


# ──────────────────────────────────────────────────────────
#  UTILITIES
# ──────────────────────────────────────────────────────────

def strip_markdown(text):
    """Remove markdown formatting so AI output renders cleanly in terminal."""
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*',     r'\1', text)
    text = re.sub(r'#{1,6}\s*',       '',    text)
    text = re.sub(r'`([^`]+)`',       r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text.strip()


def _to_devto_tag(name):
    """Normalize a tech name to a Dev.to-compatible tag."""
    return re.sub(r'[\s\-\.]+', '', name.lower())


def extract_pdf_text(path, max_chars=4000):
    """Extract text from a PDF file (up to max_chars). Returns empty string on failure."""
    try:
        import PyPDF2
        text = ""
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages[:6]:
                text += (page.extract_text() or "")
                if len(text) >= max_chars:
                    break
        return text[:max_chars].strip()
    except Exception:
        return ""


# ──────────────────────────────────────────────────────────
#  WATCHLIST
# ──────────────────────────────────────────────────────────

def load_watchlist():
    if os.path.exists(WATCHLIST_PATH):
        try:
            with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in DEFAULT_WATCHLIST.items():
                data.setdefault(k, v)
            return data
        except Exception:
            pass
    return None


def save_watchlist(data):
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────────────────
#  CACHE  (one file per calendar day)
# ──────────────────────────────────────────────────────────

def _cache_path():
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"brief_{date.today().strftime('%Y%m%d')}.json")


def load_cache():
    p = _cache_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_cache(data):
    data["cached_at"] = datetime.now().isoformat()
    with open(_cache_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────────────────
#  HTTP HELPER
# ──────────────────────────────────────────────────────────

def _get(url, timeout=12, hdrs=None, **kwargs):
    try:
        r = requests.get(url, timeout=timeout, headers=hdrs or HEADERS, **kwargs)
        r.raise_for_status()
        return r
    except Exception:
        return None


# ──────────────────────────────────────────────────────────
#  SOURCE: HACKER NEWS
# ──────────────────────────────────────────────────────────

def fetch_hackernews(keywords=None, limit=5):
    """Top HN stories — keyword matches first, top stories as fill."""
    r = _get("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not r:
        return []

    ids  = r.json()[:50]
    kws  = [k.lower() for k in (keywords or [])]
    hits, fallback = [], []

    for sid in ids:
        if len(hits) >= limit and len(fallback) >= limit:
            break
        sr = _get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
        if not sr:
            continue
        item = sr.json()
        if not item or item.get("type") != "story":
            continue

        title = item.get("title", "")
        entry = {
            "title":    title,
            "url":      item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
            "score":    item.get("score", 0),
            "comments": item.get("descendants", 0),
        }
        (hits if (kws and any(kw in title.lower() for kw in kws)) else fallback).append(entry)

    return (hits + fallback)[:limit]


# ──────────────────────────────────────────────────────────
#  SOURCE: DEV.TO  (properly tag-normalized)
# ──────────────────────────────────────────────────────────

def fetch_devto(tags=None, limit=5):
    """Top Dev.to articles for the user's tech tags (properly normalized)."""
    articles, seen = [], set()

    for raw_tag in (tags or [])[:4]:
        tag = _to_devto_tag(raw_tag)
        if not tag:
            continue
        r = _get("https://dev.to/api/articles",
                 params={"tag": tag, "per_page": 8, "top": 7})
        if not r:
            continue
        for a in r.json():
            url = a.get("url", "")
            if url and url not in seen:
                seen.add(url)
                articles.append({
                    "title":     a.get("title", ""),
                    "url":       url,
                    "author":    a.get("user", {}).get("name", "unknown"),
                    "reactions": a.get("positive_reactions_count", 0),
                    "tag":       raw_tag,
                })
        if len(articles) >= limit:
            break

    articles.sort(key=lambda x: x["reactions"], reverse=True)
    return articles[:limit]


# ──────────────────────────────────────────────────────────
#  SOURCE: GITHUB TRENDING
# ──────────────────────────────────────────────────────────

def fetch_github_trending(limit=5):
    """Scrape GitHub Trending page. Requires beautifulsoup4."""
    repos = []
    if not BS4_AVAILABLE:
        return repos
    r = _get("https://github.com/trending")
    if not r:
        return repos

    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.find_all("article", class_="Box-row")[:limit]:
        try:
            h2   = card.find("h2")
            link = h2.find("a") if h2 else None
            if not link:
                continue
            path    = link.get("href", "").strip("/")
            desc_el = card.find("p")
            desc    = desc_el.get_text(strip=True) if desc_el else ""

            stars_today = ""
            for span in card.find_all("span"):
                txt = span.get_text(strip=True)
                if "stars today" in txt:
                    stars_today = txt.replace("stars today", "").strip()
                    break

            repos.append({
                "name":        path.replace("/", " / "),
                "url":         f"https://github.com/{path}",
                "description": desc[:100],
                "stars_today": stars_today,
            })
        except Exception:
            continue

    return repos


# ──────────────────────────────────────────────────────────
#  SOURCE: REDDIT
# ──────────────────────────────────────────────────────────

def fetch_reddit(subreddits=None, limit=5):
    """Hot non-stickied posts via Reddit's public JSON API."""
    posts = []
    for sub in (subreddits or ["programming"])[:3]:
        r = _get(f"https://www.reddit.com/r/{sub}/hot.json",
                 params={"limit": 8}, hdrs=REDDIT_HEADERS)
        if r:
            try:
                for child in r.json()["data"]["children"]:
                    post = child["data"]
                    if post.get("stickied"):
                        continue
                    posts.append({
                        "title":     post.get("title", ""),
                        "url":       f"https://reddit.com{post.get('permalink', '')}",
                        "score":     post.get("score", 0),
                        "subreddit": sub,
                    })
            except Exception:
                pass
        time.sleep(0.5)

    posts.sort(key=lambda x: x["score"], reverse=True)
    return posts[:limit]


# ──────────────────────────────────────────────────────────
#  SOURCE: COMPANY NEWS  (Google News RSS — no auth)
# ──────────────────────────────────────────────────────────

def fetch_company_news(companies, limit_per=2):
    """Fetch recent headlines for each target company via Google News RSS."""
    all_news = []
    for company in companies[:5]:
        query = requests.utils.quote(f'"{company}"')
        url   = (f"https://news.google.com/rss/search"
                 f"?q={query}&hl=en-IN&gl=IN&ceid=IN:en")
        r = _get(url, timeout=12)
        if not r:
            continue
        try:
            root, count = ET.fromstring(r.content), 0
            for item in root.findall(".//item"):
                if count >= limit_per:
                    break
                title = item.findtext("title", "").strip()
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0].strip()
                link = item.findtext("link", "")
                if title:
                    all_news.append({"company": company, "title": title, "url": link})
                    count += 1
        except ET.ParseError:
            pass

    return all_news


# ──────────────────────────────────────────────────────────
#  SOURCE: PYPI VERSION TRACKER
# ──────────────────────────────────────────────────────────

def fetch_pypi_updates(packages):
    """Latest released version for each tracked PyPI package."""
    updates = []
    for pkg in packages:
        r = _get(f"https://pypi.org/pypi/{pkg}/json")
        if r:
            try:
                info = r.json()["info"]
                updates.append({
                    "package": pkg,
                    "latest":  info["version"],
                    "url":     f"https://pypi.org/project/{pkg}/",
                })
            except Exception:
                pass
    return updates


# ──────────────────────────────────────────────────────────
#  AI INTELLIGENCE REPORT  (Groq — structured 5-section report)
# ──────────────────────────────────────────────────────────

def _parse_report(text):
    """
    Parse the AI's bracketed-section output into a dict.
    E.g. [CURRENT AFFAIRS] ... [TECH NEWS] ... → {"CURRENT AFFAIRS": "...", ...}
    """
    result  = {}
    pattern = r'\[(' + '|'.join(re.escape(s) for s in REPORT_SECTIONS) + r'\])(.*?)(?=\[(?:' \
              + '|'.join(re.escape(s) for s in REPORT_SECTIONS) + r')\]|$)'
    # Slightly simpler but robust approach:
    parts   = re.split(r'\[(' + '|'.join(re.escape(s) for s in REPORT_SECTIONS) + r')\]', text)
    # parts alternates: [pre, key1, body1, key2, body2, ...]
    i = 1
    while i < len(parts) - 1:
        key  = parts[i].strip()
        body = strip_markdown(parts[i + 1]).strip()
        if key and body:
            result[key] = body
        i += 2
    return result


def ai_generate_report(watchlist, brief):
    """
    Generate a professional 5-section intelligence report using Groq.
    Optionally uses the user's resume for highly targeted suggestions.
    Returns a dict {section_name: content} or None on failure.
    """
    if not GROQ_API_KEY:
        return None

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        name      = watchlist.get("user_name", "")      or "the developer"
        role      = watchlist.get("current_role", "")   or "developer"
        stack     = ", ".join(watchlist.get("tech_stack",       [])) or "general tech"
        companies = ", ".join(watchlist.get("target_companies", [])) or "not specified"
        resume    = watchlist.get("resume_text", "").strip()

        hn      = "; ".join(s["title"] for s in brief.get("hackernews",   [])[:5]) or "none"
        co_news = "; ".join(f"{n['company']}: {n['title']}"
                            for n in brief.get("company_news", [])[:4]) or "none"
        gh      = "; ".join(f"{r['name']}: {r['description']}"
                            for r in brief.get("github",       [])[:3]) or "none"
        devto   = "; ".join(a["title"] for a in brief.get("devto",       [])[:4]) or "none"
        reddit  = "; ".join(p["title"] for p in brief.get("reddit",      [])[:3]) or "none"
        pkgs    = "; ".join(f"{p['package']} v{p['latest']}"
                            for p in brief.get("packages",     [])) or "none"

        resume_block = (
            f"\n\nRESUME / PROFILE SUMMARY:\n{resume[:2500]}"
            if resume else ""
        )

        prompt = f"""You are ALOA, a professional intelligence analyst for developers.

DEVELOPER PROFILE:
Name            : {name}
Role            : {role}
Tech Stack      : {stack}
Target Companies: {companies}{resume_block}

TODAY'S FETCHED DATA:
Hacker News     : {hn}
Company News    : {co_news}
GitHub Trending : {gh}
Dev.to Articles : {devto}
Reddit Hot      : {reddit}
Package Updates : {pkgs}

Generate a professional intelligence brief for {name}.
Use EXACTLY these section markers in this exact order.
Write each section as flowing prose — no bullets in the first 4 sections.
SUGGESTIONS may use numbered lines (1. 2. 3.).

[CURRENT AFFAIRS]
2-3 sentences on the most important global tech/business news today.

[TECH NEWS]
2-3 sentences on news most directly relevant to this person's stack and target companies.

[TRENDING TECH]
2 sentences on what is rising fastest in the tech world right now based on GitHub and Dev.to data.

[GENERAL KNOWLEDGE]
1-2 sentences — one interesting, share-worthy insight from today's data that broadens perspective.

[SUGGESTIONS]
3 specific, actionable suggestions tailored to {name}'s profile, stack, resume, and today's news.
Format: 1. <suggestion>  2. <suggestion>  3. <suggestion>

ABSOLUTE RULES:
- Plain text only. Zero markdown. No asterisks. No bold or italics. No colons after labels.
- Each section under 70 words.
- Do not repeat section header names in the body text."""

        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.6,
        )
        raw    = resp.choices[0].message.content.strip()
        parsed = _parse_report(raw)
        return parsed if parsed else {"RAW": strip_markdown(raw)}

    except Exception:
        return None


# ──────────────────────────────────────────────────────────
#  MAIN BUILD FUNCTION
# ──────────────────────────────────────────────────────────

def build_brief(watchlist, force_refresh=False):
    """
    Build the full Radar brief.
    Uses today's cache unless force_refresh=True.
    """
    if not force_refresh:
        cached = load_cache()
        if cached:
            cached["from_cache"] = True
            return cached

    stack      = watchlist.get("tech_stack",       [])
    keywords   = watchlist.get("keywords",          [])
    subreddits = watchlist.get("subreddits",        ["programming"])
    packages   = watchlist.get("packages",          [])
    companies  = watchlist.get("target_companies",  [])

    brief = {
        "date":         date.today().strftime("%B %d, %Y"),
        "hackernews":   fetch_hackernews(keywords=stack + keywords, limit=5),
        "company_news": fetch_company_news(companies, limit_per=2),
        "github":       fetch_github_trending(limit=5),
        "devto":        fetch_devto(tags=stack, limit=5),
        "reddit":       fetch_reddit(subreddits=subreddits, limit=5),
        "packages":     fetch_pypi_updates(packages),
        "report":       None,
        "from_cache":   False,
    }

    brief["report"] = ai_generate_report(watchlist, brief)
    save_cache(brief)
    return brief
