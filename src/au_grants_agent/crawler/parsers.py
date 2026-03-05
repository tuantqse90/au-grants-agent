"""HTML parsing helper utilities."""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup, Tag


def clean_text(text: Optional[str]) -> Optional[str]:
    """Clean and normalize extracted text."""
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else None


def extract_amount_range(text: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """Extract min and max dollar amounts from text like '$10,000 - $500,000'."""
    if not text:
        return None, None
    amounts = re.findall(r"\$[\d,]+(?:\.\d{2})?", text)
    parsed = []
    for a in amounts:
        try:
            parsed.append(float(a.replace("$", "").replace(",", "")))
        except ValueError:
            continue
    if len(parsed) >= 2:
        return min(parsed), max(parsed)
    elif len(parsed) == 1:
        return parsed[0], parsed[0]
    return None, None


def extract_date(text: Optional[str]) -> Optional[str]:
    """Try to extract an ISO date from various formats."""
    if not text:
        return None
    text = text.strip()
    # Try dd/mm/yyyy
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        day, month, year = m.group(1), m.group(2), m.group(3)
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    # Try dd Month yyyy
    m = re.search(
        r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
        text, re.IGNORECASE,
    )
    if m:
        day = m.group(1).zfill(2)
        month_name = m.group(2)
        year = m.group(3)
        months = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
        }
        month = months.get(month_name.lower(), "01")
        return f"{year}-{month}-{day}"
    # Already ISO-like
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    return None


def get_soup(html: str) -> BeautifulSoup:
    """Create a BeautifulSoup parser from HTML."""
    return BeautifulSoup(html, "lxml")


def safe_select_text(element: Optional[Tag], selector: str) -> Optional[str]:
    """Safely select and extract text from a CSS selector."""
    if element is None:
        return None
    found = element.select_one(selector)
    if found:
        return clean_text(found.get_text())
    return None
