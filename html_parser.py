"""
md_to_html.py
Converts AI Weekly newsletter markdown files into styled HTML email format.

Usage:
    from md_to_html import convert_md_to_html
    html = convert_md_to_html("newsletter.md")

    # Or run directly:
    python md_to_html.py newsletter.md output.html
"""

import re
import sys
from datetime import datetime


# ─────────────────────────────────────────────────────────────
# SECTION PARSERS
# ─────────────────────────────────────────────────────────────

def parse_markdown(md: str) -> dict:
    """
    Parse the AI Weekly markdown into structured sections.
    Returns a dict with keys matching the newsletter sections.
    """
    data = {
        "title": "",
        "date": "",
        "intro": "",
        "big_story": {"title": "", "body": "", "url": ""},
        "quick_hits": [],          # list of {text, url}
        "papers": [],              # list of {title, url, pdf_url, authors, summary}
        "github": [],              # list of {name, url, stars, description}
        "learn": "",
        "products": [],            # list of {name, url, description}
        "bottom_line": "",
    }

    lines = md.splitlines()
    i = 0

    # ── Title & date ──────────────────────────────────────────
    for j, line in enumerate(lines):
        m = re.match(r"^#\s+(.+)", line)
        if m:
            data["title"] = m.group(1).strip()
            # try to extract date like "April 05 2026"
            dm = re.search(r"(\w+ \d{1,2},?\s*\d{4})", data["title"])
            if dm:
                data["date"] = dm.group(1)
            i = j + 1
            break

    # ── Walk remaining lines section by section ───────────────
    current_section = None
    buffer = []

    def flush_buffer():
        return "\n".join(buffer).strip()

    def next_section(name):
        nonlocal current_section, buffer
        text = flush_buffer()
        if current_section and text:
            _store_buffer(current_section, text, data)
        current_section = name
        buffer = []

    # Map emoji/keyword → internal section name
    SECTION_MAP = {
        "🔥": "intro",
        "📰": "big_story",
        "⚡": "quick_hits",
        "📄": "papers",
        "🐙": "github",
        "🎓": "learn",
        "🚀": "products",
        "👋": "bottom_line",
    }

    while i < len(lines):
        line = lines[i]

        # Detect section headings (## lines)
        m = re.match(r"^##\s+(.+)", line)
        if m:
            heading = m.group(1)
            detected = None
            for emoji, name in SECTION_MAP.items():
                if emoji in heading:
                    detected = name
                    break
            if detected:
                next_section(detected)
                i += 1
                continue

        buffer.append(line)
        i += 1

    # flush last buffer
    text = flush_buffer()
    if current_section and text:
        _store_buffer(current_section, text, data)

    return data


def _store_buffer(section: str, text: str, data: dict):
    """Parse buffered text into the correct data field."""

    if section == "intro":
        data["intro"] = text.strip()

    elif section == "big_story":
        _parse_big_story(text, data["big_story"])

    elif section == "quick_hits":
        _parse_quick_hits(text, data["quick_hits"])

    elif section == "papers":
        _parse_papers(text, data["papers"])

    elif section == "github":
        _parse_github(text, data["github"])

    elif section == "learn":
        data["learn"] = text.strip()

    elif section == "products":
        _parse_products(text, data["products"])

    elif section == "bottom_line":
        data["bottom_line"] = text.strip()


def _parse_big_story(text: str, story: dict):
    lines = [l for l in text.splitlines() if l.strip()]
    body_lines = []
    for line in lines:
        url_m = re.search(r"\[Source URL\]\((.+?)\)", line)
        if url_m:
            story["url"] = url_m.group(1)
            # strip the source link from line
            line = re.sub(r"\s*\[Source URL\]\(.+?\)", "", line).strip()
        body_lines.append(line)
    story["body"] = " ".join(body_lines).strip()


def _parse_quick_hits(text: str, hits: list):
    """Each bullet: - Text [Source URL](url)"""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        line = line.lstrip("- ").strip()
        url_m = re.search(r"\[Source URL\]\((.+?)\)", line)
        url = url_m.group(1) if url_m else ""
        clean = re.sub(r"\s*\[Source URL\]\(.+?\)", "", line).strip()
        hits.append({"text": clean, "url": url})


def _parse_papers(text: str, papers: list):
    """
    Each paper block:
    - **[Title](url)** by Authors
      Summary sentence(s)
      [PDF](pdf_url)
    """
    current = None
    for line in text.splitlines():
        line_s = line.strip()
        # New paper starts with **[
        m = re.match(r"-?\s*\*\*\[(.+?)\]\((.+?)\)\*\*\s*(?:by\s+(.+))?", line_s)
        if m:
            if current:
                papers.append(current)
            current = {
                "title": m.group(1),
                "url": m.group(2),
                "authors": (m.group(3) or "").strip(),
                "summary": "",
                "pdf_url": "",
            }
            continue

        if current is None:
            continue

        # PDF link
        pdf_m = re.search(r"\[PDF\]\((.+?)\)", line_s)
        if pdf_m:
            current["pdf_url"] = pdf_m.group(1)
            continue

        # Summary line (non-empty, not a list marker)
        if line_s and not line_s.startswith("-"):
            sep = " " if current["summary"] else ""
            current["summary"] += sep + line_s

    if current:
        papers.append(current)


def _parse_github(text: str, repos: list):
    """
    Each repo: - **[name](url)** — ⭐ Xk this week
      Description line
    """
    current = None
    for line in text.splitlines():
        line_s = line.strip()
        m = re.match(r"-?\s*\*\*\[(.+?)\]\((.+?)\)\*\*.*?(?:⭐\s*([\d\.]+[km]?)\s*this week)?", line_s, re.I)
        if m and m.group(1):
            if current:
                repos.append(current)
            stars_raw = m.group(3) or ""
            current = {
                "name": m.group(1),
                "url": m.group(2),
                "stars": stars_raw,
                "description": "",
            }
            continue
        if current and line_s:
            sep = " " if current["description"] else ""
            current["description"] += sep + line_s

    if current:
        repos.append(current)


def _parse_products(text: str, products: list):
    """
    Each product: - **[Name](url)** — Description
    """
    for line in text.splitlines():
        line_s = line.strip()
        if not line_s.startswith("-"):
            continue
        m = re.match(r"-\s*\*\*\[(.+?)\]\((.+?)\)\*\*\s*[—–-]\s*(.+)", line_s)
        if m:
            products.append({
                "name": m.group(1),
                "url": m.group(2),
                "description": m.group(3).strip(),
            })


# ─────────────────────────────────────────────────────────────
# HTML RENDERER
# ─────────────────────────────────────────────────────────────

BUTTON_HTML = """
<table border="0" cellspacing="0" cellpadding="0" style="margin-top:16px;">
  <tr>
    <td align="center" style="border-radius:4px;" bgcolor="#2F80ED">
      <a href="{url}" target="_blank"
         style="font-size:16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
                color:#ffffff;text-decoration:none;border-radius:4px;padding:12px 24px;
                border:1px solid #2F80ED;display:inline-block;font-weight:bold;">
        {label}
      </a>
    </td>
  </tr>
</table>
"""

DIVIDER = '<div style="border-top:1px solid #E5E7EB;margin:32px 0;"></div>'

CSS = """
body,table,td,a{-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;}
table,td{mso-table-lspace:0pt;mso-table-rspace:0pt;}
img{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;}
table{border-collapse:collapse !important;}
body{height:100%!important;margin:0!important;padding:0!important;width:100%!important;
     background-color:#FFFFFF;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
     color:#111111;}
a{color:#2F80ED;text-decoration:none;font-weight:500;}
a:hover{text-decoration:underline;}
h2{font-size:22px;font-weight:600;margin:0 0 16px 0;color:#111111;letter-spacing:-0.5px;}
@media only screen and (max-width:600px){
  .container{width:100%!important;max-width:100%!important;}
  .p-sm{padding:16px!important;}
}
"""


def render_html(data: dict) -> str:
    parts = []

    # ── Header ────────────────────────────────────────────────
    parts.append(f"""
<h1 style="font-size:28px;font-weight:bold;margin:0 0 16px 0;color:#111111;letter-spacing:-0.5px;">
  {data['title']}
</h1>
<p style="font-size:16px;line-height:1.6;margin:0;color:#374151;">
  {data['intro']}
</p>
{DIVIDER}
""")

    # ── Big Story ─────────────────────────────────────────────
    bs = data["big_story"]
    if bs["body"]:
        btn = BUTTON_HTML.format(url=bs["url"], label="Read the full story") if bs["url"] else ""
        parts.append(f"""
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
       style="background-color:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;">
  <tr>
    <td style="padding:24px;">
      <h2 style="margin-top:0;">📰 Big Story</h2>
      <p style="font-size:16px;line-height:1.6;margin:0 0 16px 0;color:#374151;">
        {bs['body']}
      </p>
      {btn}
    </td>
  </tr>
</table>
{DIVIDER}
""")

    # ── Quick Hits ────────────────────────────────────────────
    if data["quick_hits"]:
        rows = ""
        for hit in data["quick_hits"]:
            src = f'<a href="{hit["url"]}" style="font-size:13px;font-weight:600;">[Source →]</a>' if hit["url"] else ""
            rows += f"""
<tr>
  <td style="padding:12px 16px;border-left:3px solid #2F80ED;background-color:#F8FAFC;
             margin-bottom:12px;display:block;">
    <p style="font-size:15px;line-height:1.5;margin:0;">
      {hit['text']} {src}
    </p>
  </td>
</tr>
<tr><td style="height:10px;"></td></tr>
"""
        parts.append(f"""
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
  <tr><td><h2>⚡ Quick Hits</h2></td></tr>
  {rows}
</table>
{DIVIDER}
""")

    # ── Papers ────────────────────────────────────────────────
    if data["papers"]:
        rows = ""
        for p in data["papers"]:
            pdf_link = f'<a href="{p["pdf_url"]}" style="font-size:13px;font-weight:600;color:#2F80ED;">📄 Download PDF</a>' if p["pdf_url"] else ""
            authors_str = f" by {p['authors']}" if p["authors"] else ""
            rows += f"""
<tr>
  <td style="padding-bottom:16px;">
    <p style="margin:0 0 4px 0;">
      <a href="{p['url']}" style="font-size:16px;font-weight:700;color:#111111;">{p['title']}</a>
    </p>
    <p style="font-size:14px;line-height:1.5;margin:0 0 6px 0;color:#4B5563;">
      {authors_str}{(' — ' + p['summary']) if p['summary'] else ''}
    </p>
    {pdf_link}
  </td>
</tr>
"""
        parts.append(f"""
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
  <tr><td><h2>📄 Papers Worth Reading</h2></td></tr>
  {rows}
</table>
{DIVIDER}
""")

    # ── GitHub Spotlight ──────────────────────────────────────
    if data["github"]:
        rows = ""
        for repo in data["github"]:
            stars_str = f" — ⭐ {repo['stars']} this week" if repo["stars"] else ""
            rows += f"""
<tr>
  <td style="padding:12px;background-color:#F8FAFC;border:1px solid #E2E8F0;
             border-radius:6px;margin-bottom:12px;display:block;">
    <p style="margin:0 0 4px 0;">
      💻 <a href="{repo['url']}" style="font-size:16px;font-weight:bold;">{repo['name']}</a>
      <span style="font-size:14px;color:#4B5563;">{stars_str}</span>
    </p>
    <p style="font-size:14px;color:#4B5563;margin:0;line-height:1.5;">
      {repo['description']}
    </p>
  </td>
</tr>
<tr><td style="height:10px;"></td></tr>
"""
        parts.append(f"""
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
  <tr><td><h2>🐙 GitHub Spotlight</h2></td></tr>
  {rows}
</table>
{DIVIDER}
""")

    # ── One Thing to Learn ────────────────────────────────────
    if data["learn"]:
        parts.append(f"""
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
  <tr><td><h2>🎓 One Thing to Learn</h2></td></tr>
  <tr>
    <td>
      <p style="font-size:15px;line-height:1.6;color:#374151;margin:0;">
        {data['learn']}
      </p>
    </td>
  </tr>
</table>
{DIVIDER}
""")

    # ── Products ──────────────────────────────────────────────
    if data["products"]:
        rows = ""
        for prod in data["products"]:
            rows += f"""
<tr>
  <td style="padding-bottom:12px;">
    <p style="font-size:15px;margin:0;color:#4B5563;">
      <a href="{prod['url']}" style="font-weight:600;">{prod['name']}</a> — {prod['description']}
    </p>
  </td>
</tr>
"""
        parts.append(f"""
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
  <tr><td><h2>🚀 Products</h2></td></tr>
  {rows}
</table>
{DIVIDER}
""")

    # ── Bottom Line ───────────────────────────────────────────
    if data["bottom_line"]:
        parts.append(f"""
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
  <tr>
    <td align="center">
      <p style="font-size:15px;line-height:1.6;color:#4B5563;margin:0;text-align:center;">
        {data['bottom_line']}
      </p>
    </td>
  </tr>
</table>
""")

    inner = "\n".join(parts)

    # Convert markdown bold (**) to HTML strong tags
    inner = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", inner)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{data['title']}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>{CSS}</style>
</head>
<body style="margin:0;padding:0;background-color:#FFFFFF;">
<center style="width:100%;background-color:#FFFFFF;">
  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
         style="background-color:#FFFFFF;max-width:600px;margin:0 auto;" class="container">
    <tr>
      <td align="center" valign="top" style="padding:24px 16px;" class="p-sm">
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
          <tr><td>
            {inner}
          </td></tr>
        </table>
      </td>
    </tr>
  </table>
</center>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────

def convert_md_to_html(md_input: str, is_file: bool = True) -> str:
    """
    Convert an AI Weekly markdown newsletter to an HTML email.

    Args:
        md_input:  Either a file path (if is_file=True) or raw markdown text.
        is_file:   If True (default), md_input is treated as a file path.

    Returns:
        HTML string ready to save or send.

    Examples:
        # From a file
        html = convert_md_to_html("newsletter.md")

        # From a string
        html = convert_md_to_html(raw_md_string, is_file=False)

        with open("output.html", "w") as f:
            f.write(html)
    """
    if is_file:
        with open(md_input, "r", encoding="utf-8") as f:
            md_text = f.read()
    else:
        md_text = md_input

    data = parse_markdown(md_text)
    return render_html(data)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python md_to_html.py <input.md> [output.html]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace(".md", ".html")

    html = convert_md_to_html(input_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅  Converted '{input_path}' → '{output_path}'")