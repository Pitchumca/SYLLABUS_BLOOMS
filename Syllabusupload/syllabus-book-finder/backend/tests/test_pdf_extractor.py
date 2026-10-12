import pytest
from pathlib import Path
from app.services.pdf_extractor import extract_pdf_text, extract_text_with_pymupdf

def test_extract_sample_pdf(sample_pdf_path):
    assert sample_pdf_path.is_file(), "Sample PDF must exist"
    result = extract_pdf_text(sample_pdf_path)
    
    assert result.page_count >= 1
    assert result.character_count > 200
    assert "TEXT BOOKS" in result.text.upper() or "ALGORITHMS" in result.text.upper()
    assert result.method in ("PyMuPDF", "pdfplumber")

def test_extract_text_with_pymupdf_direct(sample_pdf_path):
    text, pages = extract_text_with_pymupdf(sample_pdf_path)
    assert pages >= 1
    assert len(text) > 200
    assert "Introduction to Algorithms" in text or "Cormen" in text
