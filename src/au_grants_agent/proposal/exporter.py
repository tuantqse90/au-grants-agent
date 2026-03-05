"""Export proposals to Markdown, DOCX, and PDF formats."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

from au_grants_agent.config import settings
from au_grants_agent.models import Grant, Proposal
from au_grants_agent.utils.logger import get_logger

logger = get_logger()
console = Console()


def _sanitize_filename(text: str, max_len: int = 40) -> str:
    """Create a filesystem-safe short name from text."""
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "_", text).strip("_")
    return text[:max_len]


def _get_output_dir(base_dir: Optional[Path] = None) -> Path:
    """Get or create the date-based output directory."""
    base = base_dir or settings.proposals_dir
    date_dir = base / datetime.utcnow().strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    return date_dir


def _build_filename(grant: Grant, ext: str) -> str:
    """Build standard filename: {go_id}_{short_title}_{date}.{ext}"""
    go_part = grant.go_id or grant.id[:8]
    title_part = _sanitize_filename(grant.title)
    date_part = datetime.utcnow().strftime("%Y%m%d")
    return f"{go_part}_{title_part}_{date_part}.{ext}"


def _find_unicode_font() -> Optional[str]:
    """Find a TTF font that supports Unicode (Vietnamese) on this system."""
    candidates = [
        # macOS
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        # Windows
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialuni.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            logger.debug("Found Unicode font: %s", path)
            return path
    return None


def _find_unicode_font_bold() -> Optional[str]:
    """Find a bold variant of a Unicode TTF font."""
    candidates = [
        "/Library/Fonts/Arial Unicode.ttf",  # macOS — same file, no bold variant
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return None


class ProposalExporter:
    """Export generated proposals to multiple formats."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir

    def _full_content(self, proposal: Proposal) -> str:
        """Combine English content and Vietnamese summary."""
        parts = []
        if proposal.content_en:
            parts.append(proposal.content_en)
        if proposal.summary_vi:
            parts.append("---\n\n## Tóm tắt Tiếng Việt\n\n" + proposal.summary_vi)
        return "\n\n".join(parts)

    # ── Markdown ────────────────────────────────────────────────

    def export_markdown(self, grant: Grant, proposal: Proposal) -> Path:
        """Export proposal as Markdown with YAML frontmatter."""
        out_dir = _get_output_dir(self.output_dir)
        filename = _build_filename(grant, "md")
        filepath = out_dir / filename

        frontmatter = f"""---
title: "{grant.title}"
grant_id: "{grant.id}"
go_id: "{grant.go_id or 'N/A'}"
agency: "{grant.agency or 'N/A'}"
organisation: "{proposal.org_name or 'N/A'}"
generated: "{proposal.generated_at}"
model: "{proposal.model}"
---

"""
        filepath.write_text(frontmatter + self._full_content(proposal), encoding="utf-8")
        logger.info("Exported MD: %s", filepath)
        return filepath

    # ── DOCX ────────────────────────────────────────────────────

    def export_docx(self, grant: Grant, proposal: Proposal) -> Path:
        """Export proposal as DOCX with professional formatting."""
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt

        out_dir = _get_output_dir(self.output_dir)
        filename = _build_filename(grant, "docx")
        filepath = out_dir / filename

        doc = Document()

        # Default font
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Calibri"
        font.size = Pt(12)

        # Title page
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_para.add_run(grant.title)
        title_run.bold = True
        title_run.font.size = Pt(24)

        doc.add_paragraph()  # spacer

        meta_lines = [
            f"Grant Program: {grant.agency or 'Australian Government'}",
            f"Applicant Organisation: {proposal.org_name or 'N/A'}",
            f"Date: {datetime.utcnow().strftime('%d %B %Y')}",
            f"Grant ID: {grant.go_id or grant.id[:8]}",
        ]
        for line in meta_lines:
            p = doc.add_paragraph(line)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_page_break()

        # Content — parse markdown-like sections
        content = self._full_content(proposal)
        for line in content.split("\n"):
            line = line.rstrip()
            if line.startswith("# "):
                doc.add_heading(line[2:], level=1)
            elif line.startswith("## "):
                doc.add_heading(line[3:], level=2)
            elif line.startswith("### "):
                doc.add_heading(line[4:], level=3)
            elif line.startswith("---"):
                doc.add_page_break()
            elif line.startswith("|"):
                doc.add_paragraph(line, style="Normal")
            elif line.strip() == "":
                doc.add_paragraph()
            else:
                p = doc.add_paragraph()
                parts = re.split(r"(\*\*.*?\*\*)", line)
                for part in parts:
                    if part.startswith("**") and part.endswith("**"):
                        run = p.add_run(part[2:-2])
                        run.bold = True
                    else:
                        p.add_run(part)

        # Page numbers
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement

        section = doc.sections[-1]
        footer = section.footer
        footer.is_linked_to_previous = False
        p = footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fld = OxmlElement("w:fldSimple")
        fld.set(qn("w:instr"), "PAGE")
        p._element.append(fld)

        doc.save(str(filepath))
        logger.info("Exported DOCX: %s", filepath)
        return filepath

    # ── PDF ──────────────────────────────────────────────────────

    def export_pdf(self, grant: Grant, proposal: Proposal) -> Path:
        """Export proposal as PDF with full Unicode support (Vietnamese)."""
        from fpdf import FPDF

        out_dir = _get_output_dir(self.output_dir)
        filename = _build_filename(grant, "pdf")
        filepath = out_dir / filename

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)

        # ── Load Unicode font ──
        font_path = _find_unicode_font()
        font_bold_path = _find_unicode_font_bold()
        uni_font = None

        if font_path:
            try:
                pdf.add_font("UniFont", "", font_path, uni=True)
                if font_bold_path:
                    pdf.add_font("UniFont", "B", font_bold_path, uni=True)
                else:
                    # Use regular as bold fallback
                    pdf.add_font("UniFont", "B", font_path, uni=True)
                uni_font = "UniFont"
                logger.info("PDF: Using Unicode font from %s", font_path)
            except Exception as e:
                logger.warning("PDF: Failed to load Unicode font: %s", e)
                uni_font = None

        def set_font(style: str = "", size: int = 11):
            """Set font with Unicode fallback."""
            if uni_font:
                pdf.set_font(uni_font, style, size)
            else:
                pdf.set_font("Helvetica", style, size)

        def safe_write(text: str, h: int = 6):
            """Write text, resetting X and handling errors gracefully."""
            pdf.set_x(pdf.l_margin)  # always reset to left margin
            try:
                pdf.multi_cell(0, h, text)
            except UnicodeEncodeError:
                safe = text.encode("latin-1", errors="replace").decode("latin-1")
                pdf.multi_cell(0, h, safe)
            except Exception:
                # Skip lines that can't be rendered
                pdf.ln(h)

        # ── Title Page ──
        pdf.add_page()
        pdf.ln(40)
        set_font("B", 22)
        safe_write(grant.title)
        pdf.ln(15)

        set_font("", 13)
        meta = [
            f"Agency: {grant.agency or 'Australian Government'}",
            f"Organisation: {proposal.org_name or 'N/A'}",
            f"Date: {datetime.utcnow().strftime('%d %B %Y')}",
            f"Grant ID: {grant.go_id or grant.id[:8]}",
        ]
        for line in meta:
            pdf.cell(0, 9, line, ln=True, align="C")

        # Green line separator
        pdf.ln(10)
        pdf.set_draw_color(0, 255, 136)
        pdf.set_line_width(0.8)
        pdf.line(30, pdf.get_y(), 180, pdf.get_y())

        # ── Content Pages ──
        pdf.add_page()
        content = self._full_content(proposal)

        # Track if we're in Vietnamese section for logging
        in_vi_section = False

        for line in content.split("\n"):
            line = line.rstrip()

            # Check page space
            if pdf.get_y() > 270:
                pdf.add_page()

            # Headings
            if line.startswith("### "):
                pdf.ln(3)
                set_font("B", 12)
                safe_write(line[4:])
                pdf.ln(1)
            elif line.startswith("## "):
                pdf.ln(4)
                set_font("B", 14)
                # Detect Vietnamese section
                if "Tiếng Việt" in line or "Tóm tắt" in line:
                    in_vi_section = True
                safe_write(line[3:])
                pdf.ln(2)
            elif line.startswith("# "):
                pdf.ln(5)
                set_font("B", 16)
                safe_write(line[2:])
                pdf.ln(3)
            elif line.startswith("**") and line.endswith("**"):
                # Full bold line
                pdf.ln(2)
                set_font("B", 11)
                safe_write(line.strip("*"))
                set_font("", 11)
            elif line.startswith("---"):
                # Horizontal rule
                pdf.ln(5)
                pdf.set_draw_color(0, 255, 136)
                pdf.set_line_width(0.5)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(5)
            elif line.startswith("|"):
                # Table row — render as compact text
                set_font("", 8)
                clean = line.replace("|", " | ").strip().strip("|").strip()
                # Skip separator rows (----, ====, ::::)
                if clean and not all(c in "-= :| " for c in clean):
                    safe_write(clean)
            elif line.strip() == "":
                pdf.ln(3)
            elif line.startswith("*   ") or line.startswith("- ") or line.startswith("* "):
                # Bullet point
                set_font("", 11)
                bullet_text = line.lstrip("*- ").strip()
                bullet_text = re.sub(r"\*\*(.*?)\*\*", r"\1", bullet_text)
                safe_write(f"  \u2022 {bullet_text}")
            elif line.startswith("    "):
                # Indented / sub-bullet
                set_font("", 10)
                clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line.strip().lstrip("*- "))
                safe_write(f"      - {clean}")
            else:
                # Regular paragraph
                set_font("", 11)
                clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
                safe_write(clean)

        # ── Page Numbers ──
        total_pages = pdf.pages_count
        for i in range(1, total_pages + 1):
            pdf.page = i
            pdf.set_y(-15)
            if uni_font:
                pdf.set_font(uni_font, "", 8)
            else:
                pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 10, f"Page {i} of {total_pages}", align="C")

        pdf.output(str(filepath))
        logger.info("Exported PDF: %s", filepath)
        console.print(f"  [#00ff88]PDF saved: {filepath}[/#00ff88]")
        return filepath

    # ── Export All ───────────────────────────────────────────────

    def export_all(
        self, grant: Grant, proposal: Proposal, formats: str = "all"
    ) -> list[Path]:
        """Export proposal in specified formats. Returns list of created file paths."""
        paths = []
        fmt = formats.lower()

        if fmt in ("all", "md"):
            paths.append(self.export_markdown(grant, proposal))

        if fmt in ("all", "docx"):
            try:
                paths.append(self.export_docx(grant, proposal))
            except Exception as e:
                logger.error("DOCX export failed: %s", e)
                console.print(f"[red]DOCX export failed: {e}[/red]")

        if fmt in ("all", "pdf"):
            try:
                paths.append(self.export_pdf(grant, proposal))
            except Exception as e:
                logger.error("PDF export failed: %s", e)
                console.print(f"[red]PDF export failed: {e}[/red]")

        return paths
