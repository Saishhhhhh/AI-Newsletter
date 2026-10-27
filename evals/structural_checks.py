"""Deterministic, no-LLM checks for a generated newsletter draft. No network calls."""

import re
from html.parser import HTMLParser

REQUIRED_SECTIONS = ["🔥", "📰", "⚡", "📄", "🐙", "🎓", "🚀", "👋"]

BANNED_BUZZWORDS = [
    "game-changer",
    "revolutionary",
    "cutting-edge",
    "in today's fast-paced world",
    "unlock the power of",
]

WORD_COUNT_RANGE = (550, 950)  # a little slack around the 600-900 target


def check_word_count(md: str) -> list[str]:
    word_count = len(md.split())
    lo, hi = WORD_COUNT_RANGE
    if not (lo <= word_count <= hi):
        return [f"Word count {word_count} is outside the {lo}-{hi} range"]
    return []


def check_sections_present(md: str) -> list[str]:
    issues = []
    for emoji in REQUIRED_SECTIONS:
        if emoji not in md:
            issues.append(f"Missing required section marker: {emoji}")
    if "🔦 SPOTLIGHT" not in md:
        issues.append("Missing closing 🔦 SPOTLIGHT line")
    return issues


def check_items_have_sources(md: str) -> list[str]:
    issues = []
    quick_hits_block = _extract_block(md, "⚡")
    for line in quick_hits_block.splitlines():
        line = line.strip()
        if line.startswith("-") and "[Source URL]" not in line:
            issues.append(f"Quick Hit missing source link: {line[:60]}")
    return issues


def check_banned_buzzwords(md: str) -> list[str]:
    lowered = md.lower()
    return [f"Banned buzzword found: '{word}'" for word in BANNED_BUZZWORDS if word in lowered]


def _extract_block(md: str, emoji: str) -> str:
    lines = md.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("##") and emoji in line:
            start = i + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].strip().startswith("##"):
            end = i
            break
    return "\n".join(lines[start:end])


class _WellFormedChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    VOID_TAGS = {"br", "img", "hr", "meta", "input", "link"}

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID_TAGS:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"Mismatched closing tag: </{tag}>")
        elif self.stack:
            self.stack.pop()


def check_html_well_formed(html: str) -> list[str]:
    checker = _WellFormedChecker()
    try:
        checker.feed(html)
    except Exception as e:
        return [f"HTML parse error: {e}"]
    return checker.errors


def run_structural_checks(md: str, html: str | None = None) -> dict:
    issues = []
    issues += check_word_count(md)
    issues += check_sections_present(md)
    issues += check_items_have_sources(md)
    issues += check_banned_buzzwords(md)
    if html is not None:
        issues += check_html_well_formed(html)

    return {"passed": len(issues) == 0, "issues": issues}
