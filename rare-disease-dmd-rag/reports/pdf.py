"""PDF export for the comparison/insights tables and Q&A answers, shown
as "Download as PDF" buttons in the Streamlit UI. Uses fpdf2 -- pure
Python, no system dependencies (no wkhtmltopdf/Pango/Cairo to install),
which matters given how much we've cared about keeping this deployment
lightweight elsewhere.
"""
from __future__ import annotations

import pathlib

from fpdf import FPDF, FontFace

BRAND_NAVY = (12, 68, 124)  # #0C447C as RGB
# Optional: point this at your own logo image to brand the PDF header.
LOGO_PATH = pathlib.Path(__file__).parent.parent / "logo" / "brand_logo.png"

# The core Helvetica font only supports latin-1 -- real corpus text (trial
# eligibility criteria, abstracts) has stray Unicode like "≥"/"–"/"…" that
# would otherwise crash PDF generation. Map common cases to ASCII and
# replace anything else rather than pulling in a Unicode font just to
# render a handful of odd characters.
_UNICODE_REPLACEMENTS = {
    "≥": ">=", "≤": "<=", "–": "-", "—": "--",
    "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...",
}


def _sanitize(text) -> str:
    text = str(text)
    for bad, good in _UNICODE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class _ReportPDF(FPDF):
    def header(self):
        if LOGO_PATH.exists():
            try:
                self.image(str(LOGO_PATH), x=10, y=8, h=10)
                self.set_xy(10, 20)
            except Exception:
                self.set_xy(10, 10)
        else:
            self.set_xy(10, 10)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*BRAND_NAVY)
        self.cell(0, 8, _sanitize(self.title_text), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Rare Disease DMD RAG -- page {self.page_no()}", align="C")


def _new_pdf(title: str) -> _ReportPDF:
    pdf = _ReportPDF()
    pdf.title_text = title
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    return pdf


def _write_paragraph(pdf: FPDF, heading: str, text: str):
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _sanitize(heading), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _sanitize(text))
    pdf.ln(3)


def _write_table(pdf: FPDF, headers: list[str], rows: list[list[str]]):
    pdf.set_font("Helvetica", "", 8)
    with pdf.table(
        col_widths=None, text_align="LEFT", line_height=4.5,
        headings_style=FontFace(emphasis="BOLD", fill_color=(241, 239, 232)),
    ) as table:
        table.row([_sanitize(h) for h in headers])
        for row in rows:
            table.row([_sanitize(c) if c is not None else "-" for c in row])


def comparison_pdf(kind: str, label_a: str, label_b: str, rows, summary: str, caveat: str | None = None) -> bytes:
    """`rows` is a list of objects with .parameter/.value_a/.value_b/.ai_observation
    (agents.comparison.ComparisonRow) -- kept duck-typed so this doesn't
    need to import that module."""
    pdf = _new_pdf(f"{kind} Comparison: {label_a} vs {label_b}")
    _write_paragraph(pdf, "AI Summary", summary)
    if caveat:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(150, 90, 20)
        pdf.multi_cell(0, 5, _sanitize(f"Note: {caveat}"))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)
    table_rows = [[r.parameter, r.value_a, r.value_b, r.ai_observation] for r in rows]
    _write_table(pdf, ["Parameter", label_a, label_b, "AI Observation"], table_rows)
    return bytes(pdf.output())


def guidance_pdf(items: list[dict], note: str | None = None) -> bytes:
    pdf = _new_pdf("Regulatory Insights -- FDA/EMA Guidance")
    if note:
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 5, _sanitize(note))
        pdf.ln(3)
    table_rows = [
        [i["guidance"], i["agency"], i["date"], i["status"], i["impact_area"], i["ai_insight"]]
        for i in items
    ]
    _write_table(pdf, ["Guidance/Update", "Agency", "Date", "Status", "Impact Area", "AI Insight"], table_rows)
    return bytes(pdf.output())


def answer_pdf(question: str, summary: str, citations: list[dict], note: str | None = None) -> bytes:
    pdf = _new_pdf("Grounded Answer")
    _write_paragraph(pdf, "Question", question)
    _write_paragraph(pdf, "Answer", summary)
    if note:
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 5, _sanitize(note))
        pdf.ln(3)
    seen = set()
    rows = []
    for c in citations:
        if c["citation"] in seen:
            continue
        seen.add(c["citation"])
        rows.append([c["citation"], c["source_type"], c["url"] or "-"])
    _write_table(pdf, ["Citation", "Source Type", "URL"], rows)
    return bytes(pdf.output())
