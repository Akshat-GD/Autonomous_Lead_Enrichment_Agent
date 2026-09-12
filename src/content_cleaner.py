from __future__ import annotations

import re

from bs4 import BeautifulSoup
from markdownify import markdownify as html_to_markdown

from .config import settings

_STRIP_TAGS = ["script", "style", "svg", "noscript", "iframe", "path", "link", "meta"]

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# Generic/public-looking mailbox prefixes we care about (per spec: contact@,
# sales@, support@, etc.) — filters out obviously personal-looking noise
# scraped from e.g. blog author bylines.
_GENERIC_PREFIXES = (
    "contact", "sales", "support", "info", "hello", "hi", "press",
    "media", "partnerships", "careers", "jobs", "help", "team", "privacy",
    "security", "legal", "billing", "enterprise",
)


def extract_public_emails(raw_text: str) -> list[str]:
    found = {m.group(0).lower() for m in _EMAIL_RE.finditer(raw_text)}
    generic = {e for e in found if e.split("@", 1)[0] in _GENERIC_PREFIXES}
    # Fall back to all found emails if none matched the generic-prefix filter,
    # rather than silently returning nothing.
    result = generic or found
    # Drop obvious asset/false-positive matches like foo@2x.png artifacts.
    return sorted(e for e in result if not e.endswith((".png", ".jpg", ".svg", ".webp")))


def html_to_clean_markdown(html: str) -> str:
    """Strip boilerplate and return trimmed Markdown for one page."""
    soup = BeautifulSoup(html, "html.parser")

    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Repeated site chrome (nav bars, footers) shows up on every crawled page
    # and burns tokens without adding new signal beyond the homepage.
    for tag in soup.find_all(["nav", "footer"]):
        tag.decompose()

    body = soup.body or soup
    markdown = html_to_markdown(str(body), heading_style="ATX")

    # Collapse excess blank lines left behind by stripped elements.
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()

    if len(markdown) > settings.max_chars_per_page:
        markdown = markdown[: settings.max_chars_per_page] + "\n\n...[truncated]"

    return markdown


def build_llm_context(pages: dict[str, str]) -> tuple[str, list[str]]:
    """Turn {url: raw_html} into a single token-budgeted Markdown context.

    Returns (context_markdown, list_of_emails_found_via_regex_safety_net).
    """
    sections: list[str] = []
    all_text_for_email_scan: list[str] = []
    running_len = 0

    for url, html in pages.items():
        cleaned = html_to_clean_markdown(html)
        all_text_for_email_scan.append(cleaned)

        section = f"\n\n## SOURCE PAGE: {url}\n\n{cleaned}"
        if running_len + len(section) > settings.max_chars_total_context:
            remaining = settings.max_chars_total_context - running_len
            if remaining > 200:  # only include if a meaningful chunk fits
                sections.append(section[:remaining] + "\n\n...[context budget reached]")
            break
        sections.append(section)
        running_len += len(section)

    context = "".join(sections).strip()
    emails = extract_public_emails("\n".join(all_text_for_email_scan))
    return context, emails