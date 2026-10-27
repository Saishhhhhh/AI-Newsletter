"""
html_parser.py
Converts AI Weekly newsletter markdown files into a polished, styled HTML email.

Usage:
    from html_parser import convert_md_to_html
    html = convert_md_to_html("newsletter.md")

    # Or run directly:
    python html_parser.py newsletter.md output.html
"""

import re
import sys


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
        "spotlight": {"text": "", "url": ""},
    }

    # ── Spotlight line (pulled out before section walking so it doesn't pollute bottom_line) ─
    spotlight_m = re.search(r"🔦\s*SPOTLIGHT:\s*(.+)", md)
    if spotlight_m:
        spotlight_text = spotlight_m.group(1).strip()
        url_m = re.search(r"\[Source URL\]\((.+?)\)", spotlight_text)
        if url_m:
            data["spotlight"]["url"] = url_m.group(1)
            spotlight_text = re.sub(r"\s*\[Source URL\]\(.+?\)", "", spotlight_text).strip()
        data["spotlight"]["text"] = spotlight_text
        md = md[:spotlight_m.start()].rstrip()

    lines = md.splitlines()
    i = 0

    # ── Title & date ──────────────────────────────────────────
    for j, line in enumerate(lines):
        m = re.match(r"^#\s+(.+)", line)
        if m:
            data["title"] = m.group(1).strip()
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

    text = flush_buffer()
    if current_section and text:
        _store_buffer(current_section, text, data)

    return data


def _store_buffer(section: str, text: str, data: dict):
    """Parse buffered text into the correct data field. Failures in one section
    are swallowed so a single malformed section doesn't drop the whole issue."""
    try:
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
    except Exception as e:
        print(f"[html_parser] Skipping section '{section}' due to parse error: {e}")


def _parse_big_story(text: str, story: dict):
    lines = [l for l in text.splitlines() if l.strip()]
    body_lines = []
    for line in lines:
        url_m = re.search(r"\[([^\]]+)\]\((https?://[^\s)]+)\)\.?\s*$", line)
        if url_m:
            story["url"] = url_m.group(2)
            line = line[:url_m.start()].strip()
        else:
            fallback_m = re.search(r"\[Source URL\]\((https?://[^\s)]+)\)", line)
            if fallback_m:
                story["url"] = fallback_m.group(1)
                line = re.sub(r"\s*\[Source URL\]\(.+?\)", "", line).strip()
        body_lines.append(line)
    story["body"] = " ".join(body_lines).strip()


def _parse_quick_hits(text: str, hits: list):
    """Each bullet: - Text [Source URL](url) or - Text [label](url)"""
    for line in text.splitlines():
        line = line.strip()
        if not line.lstrip()[:1] in ("-", "*"):
            continue
        line = line.lstrip("-* ").strip()
        url_m = re.search(r"\[([^\]]+)\]\((https?://[^\s)]+)\)\.?\s*$", line)
        if url_m:
            url = url_m.group(2)
            clean = line[:url_m.start()].strip()
        else:
            fallback_m = re.search(r"\[Source URL\]\((https?://[^\s)]+)\)", line)
            if fallback_m:
                url = fallback_m.group(1)
                clean = re.sub(r"\s*\[Source URL\]\(.+?\)", "", line).strip()
            else:
                url = ""
                clean = line
        hits.append({"text": clean, "url": url})


ANY_URL_PATTERN = re.compile(r"\((https?://[^\s)]+)\)")


def _fallback_bold_title(line_s: str):
    """
    Defense-in-depth for when the model writes **Title** without wrapping it in a markdown
    link (e.g. puts the url in a trailing [Source URL](url) instead). Pulls the bold text as
    the title and the first url found anywhere on the line as the link.
    """
    m = re.match(r"[-*]?\s*\*\*(.+?)\*\*\s*(.*)", line_s)
    if not m:
        return None
    title = m.group(1).strip()
    rest = m.group(2)
    url_m = ANY_URL_PATTERN.search(rest)
    url = url_m.group(1) if url_m else ""
    rest_clean = re.sub(r"\[.*?\]\(https?://[^\s)]+\)", "", rest).strip(" -—–")
    return title, url, rest_clean


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
        m = re.match(r"[-*]?\s*\*\*\[(.+?)\]\((.+?)\)\*\*\s*(?:by\s+(.+))?", line_s)
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

        fallback = _fallback_bold_title(line_s) if line_s[:1] in ("-", "*") and "**" in line_s else None
        if fallback:
            if current:
                papers.append(current)
            title, url, rest_clean = fallback
            authors = ""
            by_m = re.match(r"by\s+([^—–\-]+)", rest_clean, re.I)
            if by_m:
                authors = by_m.group(1).strip()
                rest_clean = rest_clean[by_m.end():].strip(" -—–")
            current = {
                "title": title,
                "url": url,
                "authors": authors,
                "summary": rest_clean,
                "pdf_url": "",
            }
            continue

        if current is None:
            continue

        pdf_m = re.search(r"\[PDF\]\((.+?)\)", line_s)
        if pdf_m:
            current["pdf_url"] = pdf_m.group(1)
            continue

        if line_s and line_s[:1] not in ("-", "*"):
            sep = " " if current["summary"] else ""
            current["summary"] += sep + line_s

    if current:
        papers.append(current)


def _parse_github(text: str, repos: list):
    """
    Each repo: - **[name](url)** — ⭐ Xk this week. Description...
    (Supports description on the same line or on subsequent lines)
    """
    current = None
    for line in text.splitlines():
        line_s = line.strip()
        if not line_s:
            continue

        is_bullet = line_s[:1] in ("-", "*")
        m = re.match(r"[-*]?\s*\*\*\[(.+?)\]\((.+?)\)\*\*(.*)", line_s) if is_bullet else None
        if m:
            if current:
                repos.append(current)
            name = m.group(1).strip()
            url = m.group(2).strip()
            rest = m.group(3).strip(" —–-")

            stars_raw = ""
            stars_m = re.search(r"⭐\s*([\d\.]+[kKmM]?)(?:\s*stars?)?(?:\s*this week)?", rest, re.I)
            if stars_m:
                stars_raw = stars_m.group(1)
                rest = (rest[:stars_m.start()] + rest[stars_m.end():]).strip(" —–-.")

            current = {
                "name": name,
                "url": url,
                "stars": stars_raw,
                "description": rest,
            }
            continue

        fallback = _fallback_bold_title(line_s) if is_bullet and "**" in line_s else None
        if fallback:
            if current:
                repos.append(current)
            name, url, rest_clean = fallback
            stars_raw = ""
            stars_m = re.search(r"⭐\s*([\d\.]+[kKmM]?)(?:\s*stars?)?(?:\s*this week)?", rest_clean, re.I)
            if stars_m:
                stars_raw = stars_m.group(1)
                rest_clean = (rest_clean[:stars_m.start()] + rest_clean[stars_m.end():]).strip(" —–-.")
            current = {
                "name": name,
                "url": url,
                "stars": stars_raw,
                "description": rest_clean,
            }
            continue

        if current and not is_bullet:
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
        if line_s[:1] not in ("-", "*"):
            continue
        m = re.match(r"[-*]\s*\*\*\[(.+?)\]\((.+?)\)\*\*\s*[—–-]\s*(.+)", line_s)
        if m:
            products.append({
                "name": m.group(1),
                "url": m.group(2),
                "description": m.group(3).strip(),
            })
            continue

        fallback = _fallback_bold_title(line_s) if "**" in line_s else None
        if fallback:
            name, url, rest_clean = fallback
            products.append({
                "name": name,
                "url": url,
                "description": rest_clean.lstrip("-—– ").strip(),
            })


# ─────────────────────────────────────────────────────────────
# HTML RENDERER
# ─────────────────────────────────────────────────────────────

FONT_STACK = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

# Per-section accent colors — keeps the "same gray card everywhere" look from
# feeling flat and gives each section visual identity.
ACCENT = {
    "big_story":  "#2F80ED",
    "quick_hits": "#7C3AED",
    "papers":     "#0EA5E9",
    "github":     "#111827",
    "learn":      "#059669",
    "products":   "#EA580C",
    "spotlight":  "#D97706",
}

BUTTON_HTML = """
<table border="0" cellspacing="0" cellpadding="0" style="margin-top:16px;">
  <tr>
    <td align="center" style="border-radius:6px;" bgcolor="{color}">
      <a href="{url}" target="_blank"
         style="font-size:15px;font-family:{font};
                color:#ffffff;text-decoration:none;border-radius:6px;padding:12px 24px;
                display:inline-block;font-weight:600;">
        {label}
      </a>
    </td>
  </tr>
</table>
""".replace("{font}", FONT_STACK)

DIVIDER = '<div style="border-top:1px solid #E5E7EB;margin:28px 0;"></div>'


def _pill(text: str, color: str) -> str:
    if not text:
        return ""
    return (
        f'<span style="display:inline-block;background-color:{color}1A;color:{color};'
        f'font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px;'
        f'margin-left:8px;">{text}</span>'
    )


def _section_card(emoji: str, heading: str, accent: str, body_html: str) -> str:
    return f"""
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
       style="background-color:#FFFFFF;border:1px solid #E5E7EB;border-left:4px solid {accent};
              border-radius:8px;">
  <tr>
    <td style="padding:22px 24px;">
      <h2 style="font-size:19px;font-weight:700;margin:0 0 14px 0;color:#111111;letter-spacing:-0.3px;">
        {emoji} {heading}
      </h2>
      {body_html}
    </td>
  </tr>
</table>
{DIVIDER}
"""


CSS = f"""
body,table,td,a{{-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;}}
table,td{{mso-table-lspace:0pt;mso-table-rspace:0pt;}}
img{{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none;}}
table{{border-collapse:collapse !important;}}
body{{height:100%!important;margin:0!important;padding:0!important;width:100%!important;
     background-color:#F3F4F6;font-family:{FONT_STACK};
     color:#111111;}}
a{{color:#2F80ED;text-decoration:none;font-weight:600;}}
a:hover{{text-decoration:underline;}}
@media only screen and (max-width:600px){{
  .container{{width:100%!important;max-width:100%!important;}}
  .p-sm{{padding:16px!important;}}
  .hero-pad{{padding:28px 20px!important;}}
}}
"""


def render_html(data: dict) -> str:
    parts = []

    # ── Hero band ─────────────────────────────────────────────
    parts.append(f"""
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
       style="background:linear-gradient(135deg,#1E3A8A 0%,#2F80ED 100%);border-radius:12px 12px 0 0;">
  <tr>
    <td class="hero-pad" style="padding:36px 32px 28px 32px;">
      <p style="margin:0 0 8px 0;font-size:12px;font-weight:700;letter-spacing:1.5px;
                text-transform:uppercase;color:#BFDBFE;">
        AI Weekly · {data['date'] or ''}
      </p>
      <h1 style="font-size:26px;font-weight:800;margin:0 0 14px 0;color:#FFFFFF;letter-spacing:-0.4px;line-height:1.3;">
        {data['title']}
      </h1>
      <p style="font-size:15px;line-height:1.6;margin:0;color:#E0E7FF;">
        {data['intro']}
      </p>
    </td>
  </tr>
</table>
""")

    # ── Spotlight callout ────────────────────────────────────
    sp = data.get("spotlight", {})
    if sp.get("text"):
        link = (
            f'<a href="{sp["url"]}" style="font-size:13px;font-weight:700;color:{ACCENT["spotlight"]};">Dig in →</a>'
            if sp.get("url") else ""
        )
        parts.append(f"""
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
       style="background-color:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;margin-top:16px;">
  <tr>
    <td style="padding:18px 22px;">
      <p style="margin:0 0 6px 0;font-size:13px;font-weight:800;letter-spacing:0.5px;
                text-transform:uppercase;color:{ACCENT['spotlight']};">
        🔦 Spotlight — the thing nobody's talking about
      </p>
      <p style="font-size:15px;line-height:1.6;margin:0 0 8px 0;color:#374151;">
        {sp['text']}
      </p>
      {link}
    </td>
  </tr>
</table>
""")

    parts.append('<div style="height:24px;"></div>')

    # ── Big Story (feature / pull-quote treatment) ───────────
    bs = data["big_story"]
    if bs["body"]:
        btn = BUTTON_HTML.format(url=bs["url"], label="Read the full story", color=ACCENT["big_story"]) if bs["url"] else ""
        body = _section_card(
            "📰", "Big Story", ACCENT["big_story"],
            f"""
      <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
             style="border-left:3px solid {ACCENT['big_story']};">
        <tr>
          <td style="padding-left:16px;">
            <p style="font-size:18px;line-height:1.55;margin:0 0 14px 0;color:#1F2933;font-weight:500;">
              {bs['body']}
            </p>
          </td>
        </tr>
      </table>
      {btn}
      """
        )
        parts.append(body)

    # ── Quick Hits ────────────────────────────────────────────
    if data["quick_hits"]:
        rows = ""
        for hit in data["quick_hits"]:
            src = f'<a href="{hit["url"]}" style="font-size:12px;font-weight:700;">Source →</a>' if hit["url"] else ""
            rows += f"""
<tr>
  <td style="padding:12px 16px;border-left:3px solid {ACCENT['quick_hits']};background-color:#FAF5FF;
             border-radius:0 6px 6px 0;">
    <p style="font-size:15px;line-height:1.5;margin:0;color:#1F2933;">
      {hit['text']} {src}
    </p>
  </td>
</tr>
<tr><td style="height:10px;"></td></tr>
"""
        body = f"""<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">{rows}</table>"""
        parts.append(_section_card("⚡", "Quick Hits", ACCENT["quick_hits"], body))

    # ── Papers ────────────────────────────────────────────────
    if data["papers"]:
        rows = ""
        for p in data["papers"]:
            pdf_link = f'<a href="{p["pdf_url"]}" style="font-size:12px;font-weight:700;color:{ACCENT["papers"]};">📄 PDF</a>' if p["pdf_url"] else ""
            authors_str = f" by {p['authors']}" if p["authors"] else ""
            rows += f"""
<tr>
  <td style="padding-bottom:16px;border-bottom:1px solid #F1F5F9;">
    <p style="margin:0 0 4px 0;">
      <a href="{p['url']}" style="font-size:16px;font-weight:700;color:#111111;">{p['title']}</a>
    </p>
    <p style="font-size:13px;line-height:1.5;margin:0 0 6px 0;color:#6B7280;">
      {authors_str}{(' — ' + p['summary']) if p['summary'] else ''}
    </p>
    {pdf_link}
  </td>
</tr>
<tr><td style="height:12px;"></td></tr>
"""
        parts.append(_section_card("📄", "Papers Worth Reading", ACCENT["papers"],
                                    f'<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">{rows}</table>'))

    # ── GitHub Spotlight ──────────────────────────────────────
    if data["github"]:
        rows = ""
        for repo in data["github"]:
            stars_pill = _pill(f"⭐ {repo['stars']}" if repo["stars"] else "", ACCENT["github"])
            rows += f"""
<tr>
  <td style="padding:12px;background-color:#F9FAFB;border:1px solid #E5E7EB;
             border-radius:6px;">
    <p style="margin:0 0 4px 0;">
      💻 <a href="{repo['url']}" style="font-size:15px;font-weight:700;color:#111111;">{repo['name']}</a>
      {stars_pill}
    </p>
    <p style="font-size:14px;color:#4B5563;margin:0;line-height:1.5;">
      {repo['description']}
    </p>
  </td>
</tr>
<tr><td style="height:10px;"></td></tr>
"""
        parts.append(_section_card("🐙", "GitHub Spotlight", ACCENT["github"],
                                    f'<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">{rows}</table>'))

    # ── One Thing to Learn ────────────────────────────────────
    if data["learn"]:
        parts.append(_section_card(
            "🎓", "One Thing to Learn", ACCENT["learn"],
            f"""<p style="font-size:15px;line-height:1.6;color:#374151;margin:0;">{data['learn']}</p>"""
        ))

    # ── Products ──────────────────────────────────────────────
    if data["products"]:
        rows = ""
        for prod in data["products"]:
            rows += f"""
<tr>
  <td style="padding-bottom:12px;">
    <p style="font-size:15px;margin:0;color:#4B5563;">
      <a href="{prod['url']}" style="font-weight:700;color:{ACCENT['products']};">{prod['name']}</a> — {prod['description']}
    </p>
  </td>
</tr>
"""
        parts.append(_section_card("🚀", "Products", ACCENT["products"],
                                    f'<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">{rows}</table>'))

    # ── Bottom Line ───────────────────────────────────────────
    if data["bottom_line"]:
        parts.append(f"""
<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
  <tr>
    <td align="center" style="padding:8px 8px 4px 8px;">
      <p style="font-size:15px;line-height:1.6;color:#4B5563;margin:0;text-align:center;font-style:italic;">
        👋 {data['bottom_line']}
      </p>
    </td>
  </tr>
</table>
""")

    # ── Footer ────────────────────────────────────────────────
    parts.append(f"""
<div style="border-top:1px solid #E5E7EB;margin:24px 0 0 0;padding-top:16px;text-align:center;">
  <p style="font-size:12px;color:#9CA3AF;margin:0;">
    Written by an autonomous research agent · If this was useful, forward it to a builder friend.
  </p>
</div>
""")

    inner = "\n".join(parts)

    def _replace_markdown_link(m):
        label, url = m.group(1).strip(), m.group(2).strip()
        if label.startswith("http://") or label.startswith("https://"):
            label = "Source →"
        return f'<a href="{url}" style="color:#2F80ED;font-weight:600;text-decoration:none;">{label}</a>'

    inner = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", _replace_markdown_link, inner)
    inner = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", inner)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{data['title']}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>{CSS}</style>
</head>
<body style="margin:0;padding:0;background-color:#F3F4F6;">
<center style="width:100%;background-color:#F3F4F6;">
  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
         style="background-color:#F3F4F6;max-width:600px;margin:0 auto;" class="container">
    <tr>
      <td align="center" valign="top" style="padding:24px 16px 32px 16px;" class="p-sm">
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


def html_to_plaintext(html: str) -> str:
    """Crude but good-enough HTML → plaintext fallback for the email's text/plain part."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(p|tr|h1|h2|div)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
        print("Usage: python html_parser.py <input.md> [output.html]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace(".md", ".html")

    html = convert_md_to_html(input_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Converted '{input_path}' -> '{output_path}'")
