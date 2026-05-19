"""Build polished PDF files from structured content using ReportLab."""
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak, ListFlowable, ListItem
)

BRAND_DARK = colors.HexColor("#0F172A")
BRAND_ACCENT = colors.HexColor("#6366F1")
BRAND_LIGHT = colors.HexColor("#F8FAFC")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title", parent=base["Title"],
            fontSize=28, textColor=BRAND_DARK, spaceAfter=8, leading=34,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"],
            fontSize=14, textColor=BRAND_ACCENT, spaceAfter=24, leading=18,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"],
            fontSize=18, textColor=BRAND_DARK, spaceBefore=18, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"],
            fontSize=13, textColor=BRAND_ACCENT, spaceBefore=12, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"],
            fontSize=11, textColor=BRAND_DARK, leading=16, spaceAfter=8,
        ),
        "prompt_box": ParagraphStyle(
            "PromptBox", parent=base["Normal"],
            fontSize=10, textColor=BRAND_DARK, leading=15, spaceAfter=4,
            backColor=colors.HexColor("#EEF2FF"),
            borderColor=BRAND_ACCENT, borderWidth=1, borderPadding=8,
        ),
    }


def build_prompt_pack(output_path: str, data: dict[str, Any]) -> str:
    """
    data shape:
    {
      "title": str,
      "subtitle": str,
      "intro": str,
      "sections": [
        {
          "name": str,
          "description": str,
          "prompts": [{"label": str, "prompt": str, "use_case": str}, ...]
        }
      ],
      "bonus_tips": [str],
    }
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    s = _styles()
    story = []

    # Cover
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph(data["title"], s["title"]))
    story.append(Paragraph(data.get("subtitle", ""), s["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=BRAND_ACCENT))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(data.get("intro", ""), s["body"]))
    story.append(PageBreak())

    # Sections
    for section in data.get("sections", []):
        story.append(Paragraph(section["name"], s["h1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0")))
        story.append(Spacer(1, 0.1 * inch))
        if section.get("description"):
            story.append(Paragraph(section["description"], s["body"]))
        story.append(Spacer(1, 0.15 * inch))

        for i, p in enumerate(section.get("prompts", []), 1):
            story.append(Paragraph(f"{i}. {p['label']}", s["h2"]))
            story.append(Paragraph(f"<b>Use case:</b> {p['use_case']}", s["body"]))
            story.append(Paragraph(p["prompt"], s["prompt_box"]))
            story.append(Spacer(1, 0.1 * inch))

        story.append(PageBreak())

    # Bonus tips
    if data.get("bonus_tips"):
        story.append(Paragraph("Bonus Tips", s["h1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0")))
        story.append(Spacer(1, 0.1 * inch))
        items = [ListItem(Paragraph(tip, s["body"]), leftIndent=12) for tip in data["bonus_tips"]]
        story.append(ListFlowable(items, bulletType="bullet", start="•"))

    doc.build(story)
    return output_path
