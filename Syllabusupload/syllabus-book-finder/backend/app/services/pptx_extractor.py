import os
import re
from pathlib import Path
from typing import Dict, List, Any
import pptx

class PPTXExtractionResult:
    def __init__(self, text: str, slide_count: int, slides_data: List[Dict[str, Any]]):
        self.text = text
        self.slide_count = slide_count
        self.slides_data = slides_data

def extract_presentation_text(file_path: Path) -> PPTXExtractionResult:
    """
    Extract text content from presentation file (.pptx or .ppt).
    Extracts slide titles, body bullet points, table text, and speaker notes.
    """
    ext = file_path.suffix.lower()
    
    if ext == ".pptx":
        return _extract_from_pptx(file_path)
    elif ext == ".ppt":
        return _extract_from_legacy_ppt(file_path)
    else:
        raise ValueError(f"Unsupported presentation extension '{ext}'. Expected .pptx or .ppt")

def _extract_from_pptx(file_path: Path) -> PPTXExtractionResult:
    prs = pptx.Presentation(str(file_path))
    slide_count = len(prs.slides)
    all_text_blocks = []
    slides_data = []

    for idx, slide in enumerate(prs.slides, start=1):
        slide_title = ""
        slide_lines = []

        # Check for title
        if slide.shapes.title and slide.shapes.title.text:
            slide_title = slide.shapes.title.text.strip()
            slide_lines.append(f"Slide {idx} Title: {slide_title}")

        # Extract shapes
        for shape in slide.shapes:
            if shape == slide.shapes.title:
                continue
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text and text != slide_title:
                        slide_lines.append(text)
            elif shape.has_table:
                for row in shape.table.rows:
                    row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if row_cells:
                        slide_lines.append(" | ".join(row_cells))

        # Check notes slide
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()
            if notes_text:
                slide_lines.append(f"[Speaker Notes: {notes_text}]")

        slide_full_text = "\n".join(slide_lines)
        if slide_full_text:
            all_text_blocks.append(f"--- Slide {idx} {f': {slide_title}' if slide_title else ''} ---\n{slide_full_text}")

        slides_data.append({
            "slide_number": idx,
            "title": slide_title,
            "text": slide_full_text
        })

    combined_text = "\n\n".join(all_text_blocks)
    return PPTXExtractionResult(
        text=combined_text,
        slide_count=slide_count,
        slides_data=slides_data
    )

def _extract_from_legacy_ppt(file_path: Path) -> PPTXExtractionResult:
    """Fallback text extraction for binary .ppt files using regex string extraction."""
    with open(file_path, "rb") as f:
        raw_bytes = f.read()
    
    # Extract printable unicode and ASCII chunks
    ascii_strings = re.findall(rb'[\x20-\x7E]{4,}', raw_bytes)
    extracted_lines = []
    for s in ascii_strings:
        try:
            line = s.decode("ascii", errors="ignore").strip()
            if len(line) > 5 and not line.startswith("Microsoft") and not line.startswith("Font"):
                extracted_lines.append(line)
        except Exception:
            continue

    text = "\n".join(extracted_lines[:500])
    return PPTXExtractionResult(
        text=text,
        slide_count=1,
        slides_data=[{"slide_number": 1, "title": "Legacy Presentation", "text": text}]
    )
