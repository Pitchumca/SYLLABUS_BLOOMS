import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.syllabus import Syllabus
from app.schemas.syllabus import SyllabusResponse, SyllabusUpdate
from app.utils.security import (
    sanitize_filename,
    generate_safe_stored_filename,
    validate_uploaded_file,
    validate_path_traversal,
    sanitize_input_text
)
from app.services.pdf_extractor import extract_pdf_text
from app.services.ocr_service import run_ocr_on_pdf, is_tesseract_available

router = APIRouter(prefix="/upload", tags=["PDF Upload & Text Extraction"])

@router.post("", response_model=SyllabusResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SyllabusResponse, status_code=status.HTTP_201_CREATED)
async def upload_syllabus_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a syllabus PDF (up to 25MB).
    Validates file headers and MIME, extracts text using PyMuPDF (or pdfplumber fallback),
    and creates a new Syllabus record in the database.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    clean_original_name = sanitize_filename(file.filename)
    stored_name = generate_safe_stored_filename(clean_original_name)
    stored_path = settings.UPLOAD_DIR / stored_name
    validate_path_traversal(stored_path, settings.UPLOAD_DIR)

    # Read header bytes and calculate size
    header_chunk = await file.read(1024)
    if not header_chunk:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Write file safely to disk
    file_size = len(header_chunk)
    try:
        with open(stored_path, "wb") as f:
            f.write(header_chunk)
            while chunk := await file.read(64 * 1024):
                file_size += len(chunk)
                if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
                    f.close()
                    stored_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to write file to disk: {e}")

    # Validate file type and PDF signature
    validate_uploaded_file(file, header_chunk, file_size)

    # Extract text with PyMuPDF / pdfplumber
    extraction_result = extract_pdf_text(stored_path)

    # Save to database
    syllabus = Syllabus(
        original_filename=clean_original_name,
        stored_filename=stored_name,
        file_size_bytes=file_size,
        page_count=extraction_result.page_count,
        extracted_text=extraction_result.text,
        extraction_method=extraction_result.method,
        status="uploaded"
    )
    db.add(syllabus)
    db.commit()
    db.refresh(syllabus)

    return syllabus

@router.post("/sample", response_model=SyllabusResponse, status_code=status.HTTP_201_CREATED)
def load_sample_syllabus(db: Session = Depends(get_db)):
    """Load the built-in Computer Science sample syllabus PDF."""
    sample_pdf = settings.BASE_DIR / "sample_data" / "sample_syllabus_cs.pdf"
    if not sample_pdf.is_file():
        raise HTTPException(status_code=404, detail="Sample syllabus file not found.")

    stored_name = generate_safe_stored_filename("sample_syllabus_cs.pdf")
    stored_path = settings.UPLOAD_DIR / stored_name
    shutil.copyfile(sample_pdf, stored_path)

    extraction_result = extract_pdf_text(stored_path)
    file_size = stored_path.stat().st_size

    syllabus = Syllabus(
        original_filename="Advanced_Data_Structures_21CS42.pdf",
        stored_filename=stored_name,
        file_size_bytes=file_size,
        page_count=extraction_result.page_count,
        extracted_text=extraction_result.text,
        extraction_method=extraction_result.method,
        status="uploaded"
    )
    db.add(syllabus)
    db.commit()
    db.refresh(syllabus)
    return syllabus

@router.post("/ocr/{syllabus_id}", response_model=SyllabusResponse)
def trigger_ocr_extraction(syllabus_id: int, db: Session = Depends(get_db)):
    """
    Run Tesseract OCR as a fallback on an existing uploaded syllabus PDF.
    Updates the extracted text in the database.
    """
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus record not found.")

    file_path = settings.UPLOAD_DIR / syllabus.stored_filename
    validate_path_traversal(file_path, settings.UPLOAD_DIR)

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Uploaded file is missing from storage.")

    ocr_text, pages, message = run_ocr_on_pdf(file_path)
    if not ocr_text:
        raise HTTPException(status_code=400, detail=message)

    syllabus.extracted_text = ocr_text
    syllabus.extraction_method = "Tesseract OCR"
    syllabus.page_count = max(syllabus.page_count, pages)
    db.commit()
    db.refresh(syllabus)

    return syllabus

@router.get("/syllabuses", response_model=List[SyllabusResponse])
def list_syllabuses(limit: int = 10, db: Session = Depends(get_db)):
    """List recently uploaded syllabuses."""
    return db.query(Syllabus).order_by(Syllabus.created_at.desc()).limit(limit).all()

@router.get("/syllabus/{syllabus_id}", response_model=SyllabusResponse)
def get_syllabus(syllabus_id: int, db: Session = Depends(get_db)):
    """Get single syllabus details by ID."""
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")
    return syllabus

@router.put("/syllabus/{syllabus_id}", response_model=SyllabusResponse)
def update_syllabus_text(
    syllabus_id: int,
    payload: SyllabusUpdate,
    db: Session = Depends(get_db)
):
    """Update editable syllabus text manually in the UI."""
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")

    if payload.extracted_text is not None:
        syllabus.extracted_text = sanitize_input_text(payload.extracted_text)
    if payload.status is not None:
        syllabus.status = payload.status
    if payload.extraction_method is not None:
        syllabus.extraction_method = payload.extraction_method

    db.commit()
    db.refresh(syllabus)
    return syllabus
