import logging
from pathlib import Path
from typing import Tuple, Optional
import fitz  # PyMuPDF
import pdfplumber

logger = logging.getLogger(__name__)

class PDFExtractionResult:
    def __init__(self, text: str, page_count: int, method: str, character_count: int, is_scanned_likely: bool):
        self.text = text
        self.page_count = page_count
        self.method = method
        self.character_count = character_count
        self.is_scanned_likely = is_scanned_likely

def extract_text_with_pymupdf(file_path: Path) -> Tuple[str, int]:
    """Extract text and page count using PyMuPDF (fitz)."""
    full_text = []
    doc = fitz.open(str(file_path))
    page_count = len(doc)
    
    for page_num in range(page_count):
        page = doc[page_num]
        # Text extraction with reading order preserved
        page_text = page.get_text("text")
        if page_text:
            full_text.append(f"--- Page {page_num + 1} ---\n{page_text.strip()}\n")
            
    doc.close()
    return "\n".join(full_text).strip(), page_count

def extract_text_with_pdfplumber(file_path: Path) -> Tuple[str, int]:
    """Fallback text extraction using pdfplumber."""
    full_text = []
    with pdfplumber.open(str(file_path)) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text(layout=True) or page.extract_text()
            if page_text:
                full_text.append(f"--- Page {i + 1} ---\n{page_text.strip()}\n")
    return "\n".join(full_text).strip(), page_count

def extract_pdf_text(file_path: Path) -> PDFExtractionResult:
    """
    Main extraction pipeline:
    1. Try PyMuPDF first.
    2. If text is sparse (< 100 characters across document) or fails, try pdfplumber.
    3. Detect if the document is likely scanned / image-only.
    """
    text = ""
    page_count = 0
    method = "PyMuPDF"
    
    try:
        text, page_count = extract_text_with_pymupdf(file_path)
    except Exception as e:
        logger.warning(f"PyMuPDF extraction failed on {file_path}: {e}. Falling back to pdfplumber.")
        text = ""

    # If PyMuPDF returned almost no text, attempt pdfplumber fallback
    if len(text.strip()) < 100:
        try:
            fallback_text, fallback_pages = extract_text_with_pdfplumber(file_path)
            if len(fallback_text.strip()) > len(text.strip()):
                text = fallback_text
                page_count = max(page_count, fallback_pages)
                method = "pdfplumber"
        except Exception as e:
            logger.warning(f"pdfplumber fallback also failed on {file_path}: {e}")

    char_count = len(text.strip())
    # If text is extremely short relative to page count, it's likely a scanned PDF
    is_scanned = (char_count < 150 * max(1, page_count))

    return PDFExtractionResult(
        text=text,
        page_count=page_count,
        method=method,
        character_count=char_count,
        is_scanned_likely=is_scanned
    )
