import shutil
import logging
from pathlib import Path
from typing import Tuple
import pytesseract
from app.config import settings

logger = logging.getLogger(__name__)

def is_tesseract_available() -> bool:
    """Check if Tesseract OCR binary is installed and reachable."""
    if settings.TESSERACT_CMD and Path(settings.TESSERACT_CMD).is_file():
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        return True
    
    # Check default system PATH
    found = shutil.which("tesseract")
    if found:
        pytesseract.pytesseract.tesseract_cmd = found
        return True
    
    # Common Windows default locations
    common_windows_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\HP\AppData\Local\Tesseract-OCR\tesseract.exe"
    ]
    for p in common_windows_paths:
        if Path(p).is_file():
            pytesseract.pytesseract.tesseract_cmd = p
            return True
            
    return False

def run_ocr_on_pdf(file_path: Path, max_pages: int = 20) -> Tuple[str, int, str]:
    """
    Perform OCR on a PDF file by converting pages to images and processing with pytesseract.
    Returns (extracted_text, page_count, status_message).
    """
    if not is_tesseract_available():
        return (
            "", 
            0, 
            "Tesseract OCR binary not found on the server host. Please install Tesseract OCR or enter the syllabus text manually in the text editor below."
        )

    try:
        from pdf2image import convert_from_path
        
        # Convert PDF pages to PIL images
        images = convert_from_path(str(file_path), first_page=1, last_page=max_pages)
        page_count = len(images)
        full_text = []

        for i, img in enumerate(images):
            text = pytesseract.image_to_string(img, lang="eng")
            if text.strip():
                full_text.append(f"--- Page {i + 1} (OCR) ---\n{text.strip()}\n")

        extracted = "\n".join(full_text).strip()
        return extracted, page_count, "OCR completed successfully."

    except Exception as e:
        logger.error(f"Error running OCR on {file_path}: {e}")
        return (
            "",
            0,
            f"OCR processing encountered an issue: {str(e)}. You can review or paste the syllabus text directly into the syllabus editor."
        )
