"""
╔══════════════════════════════════════════════════════════════════╗
║  ALOA RESUME ENGINE — HTML Templates (v1.0)                     ║
║  3 Industry-Grade Resume Templates                               ║
║  1. ATS Classic (Tech/FAANG)                                     ║
║  2. Modern Professional (Corporate)                              ║
║  3. Creative Two-Column (Marketing/Design)                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import html as html_mod


def _esc(text):
    """Escape HTML special characters."""
    if not text:
        return ""
    return html_mod.escape(str(text))


def _build_bullets_html(bullets):
    """Build an HTML <ul> from a list of bullet strings."""
    if not bullets:
        return ""
    items = "\n".join(f"            <li>{_esc(b)}</li>" for b in bullets if b)
    return f"          <ul>\n{items}\n          </ul>"


def _skills_by_category(skills):
    """Group skills into categories. Returns dict of category -> list of skill dicts."""
    groups = {}
    for s in skills:
        cat = s.get("category", "Other") or "Other"
        groups.setdefault(cat, []).append(s)
    return groups


# ══════════════════════════════════════════════════════════════
# TEMPLATE 1: ATS CLASSIC — Single Column, Dense, FAANG-Ready
# ══════════════════════════════════════════════════════════════

def render_ats_classic(profile):
    """
    Render a clean, ATS-optimized single-column resume.
    Inspired by the classic LaTeX / Jake's Resume format.
    Optimized for Workday, Greenhouse, Lever ATS systems.
    """
    p = profile.get("personal", {})
    sections = []

    # ── Contact Line ──
    contact_parts = []
    if p.get("phone"):
        contact_parts.append(f'📞 {_esc(p["phone"])}')
    if p.get("email"):
        contact_parts.append(f'✉ <a href="mailto:{_esc(p["email"])}">{_esc(p["email"])}</a>')
    if p.get("linkedin"):
        ln = p["linkedin"]
        url = ln if ln.startswith("http") else f"https://linkedin.com/in/{ln}"
        contact_parts.append(f'🔗 <a href="{_esc(url)}">LinkedIn</a>')
    if p.get("github"):
        gh = p["github"]
        url = gh if gh.startswith("http") else f"https://github.com/{gh}"
        contact_parts.append(f'💻 <a href="{_esc(url)}">GitHub</a>')
    if p.get("portfolio"):
        pf = p["portfolio"]
        url = pf if pf.startswith("http") else f"https://{pf}"
        contact_parts.append(f'🌐 <a href="{_esc(url)}">Portfolio</a>')
    contact_line = " &nbsp;|&nbsp; ".join(contact_parts)
    location_line = f'<div class="location">{_esc(p.get("location", ""))}</div>' if p.get("location") else ""

    # ── Summary ──
    summary = profile.get("summary", "")
    if summary:
        sections.append(f"""
      <div class="section">
        <h2>Profile Summary</h2>
        <p class="summary-text">{_esc(summary)}</p>
      </div>""")

    # ── Skills ──
    skills = profile.get("skills", [])
    if skills:
        groups = _skills_by_category(skills)
        skill_lines = []
        for cat, items in groups.items():
            names = ", ".join(_esc(s["name"]) for s in items)
            skill_lines.append(f'<span class="skill-category"><strong>{_esc(cat)}:</strong> {names}</span>')
        skills_html = "\n".join(skill_lines)
        sections.append(f"""
      <div class="section">
        <h2>Technical Skills</h2>
        <div class="skills-block">{skills_html}</div>
      </div>""")

    # ── Experience ──
    experience = profile.get("experience", [])
    if experience:
        exp_items = []
        for exp in experience:
            bullets = _build_bullets_html(exp.get("bullets", []))
            title_company = f'<strong>{_esc(exp.get("company", ""))}</strong> — {_esc(exp.get("title", ""))}'
            location = _esc(exp.get("location", ""))
            dates = f'{_esc(exp.get("start_date", ""))} – {_esc(exp.get("end_date", ""))}'
            exp_items.append(f"""
        <div class="entry">
          <div class="entry-header">
            <span class="entry-title">{title_company}</span>
            <span class="entry-date">{dates}</span>
          </div>
          <div class="entry-sub">
            <span>{location}</span>
          </div>
{bullets}
        </div>""")
        sections.append(f"""
      <div class="section">
        <h2>Experience</h2>
        {"".join(exp_items)}
      </div>""")

    # ── Projects ──
    projects = profile.get("projects", [])
    if projects:
        proj_items = []
        for proj in projects:
            techs = ", ".join(_esc(t) for t in proj.get("technologies", []))
            tech_str = f' | <em>{techs}</em>' if techs else ""
            link_str = ""
            if proj.get("link"):
                link_str = f' | <a href="{_esc(proj["link"])}">Link ↗</a>'
            bullets = _build_bullets_html(proj.get("bullets", []))
            date_str = _esc(proj.get("date", ""))
            proj_items.append(f"""
        <div class="entry">
          <div class="entry-header">
            <span class="entry-title"><strong>{_esc(proj.get("name", ""))}</strong>{tech_str}{link_str}</span>
            <span class="entry-date">{date_str}</span>
          </div>
{bullets}
        </div>""")
        sections.append(f"""
      <div class="section">
        <h2>Projects</h2>
        {"".join(proj_items)}
      </div>""")

    # ── Education ──
    education = profile.get("education", [])
    if education:
        edu_items = []
        for edu in education:
            degree = f'{_esc(edu.get("degree", ""))} — {_esc(edu.get("field", ""))}'.strip(" —")
            gpa_str = f' — CGPA: {_esc(edu.get("gpa", ""))}' if edu.get("gpa") else ""
            dates = f'{_esc(edu.get("start_date", ""))} – {_esc(edu.get("end_date", ""))}'
            location = _esc(edu.get("location", ""))
            coursework = edu.get("coursework", [])
            cw_str = ""
            if coursework:
                cw_str = f'<div class="coursework"><strong>Relevant Coursework:</strong> {", ".join(_esc(c) for c in coursework)}</div>'
            edu_items.append(f"""
        <div class="entry">
          <div class="entry-header">
            <span class="entry-title"><strong>{_esc(edu.get("institution", ""))}</strong>{gpa_str}</span>
            <span class="entry-date">{dates}</span>
          </div>
          <div class="entry-sub">
            <span>{degree}</span>
            <span>{location}</span>
          </div>
          {cw_str}
        </div>""")
        sections.append(f"""
      <div class="section">
        <h2>Education</h2>
        {"".join(edu_items)}
      </div>""")

    # ── Certifications ──
    certs = profile.get("certifications", [])
    if certs:
        cert_items = []
        for c in certs:
            link_str = ""
            if c.get("link"):
                link_str = f' — <a href="{_esc(c["link"])}">View Credential</a>'
            cert_items.append(f'<li>{_esc(c.get("name", ""))}: {_esc(c.get("issuer", ""))}{link_str}</li>')
        sections.append(f"""
      <div class="section">
        <h2>Certifications</h2>
        <ul>{"".join(cert_items)}</ul>
      </div>""")

    # ── Achievements ──
    achievements = profile.get("achievements", [])
    if achievements:
        items = "\n".join(f"          <li>{_esc(a)}</li>" for a in achievements)
        sections.append(f"""
      <div class="section">
        <h2>Achievements</h2>
        <ul>{items}</ul>
      </div>""")

    # ── Strengths ──
    strengths = profile.get("strengths", [])
    if strengths:
        items = "\n".join(f"          <li>{_esc(s)}</li>" for s in strengths)
        sections.append(f"""
      <div class="section">
        <h2>Strengths</h2>
        <ul>{items}</ul>
      </div>""")

    body_content = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_esc(p.get('full_name', 'Resume'))} — Resume</title>
    <link href="https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;0,700;1,400&family=Source+Sans+Pro:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        @page {{ margin: 0.45in 0.55in; size: A4; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Source Sans Pro', 'Segoe UI', 'Calibri', sans-serif;
            font-size: 10pt;
            line-height: 1.35;
            color: #1a1a1a;
            padding: 28px 42px;
            max-width: 850px;
            margin: 0 auto;
            background: #fff;
        }}
        h1 {{
            font-family: 'Crimson Text', 'Georgia', serif;
            font-size: 26pt;
            font-weight: 700;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-bottom: 2px;
            color: #111;
        }}
        .location {{
            text-align: center;
            font-size: 9.5pt;
            color: #444;
            margin-bottom: 2px;
        }}
        .contact-line {{
            text-align: center;
            font-size: 9pt;
            color: #333;
            margin-bottom: 10px;
            word-spacing: 1px;
        }}
        .contact-line a {{ color: #0056b3; text-decoration: none; }}
        .contact-line a:hover {{ text-decoration: underline; }}

        .section {{ margin-bottom: 8px; }}
        .section h2 {{
            font-size: 11pt;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            border-bottom: 1.8px solid #111;
            padding-bottom: 2px;
            margin-bottom: 5px;
            color: #111;
        }}

        .summary-text {{
            font-size: 9.5pt;
            color: #333;
            line-height: 1.4;
            margin-bottom: 4px;
        }}

        .skills-block {{
            font-size: 9.5pt;
            line-height: 1.4;
        }}
        .skill-category {{ display: block; margin-bottom: 0px; line-height: 1.45; }}

        .entry {{ margin-bottom: 7px; }}
        .entry-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
        }}
        .entry-title {{ font-size: 10pt; }}
        .entry-date {{
            font-size: 9pt;
            color: #444;
            white-space: nowrap;
            font-weight: 600;
        }}
        .entry-sub {{
            display: flex;
            justify-content: space-between;
            font-size: 9pt;
            color: #555;
            font-style: italic;
            margin-bottom: 2px;
        }}
        .coursework {{
            font-size: 9pt;
            color: #444;
            margin-top: 2px;
        }}

        ul {{
            margin: 2px 0 3px 18px;
            padding: 0;
        }}
        li {{
            font-size: 9.5pt;
            margin-bottom: 1px;
            line-height: 1.35;
        }}

        a {{ color: #0056b3; }}

        @media print {{
            body {{ padding: 0; margin: 0; }}
        }}
    </style>
</head>
<body>
    <header>
      <h1>{_esc(p.get('full_name', ''))}</h1>
      {location_line}
      <div class="contact-line">{contact_line}</div>
    </header>
    {body_content}
</body>
</html>"""


# ══════════════════════════════════════════════════════════════
# TEMPLATE 2: MODERN PROFESSIONAL — Corporate, Colored Header
# ══════════════════════════════════════════════════════════════

def render_modern_professional(profile):
    """
    Render a modern professional resume with colored header band,
    timeline-style experience, and accent colors.
    Inspired by Deloitte/McKinsey corporate resume formats.
    """
    p = profile.get("personal", {})

    # ── Contact icons ──
    contact_items = []
    if p.get("phone"):
        contact_items.append(f'<span class="contact-item">📞 {_esc(p["phone"])}</span>')
    if p.get("email"):
        contact_items.append(f'<span class="contact-item">✉️ <a href="mailto:{_esc(p["email"])}">{_esc(p["email"])}</a></span>')
    if p.get("location"):
        contact_items.append(f'<span class="contact-item">📍 {_esc(p["location"])}</span>')
    if p.get("linkedin"):
        ln = p["linkedin"]
        url = ln if ln.startswith("http") else f"https://linkedin.com/in/{ln}"
        contact_items.append(f'<span class="contact-item">🔗 <a href="{_esc(url)}">LinkedIn</a></span>')
    if p.get("github"):
        gh = p["github"]
        url = gh if gh.startswith("http") else f"https://github.com/{gh}"
        contact_items.append(f'<span class="contact-item">💻 <a href="{_esc(url)}">GitHub</a></span>')
    contact_html = "  ".join(contact_items)

    sections = []

    # ── Summary ──
    summary = profile.get("summary", "")
    if summary:
        sections.append(f"""
    <div class="section">
      <h2><span class="section-icon">👤</span> Professional Summary</h2>
      <p class="summary">{_esc(summary)}</p>
    </div>""")

    # ── Skills ──
    skills = profile.get("skills", [])
    if skills:
        groups = _skills_by_category(skills)
        skill_html_parts = []
        for cat, items in groups.items():
            tags = " ".join(f'<span class="skill-tag">{_esc(s["name"])}</span>' for s in items)
            skill_html_parts.append(f'<div class="skill-group"><strong>{_esc(cat)}</strong><div class="skill-tags">{tags}</div></div>')
        sections.append(f"""
    <div class="section">
      <h2><span class="section-icon">⚡</span> Skills</h2>
      {"".join(skill_html_parts)}
    </div>""")

    # ── Experience (with timeline) ──
    experience = profile.get("experience", [])
    if experience:
        exp_items = []
        for exp in experience:
            bullets = _build_bullets_html(exp.get("bullets", []))
            exp_items.append(f"""
        <div class="timeline-item">
          <div class="timeline-dot"></div>
          <div class="timeline-content">
            <div class="entry-header">
              <span class="job-title">{_esc(exp.get("title", ""))}</span>
              <span class="job-date">{_esc(exp.get("start_date", ""))} – {_esc(exp.get("end_date", ""))}</span>
            </div>
            <div class="job-company">{_esc(exp.get("company", ""))} {("· " + _esc(exp.get("location", ""))) if exp.get("location") else ""}</div>
{bullets}
          </div>
        </div>""")
        sections.append(f"""
    <div class="section">
      <h2><span class="section-icon">💼</span> Employment History</h2>
      <div class="timeline">
        {"".join(exp_items)}
      </div>
    </div>""")

    # ── Education ──
    education = profile.get("education", [])
    if education:
        edu_items = []
        for edu in education:
            gpa = f' — GPA: {_esc(edu.get("gpa", ""))}' if edu.get("gpa") else ""
            coursework = edu.get("coursework", [])
            cw = ""
            if coursework:
                cw = f'<div class="coursework"><em>Coursework:</em> {", ".join(_esc(c) for c in coursework)}</div>'
            edu_items.append(f"""
        <div class="edu-item">
          <div class="entry-header">
            <span><strong>{_esc(edu.get("institution", ""))}</strong></span>
            <span class="job-date">{_esc(edu.get("start_date", ""))} – {_esc(edu.get("end_date", ""))}</span>
          </div>
          <div class="edu-degree">{_esc(edu.get("degree", ""))} — {_esc(edu.get("field", ""))}{gpa}</div>
          <div class="edu-location">{_esc(edu.get("location", ""))}</div>
          {cw}
        </div>""")
        sections.append(f"""
    <div class="section">
      <h2><span class="section-icon">🎓</span> Education</h2>
      {"".join(edu_items)}
    </div>""")

    # ── Projects ──
    projects = profile.get("projects", [])
    if projects:
        proj_items = []
        for proj in projects:
            techs = ", ".join(_esc(t) for t in proj.get("technologies", []))
            link = ""
            if proj.get("link"):
                link = f' <a href="{_esc(proj["link"])}" class="proj-link">↗</a>'
            bullets = _build_bullets_html(proj.get("bullets", []))
            proj_items.append(f"""
        <div class="proj-item">
          <div class="entry-header">
            <span><strong>{_esc(proj.get("name", ""))}</strong>{link}</span>
            <span class="job-date">{_esc(proj.get("date", ""))}</span>
          </div>
          <div class="proj-tech">{techs}</div>
{bullets}
        </div>""")
        sections.append(f"""
    <div class="section">
      <h2><span class="section-icon">🚀</span> Projects</h2>
      {"".join(proj_items)}
    </div>""")

    # ── Certifications ──
    certs = profile.get("certifications", [])
    if certs:
        cert_items = []
        for c in certs:
            link = ""
            if c.get("link"):
                link = f' — <a href="{_esc(c["link"])}">View</a>'
            cert_items.append(f'<li><strong>{_esc(c.get("name", ""))}</strong> · {_esc(c.get("issuer", ""))}{link}</li>')
        sections.append(f"""
    <div class="section">
      <h2><span class="section-icon">📜</span> Certifications</h2>
      <ul>{"".join(cert_items)}</ul>
    </div>""")

    # ── Achievements ──
    achievements = profile.get("achievements", [])
    if achievements:
        items = "\n".join(f"        <li>{_esc(a)}</li>" for a in achievements)
        sections.append(f"""
    <div class="section">
      <h2><span class="section-icon">🏆</span> Achievements</h2>
      <ul>{items}</ul>
    </div>""")

    # ── Strengths ──
    strengths = profile.get("strengths", [])
    if strengths:
        items = "\n".join(f"        <li>{_esc(s)}</li>" for s in strengths)
        sections.append(f"""
    <div class="section">
      <h2><span class="section-icon">💪</span> Strengths</h2>
      <ul>{items}</ul>
    </div>""")

    body = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_esc(p.get('full_name', 'Resume'))} — Resume</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Playfair+Display:wght@700;800&display=swap" rel="stylesheet">
    <style>
        @page {{ margin: 0; size: A4; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            color: #222;
            background: #fff;
            max-width: 850px;
            margin: 0 auto;
        }}

        /* ── HEADER ── */
        .header {{
            background: linear-gradient(135deg, #0f4c75 0%, #1b6ca8 50%, #3282b8 100%);
            color: #fff;
            padding: 32px 44px 24px;
            position: relative;
        }}
        .header::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #f9a826, #f76c6c, #a8e6cf, #3282b8);
        }}
        .header h1 {{
            font-family: 'Playfair Display', 'Georgia', serif;
            font-size: 30pt;
            font-weight: 800;
            margin-bottom: 2px;
            letter-spacing: 1px;
        }}
        .header .title {{
            font-size: 13pt;
            font-weight: 300;
            opacity: 0.9;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }}
        .header .contacts {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px 20px;
            font-size: 9pt;
        }}
        .contact-item a {{ color: #bbe1fa; text-decoration: none; }}
        .contact-item a:hover {{ text-decoration: underline; }}

        /* ── BODY ── */
        .body-content {{ padding: 18px 44px 30px; }}

        .section {{ margin-bottom: 14px; }}
        .section h2 {{
            font-size: 12pt;
            font-weight: 700;
            color: #0f4c75;
            text-transform: uppercase;
            letter-spacing: 2px;
            border-left: 4px solid #f9a826;
            padding-left: 10px;
            margin-bottom: 8px;
        }}
        .section-icon {{ margin-right: 4px; }}

        .summary {{
            font-size: 9.8pt;
            color: #444;
            line-height: 1.5;
            border-left: 3px solid #e8e8e8;
            padding-left: 12px;
            font-style: italic;
        }}

        /* ── SKILLS ── */
        .skill-group {{ margin-bottom: 6px; }}
        .skill-group strong {{ font-size: 9pt; color: #0f4c75; }}
        .skill-tags {{ display: flex; flex-wrap: wrap; gap: 5px; margin-top: 3px; }}
        .skill-tag {{
            background: #e8f4fd;
            color: #0f4c75;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 8.5pt;
            font-weight: 500;
            border: 1px solid #c8e1f3;
        }}

        /* ── TIMELINE ── */
        .timeline {{ position: relative; padding-left: 20px; }}
        .timeline::before {{
            content: '';
            position: absolute;
            left: 5px;
            top: 8px;
            bottom: 8px;
            width: 2px;
            background: #d0d0d0;
        }}
        .timeline-item {{
            position: relative;
            margin-bottom: 12px;
        }}
        .timeline-dot {{
            position: absolute;
            left: -19px;
            top: 6px;
            width: 10px;
            height: 10px;
            background: #f9a826;
            border-radius: 50%;
            border: 2px solid #fff;
            box-shadow: 0 0 0 2px #f9a826;
        }}
        .timeline-content {{ padding-left: 4px; }}

        .entry-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
        }}
        .job-title {{
            font-weight: 700;
            font-size: 10.5pt;
            color: #111;
        }}
        .job-date {{
            font-size: 9pt;
            color: #666;
            font-weight: 600;
            white-space: nowrap;
        }}
        .job-company {{
            font-size: 9.5pt;
            color: #0f4c75;
            font-weight: 500;
            margin-bottom: 3px;
        }}

        .edu-item {{ margin-bottom: 8px; }}
        .edu-degree {{ font-size: 9.5pt; color: #444; }}
        .edu-location {{ font-size: 9pt; color: #888; }}
        .coursework {{ font-size: 9pt; color: #666; margin-top: 2px; }}

        .proj-item {{ margin-bottom: 8px; }}
        .proj-tech {{ font-size: 8.5pt; color: #0f4c75; font-style: italic; margin-bottom: 2px; }}
        .proj-link {{ color: #f9a826; text-decoration: none; font-weight: 700; }}

        ul {{ margin: 3px 0 3px 18px; padding: 0; }}
        li {{ font-size: 9.5pt; margin-bottom: 2px; line-height: 1.35; }}

        a {{ color: #0f4c75; }}

        @media print {{
            .header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            body {{ margin: 0; }}
        }}
    </style>
</head>
<body>
    <div class="header">
      <h1>{_esc(p.get('full_name', ''))}</h1>
      <div class="title">{_esc(p.get('title', ''))}</div>
      <div class="contacts">{contact_html}</div>
    </div>
    <div class="body-content">
      {body}
    </div>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════
# TEMPLATE 3: CREATIVE TWO-COLUMN — Sidebar + Main Content
# ══════════════════════════════════════════════════════════════

def render_creative_twocolumn(profile):
    """
    Render a creative two-column resume with a dark sidebar
    and light main content area. Skills shown with visual bars.
    Ideal for marketing, design, and creative roles.
    """
    p = profile.get("personal", {})

    # ── SIDEBAR CONTENT ──
    sidebar_sections = []

    # Contact in sidebar
    contact_items = []
    if p.get("email"):
        contact_items.append(f'<div class="sidebar-contact-item">✉️ {_esc(p["email"])}</div>')
    if p.get("phone"):
        contact_items.append(f'<div class="sidebar-contact-item">📞 {_esc(p["phone"])}</div>')
    if p.get("location"):
        contact_items.append(f'<div class="sidebar-contact-item">📍 {_esc(p["location"])}</div>')
    if p.get("linkedin"):
        ln = p["linkedin"]
        url = ln if ln.startswith("http") else f"https://linkedin.com/in/{ln}"
        contact_items.append(f'<div class="sidebar-contact-item">🔗 <a href="{_esc(url)}">LinkedIn</a></div>')
    if p.get("github"):
        gh = p["github"]
        url = gh if gh.startswith("http") else f"https://github.com/{gh}"
        contact_items.append(f'<div class="sidebar-contact-item">💻 <a href="{_esc(url)}">GitHub</a></div>')
    if contact_items:
        sidebar_sections.append(f"""
        <div class="sidebar-section">
          <h3>Contact</h3>
          {"".join(contact_items)}
        </div>""")

    # Summary in sidebar
    summary = profile.get("summary", "")
    if summary:
        sidebar_sections.append(f"""
        <div class="sidebar-section">
          <h3>Profile</h3>
          <p class="sidebar-summary">{_esc(summary)}</p>
        </div>""")

    # Education in sidebar
    education = profile.get("education", [])
    if education:
        edu_items = []
        for edu in education:
            gpa = f'<div class="edu-gpa">GPA: {_esc(edu.get("gpa", ""))}</div>' if edu.get("gpa") else ""
            edu_items.append(f"""
          <div class="sidebar-edu-item">
            <div class="edu-degree-name">{_esc(edu.get("degree", ""))} ({_esc(edu.get("field", ""))})</div>
            <div class="edu-inst">{_esc(edu.get("institution", ""))}</div>
            <div class="edu-date">{_esc(edu.get("end_date", ""))}</div>
            {gpa}
          </div>""")
        sidebar_sections.append(f"""
        <div class="sidebar-section">
          <h3>Education</h3>
          {"".join(edu_items)}
        </div>""")

    # Skills with visual bars in sidebar
    skills = profile.get("skills", [])
    if skills:
        skill_items = []
        for s in skills:
            prof = s.get("proficiency", 75)
            filled = int(prof / 10)
            dots = "●" * filled + "○" * (10 - filled)
            skill_items.append(f"""
          <div class="skill-bar-item">
            <span class="skill-name-bar">{_esc(s["name"])}</span>
            <span class="skill-dots">{dots}</span>
          </div>""")
        sidebar_sections.append(f"""
        <div class="sidebar-section">
          <h3>Skills</h3>
          {"".join(skill_items)}
        </div>""")

    # Courses in sidebar
    courses = profile.get("courses", [])
    if courses:
        course_items = []
        for c in courses:
            course_items.append(f"""
          <div class="sidebar-course">
            <div class="course-name">{_esc(c.get("name", ""))}</div>
            <div class="course-provider">{_esc(c.get("provider", ""))}</div>
          </div>""")
        sidebar_sections.append(f"""
        <div class="sidebar-section">
          <h3>Courses</h3>
          {"".join(course_items)}
        </div>""")

    sidebar_content = "\n".join(sidebar_sections)

    # ── MAIN CONTENT ──
    main_sections = []

    # Experience
    experience = profile.get("experience", [])
    if experience:
        exp_items = []
        for exp in experience:
            bullets = _build_bullets_html(exp.get("bullets", []))
            exp_items.append(f"""
        <div class="main-entry">
          <div class="main-entry-header">
            <span class="main-entry-title">{_esc(exp.get("title", ""))}</span>
            <span class="main-entry-date">{_esc(exp.get("start_date", ""))} – {_esc(exp.get("end_date", ""))}</span>
          </div>
          <div class="main-entry-company">{_esc(exp.get("company", ""))}</div>
{bullets}
        </div>""")
        main_sections.append(f"""
      <div class="main-section">
        <h2>💼 Employment History</h2>
        {"".join(exp_items)}
      </div>""")

    # Projects
    projects = profile.get("projects", [])
    if projects:
        proj_items = []
        for proj in projects:
            techs = ", ".join(_esc(t) for t in proj.get("technologies", []))
            bullets = _build_bullets_html(proj.get("bullets", []))
            proj_items.append(f"""
        <div class="main-entry">
          <div class="main-entry-header">
            <span class="main-entry-title">{_esc(proj.get("name", ""))}</span>
            <span class="main-entry-date">{_esc(proj.get("date", ""))}</span>
          </div>
          <div class="main-entry-company">{techs}</div>
{bullets}
        </div>""")
        main_sections.append(f"""
      <div class="main-section">
        <h2>🚀 Projects</h2>
        {"".join(proj_items)}
      </div>""")

    # Certifications
    certs = profile.get("certifications", [])
    if certs:
        cert_items = "\n".join(
            f'        <li><strong>{_esc(c.get("name", ""))}</strong> — {_esc(c.get("issuer", ""))}</li>'
            for c in certs
        )
        main_sections.append(f"""
      <div class="main-section">
        <h2>📜 Certifications</h2>
        <ul>{cert_items}</ul>
      </div>""")

    # Achievements
    achievements = profile.get("achievements", [])
    if achievements:
        items = "\n".join(f"        <li>{_esc(a)}</li>" for a in achievements)
        main_sections.append(f"""
      <div class="main-section">
        <h2>🏆 Achievements</h2>
        <ul>{items}</ul>
      </div>""")

    # Strengths
    strengths = profile.get("strengths", [])
    if strengths:
        items = "\n".join(f"        <li>{_esc(s)}</li>" for s in strengths)
        main_sections.append(f"""
      <div class="main-section">
        <h2>💪 Strengths</h2>
        <ul>{items}</ul>
      </div>""")

    # Volunteer
    volunteer = profile.get("volunteer", [])
    if volunteer:
        vol_items = []
        for v in volunteer:
            bullets = _build_bullets_html(v.get("bullets", []))
            vol_items.append(f"""
        <div class="main-entry">
          <div class="main-entry-title">{_esc(v.get("role", ""))}</div>
          <div class="main-entry-company">{_esc(v.get("organization", ""))}</div>
{bullets}
        </div>""")
        main_sections.append(f"""
      <div class="main-section">
        <h2>🤝 Volunteer & Contributions</h2>
        {"".join(vol_items)}
      </div>""")

    main_content = "\n".join(main_sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_esc(p.get('full_name', 'Resume'))} — Resume</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&family=Open+Sans:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        @page {{ margin: 0; size: A4; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Open Sans', 'Segoe UI', sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            color: #222;
            background: #f0f0f0;
            display: flex;
            justify-content: center;
        }}

        .resume-container {{
            display: flex;
            width: 850px;
            min-height: 1120px;
            background: #fff;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}

        /* ── SIDEBAR ── */
        .sidebar {{
            width: 280px;
            min-width: 280px;
            background: linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: #e0e0e0;
            padding: 30px 22px;
        }}
        .sidebar-name {{
            font-family: 'Montserrat', sans-serif;
            font-size: 22pt;
            font-weight: 800;
            color: #fff;
            line-height: 1.15;
            margin-bottom: 4px;
        }}
        .sidebar-title {{
            font-size: 10pt;
            font-weight: 300;
            color: #f9a826;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 18px;
            padding-bottom: 14px;
            border-bottom: 2px solid rgba(249, 168, 38, 0.3);
        }}
        .sidebar-section {{ margin-bottom: 18px; }}
        .sidebar-section h3 {{
            font-family: 'Montserrat', sans-serif;
            font-size: 9pt;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #f9a826;
            margin-bottom: 8px;
            padding-bottom: 4px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .sidebar-contact-item {{
            font-size: 8.5pt;
            margin-bottom: 5px;
            word-break: break-all;
        }}
        .sidebar-contact-item a {{ color: #bbe1fa; text-decoration: none; }}
        .sidebar-summary {{
            font-size: 8.5pt;
            line-height: 1.5;
            color: #ccc;
            text-align: justify;
        }}

        .sidebar-edu-item {{ margin-bottom: 10px; }}
        .edu-degree-name {{ font-size: 9pt; font-weight: 600; color: #fff; }}
        .edu-inst {{ font-size: 8.5pt; color: #aaa; }}
        .edu-date {{ font-size: 8pt; color: #888; }}
        .edu-gpa {{ font-size: 8pt; color: #f9a826; }}

        .skill-bar-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 5px;
        }}
        .skill-name-bar {{ font-size: 8.5pt; color: #ddd; }}
        .skill-dots {{
            font-size: 8pt;
            letter-spacing: 1px;
            color: #f9a826;
        }}

        .sidebar-course {{ margin-bottom: 8px; }}
        .course-name {{ font-size: 8.5pt; font-weight: 600; color: #eee; }}
        .course-provider {{ font-size: 8pt; color: #999; }}

        /* ── MAIN CONTENT ── */
        .main {{
            flex: 1;
            padding: 30px 32px;
            background: #fff;
        }}

        .main-section {{ margin-bottom: 16px; }}
        .main-section h2 {{
            font-family: 'Montserrat', sans-serif;
            font-size: 12pt;
            font-weight: 700;
            color: #1a1a2e;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            padding-bottom: 5px;
            border-bottom: 2.5px solid #f9a826;
            margin-bottom: 10px;
        }}

        .main-entry {{ margin-bottom: 12px; }}
        .main-entry-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
        }}
        .main-entry-title {{
            font-weight: 700;
            font-size: 10.5pt;
            color: #111;
        }}
        .main-entry-date {{
            font-size: 8.5pt;
            color: #f9a826;
            font-weight: 600;
            white-space: nowrap;
        }}
        .main-entry-company {{
            font-size: 9pt;
            color: #0f3460;
            font-weight: 600;
            margin-bottom: 3px;
        }}

        ul {{ margin: 3px 0 3px 17px; padding: 0; }}
        li {{
            font-size: 9.2pt;
            margin-bottom: 2px;
            line-height: 1.38;
            color: #333;
        }}

        a {{ color: #0f3460; }}

        @media print {{
            body {{ background: #fff; }}
            .resume-container {{ box-shadow: none; }}
            .sidebar {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
        }}
    </style>
</head>
<body>
    <div class="resume-container">
      <div class="sidebar">
        <div class="sidebar-name">{_esc(p.get('full_name', ''))}</div>
        <div class="sidebar-title">{_esc(p.get('title', ''))}</div>
        {sidebar_content}
      </div>
      <div class="main">
        {main_content}
      </div>
    </div>
</body>
</html>"""
