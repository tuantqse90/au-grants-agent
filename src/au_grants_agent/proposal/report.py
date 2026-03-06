"""Generate matching report PDF — comprehensive analysis of grants vs org profile."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fpdf import FPDF

from au_grants_agent.config import settings
from au_grants_agent.proposal.matcher import MatchResult
from au_grants_agent.utils.logger import get_logger

logger = get_logger()

# NullShift green
ACCENT = (0, 255, 136)
DARK = (13, 17, 23)
GRAY = (100, 100, 100)
WHITE = (255, 255, 255)
LIGHT_BG = (245, 245, 245)


def _find_font() -> Optional[str]:
    """Find a Unicode-capable TTF font."""
    candidates = [
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/UniFontSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/TTF/UniFontSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def _find_font_bold() -> Optional[str]:
    """Find a bold Unicode TTF font."""
    candidates = [
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/UniFontSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return None


class MatchingReportPDF(FPDF):
    """Custom FPDF for matching report."""

    def __init__(self, profile_name: str) -> None:
        super().__init__()
        self.profile_name = profile_name
        self._setup_fonts()

    def _setup_fonts(self) -> None:
        font_path = _find_font()
        font_bold = _find_font_bold()
        if font_path:
            self.add_font("UniFont", "", font_path, uni=True)
            if font_bold:
                self.add_font("UniFont", "B", font_bold, uni=True)
            else:
                self.add_font("UniFont", "B", font_path, uni=True)
            self._fn = "UniFont"
        else:
            logger.warning("No Unicode font found, using Helvetica fallback")
            self._fn = "Helvetica"

    def header(self):
        if self.page_no() > 1:
            self.set_font(self._fn, "B", 8)
            self.set_text_color(*GRAY)
            self.cell(0, 8, f"Grant Matching Report — {self.profile_name}", align="L")
            self.ln(2)
            self.set_draw_color(*ACCENT)
            self.set_line_width(0.5)
            self.line(10, self.get_y(), self.w - 10, self.get_y())
            self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font(self._fn, "", 7)
        self.set_text_color(*GRAY)
        self.cell(0, 10, f"AU Grants Agent | NullShift | Page {self.page_no()}", align="C")


def _score_color(score: float) -> tuple:
    """Return RGB based on score."""
    if score >= 0.7:
        return (0, 170, 100)
    elif score >= 0.5:
        return (0, 150, 200)
    elif score >= 0.3:
        return (200, 150, 0)
    return (150, 150, 150)


def generate_matching_report(
    profile_name: str,
    profile_type: str,
    profile_state: str,
    research_strengths: list[str],
    matches: list[MatchResult],
    output_dir: Optional[Path] = None,
) -> Path:
    """Generate a PDF matching report.

    Args:
        profile_name: Organisation name.
        profile_type: Org type (University, SME, etc.)
        profile_state: State abbreviation.
        research_strengths: List of research areas.
        matches: Ranked match results.
        output_dir: Output directory (default: proposals/).

    Returns:
        Path to generated PDF.
    """
    pdf = MatchingReportPDF(profile_name)
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Title Page ────────────────────────────────────────────
    pdf.add_page()

    # Green accent bar
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, 0, 8, 297, "F")

    pdf.ln(40)
    pdf.set_font(pdf._fn, "B", 28)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 15, "Grant Matching Report", ln=True, align="C")

    pdf.ln(5)
    pdf.set_font(pdf._fn, "", 14)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 10, profile_name, ln=True, align="C")

    pdf.ln(10)
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(1)
    pdf.line(60, pdf.get_y(), pdf.w - 60, pdf.get_y())

    pdf.ln(15)
    now = datetime.utcnow().strftime("%d %B %Y")
    meta_lines = [
        f"Date: {now}",
        f"Organisation Type: {profile_type or 'N/A'}",
        f"State: {profile_state or 'National'}",
        f"Grants Matched: {len(matches)}",
    ]
    pdf.set_font(pdf._fn, "", 11)
    for line in meta_lines:
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 8, line, ln=True, align="C")

    if research_strengths:
        pdf.ln(5)
        pdf.set_font(pdf._fn, "B", 10)
        pdf.set_text_color(*DARK)
        pdf.cell(0, 8, "Research Strengths:", ln=True, align="C")
        pdf.set_font(pdf._fn, "", 9)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 7, ", ".join(research_strengths[:8]), ln=True, align="C")

    # ── Executive Summary ─────────────────────────────────────
    pdf.add_page()

    pdf.set_font(pdf._fn, "B", 16)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 10, "Executive Summary", ln=True)
    pdf.set_fill_color(*ACCENT)
    pdf.rect(10, pdf.get_y(), 40, 2, "F")
    pdf.ln(8)

    # Score distribution
    excellent = sum(1 for m in matches if m.score >= 0.7)
    good = sum(1 for m in matches if 0.5 <= m.score < 0.7)
    fair = sum(1 for m in matches if 0.3 <= m.score < 0.5)
    low = sum(1 for m in matches if m.score < 0.3)

    pdf.set_font(pdf._fn, "", 10)
    pdf.set_text_color(*DARK)
    summary_lines = [
        f"Total grants analyzed: {len(matches)}",
        f"Excellent matches (70%+): {excellent}",
        f"Good matches (50-69%): {good}",
        f"Fair matches (30-49%): {fair}",
        f"Low relevance (<30%): {low}",
    ]
    for line in summary_lines:
        pdf.cell(0, 7, line, ln=True)

    # Top 3 recommendations
    if matches:
        pdf.ln(5)
        pdf.set_font(pdf._fn, "B", 12)
        pdf.cell(0, 8, "Top Recommendations", ln=True)
        pdf.ln(3)

        for i, m in enumerate(matches[:3], 1):
            g = m.grant
            color = _score_color(m.score)

            pdf.set_font(pdf._fn, "B", 10)
            pdf.set_text_color(*color)
            pdf.cell(0, 7, f"{i}. {m.score:.0%} — {g.title[:80]}", ln=True)

            pdf.set_font(pdf._fn, "", 9)
            pdf.set_text_color(*GRAY)
            pdf.cell(0, 6, f"   Agency: {g.agency or 'N/A'} | Category: {g.category or 'N/A'}", ln=True)
            if m.reasons:
                pdf.cell(0, 6, f"   Why: {'; '.join(m.reasons[:3])}", ln=True)
            pdf.ln(2)

    # ── Detailed Results Table ────────────────────────────────
    pdf.add_page()

    pdf.set_font(pdf._fn, "B", 16)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 10, "Detailed Match Results", ln=True)
    pdf.set_fill_color(*ACCENT)
    pdf.rect(10, pdf.get_y(), 40, 2, "F")
    pdf.ln(8)

    # Table header
    col_widths = [15, 15, 70, 40, 50]
    headers = ["#", "Score", "Grant Title", "Agency", "Match Reasons"]

    pdf.set_font(pdf._fn, "B", 8)
    pdf.set_fill_color(*ACCENT)
    pdf.set_text_color(*WHITE)
    for j, (header, w) in enumerate(zip(headers, col_widths)):
        pdf.cell(w, 7, header, border=1, fill=True, align="C")
    pdf.ln()

    # Table rows
    for i, m in enumerate(matches, 1):
        g = m.grant
        color = _score_color(m.score)

        if pdf.get_y() > 260:
            pdf.add_page()

        bg = LIGHT_BG if i % 2 == 0 else WHITE
        pdf.set_fill_color(*bg)
        pdf.set_font(pdf._fn, "", 7)

        row_data = [
            str(i),
            f"{m.score:.0%}",
            g.title[:45],
            (g.agency or "")[:25],
            "; ".join(m.reasons[:2])[:35] if m.reasons else "-",
        ]

        for j, (val, w) in enumerate(zip(row_data, col_widths)):
            if j == 1:
                pdf.set_text_color(*color)
            else:
                pdf.set_text_color(*DARK)
            pdf.cell(w, 6, val, border=1, fill=True)
        pdf.ln()

    # ── Per-grant detail pages ────────────────────────────────
    for i, m in enumerate(matches[:10], 1):
        g = m.grant
        color = _score_color(m.score)

        pdf.add_page()
        pdf.set_font(pdf._fn, "B", 14)
        pdf.set_text_color(*DARK)
        pdf.cell(0, 10, f"Grant #{i}: {g.title[:80]}", ln=True)
        pdf.set_fill_color(*ACCENT)
        pdf.rect(10, pdf.get_y(), 30, 1.5, "F")
        pdf.ln(6)

        # Score badge
        pdf.set_font(pdf._fn, "B", 20)
        pdf.set_text_color(*color)
        pdf.cell(30, 12, f"{m.score:.0%}", align="C")
        pdf.set_font(pdf._fn, "", 12)
        pdf.cell(0, 12, f"  {m.rating}", ln=True)
        pdf.ln(4)

        # Details
        pdf.set_font(pdf._fn, "", 9)
        pdf.set_text_color(*DARK)
        details = [
            ("GO ID", g.go_id or "N/A"),
            ("Agency", g.agency or "N/A"),
            ("Category", g.category or "N/A"),
            ("Status", g.status),
            ("Closing Date", g.closing_date or "N/A"),
        ]
        if g.amount_min:
            amt = f"${g.amount_min:,.0f}"
            if g.amount_max and g.amount_max != g.amount_min:
                amt += f" - ${g.amount_max:,.0f}"
            details.append(("Amount", amt))

        for label, value in details:
            pdf.set_font(pdf._fn, "B", 9)
            pdf.cell(30, 6, f"{label}:")
            pdf.set_font(pdf._fn, "", 9)
            pdf.cell(0, 6, value, ln=True)

        # Match reasons
        if m.reasons:
            pdf.ln(4)
            pdf.set_font(pdf._fn, "B", 10)
            pdf.cell(0, 7, "Why This Grant Matches:", ln=True)
            pdf.set_font(pdf._fn, "", 9)
            for reason in m.reasons:
                pdf.cell(5)
                pdf.cell(0, 6, f"• {reason}", ln=True)

        # Description
        if g.description:
            pdf.ln(4)
            pdf.set_font(pdf._fn, "B", 10)
            pdf.cell(0, 7, "Description:", ln=True)
            pdf.set_font(pdf._fn, "", 8)
            pdf.set_text_color(*GRAY)
            pdf.multi_cell(0, 5, g.description[:500])

        # URL
        if g.source_url:
            pdf.ln(3)
            pdf.set_font(pdf._fn, "", 8)
            pdf.set_text_color(0, 100, 200)
            pdf.cell(0, 6, g.source_url, ln=True)

    # ── Save ──────────────────────────────────────────────────
    out_dir = output_dir or settings.proposals_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^\w\s-]", "", profile_name)
    safe_name = re.sub(r"\s+", "_", safe_name)[:30]
    date_str = datetime.utcnow().strftime("%Y%m%d")
    filename = f"matching_report_{safe_name}_{date_str}.pdf"
    out_path = out_dir / filename

    pdf.output(str(out_path))
    logger.info("Matching report saved: %s", out_path)
    return out_path
