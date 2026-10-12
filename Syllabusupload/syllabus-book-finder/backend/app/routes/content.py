import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, Form
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.content_file import ContentFile
from app.models.syllabus import Syllabus
from app.models.user import User
from app.schemas.question_paper import ContentFileResponse, CourseOutcomeModel
from app.utils.auth import get_current_user, require_faculty
from app.utils.security import (
    sanitize_filename,
    generate_safe_stored_filename,
    validate_uploaded_file,
    validate_path_traversal
)
from app.services.content_extractor import extract_document_content
from app.services.alignment_engine import align_content_file_to_syllabus
from app.services.co_extractor import extract_course_outcomes, extract_syllabus_units

router = APIRouter(prefix="/content", tags=["Course Content & PPT Ingestion"])

@router.post("/upload", response_model=ContentFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_course_content(
    file: UploadFile = File(...),
    syllabus_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Upload course lecture slides (PPTX, PPT), lecture notes (PDF, DOCX), or text notes (TXT).
    Preserves slide/page boundaries, performs OCR detection, and aligns with syllabus.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = Path(file.filename).suffix.lower()
    allowed = {".pptx", ".ppt", ".pdf", ".docx", ".txt"}
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file format '{ext}'. Allowed content formats: PPTX, PPT, PDF, DOCX, TXT."
        )

    clean_original_name = sanitize_filename(file.filename)
    stored_name = generate_safe_stored_filename(clean_original_name)
    stored_path = settings.UPLOAD_DIR / stored_name
    validate_path_traversal(stored_path, settings.UPLOAD_DIR)

    # Read header
    header_chunk = await file.read(1024)
    if not header_chunk:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

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

    validate_uploaded_file(file, header_chunk, file_size, allowed_exts=allowed)

    # Universal Document Content Extraction
    chunks_data = []
    extraction_warnings = []
    extraction_status = "extracted"
    extracted_text = ""
    slide_or_page_count = 0

    try:
        ext_res = extract_document_content(stored_path)
        extracted_text = ext_res.text
        slide_or_page_count = ext_res.slide_or_page_count
        chunks_data = ext_res.chunks
        extraction_status = ext_res.status
        extraction_warnings = ext_res.warnings or []
    except Exception as e:
        extracted_text = f"Content text extraction note: {str(e)}"
        extraction_status = "failed"
        extraction_warnings = [str(e)]

    # Compute Syllabus Alignment if syllabus_id is present
    alignments_json = None
    if syllabus_id and chunks_data:
        syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
        if syllabus and syllabus.extracted_text:
            syl_units = extract_syllabus_units(syllabus.extracted_text)
            syl_cos = extract_course_outcomes(syllabus.extracted_text)
            try:
                align_res = align_content_file_to_syllabus(
                    chunks=chunks_data,
                    syllabus_units=syl_units,
                    course_outcomes=syl_cos,
                    filename=clean_original_name
                )
                alignments_json = json.dumps(align_res)
            except Exception as ae:
                extraction_warnings.append(f"Alignment error: {str(ae)}")

    content_record = ContentFile(
        syllabus_id=syllabus_id,
        faculty_id=current_user.id,
        original_filename=clean_original_name,
        stored_filename=stored_name,
        file_type=ext.lstrip("."),
        file_size_bytes=file_size,
        extracted_text=extracted_text,
        slide_or_page_count=slide_or_page_count,
        extraction_status=extraction_status,
        extraction_warnings=json.dumps(extraction_warnings) if extraction_warnings else None,
        chunks_json=json.dumps(chunks_data) if chunks_data else None,
        alignments_json=alignments_json
    )
    db.add(content_record)
    db.commit()
    db.refresh(content_record)
    return content_record

@router.get("/syllabus/{syllabus_id}", response_model=List[ContentFileResponse])
def get_syllabus_content_files(
    syllabus_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Retrieve all uploaded content files (PPT/PDF) for a syllabus."""
    return db.query(ContentFile).filter(ContentFile.syllabus_id == syllabus_id).all()

@router.get("/syllabus/{syllabus_id}/outcomes", response_model=List[CourseOutcomeModel])
def get_syllabus_course_outcomes(
    syllabus_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Extract and return Course Outcomes (CO1..CO6) and Units from syllabus and content.
    """
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus record not found.")

    syllabus_text = syllabus.extracted_text or ""
    
    # Also include any content files text
    content_files = db.query(ContentFile).filter(ContentFile.syllabus_id == syllabus_id).all()
    extra_text = "\n".join([cf.extracted_text or "" for cf in content_files])

    outcomes = extract_course_outcomes(f"{syllabus_text}\n{extra_text}")
    return outcomes

@router.get("/syllabus/{syllabus_id}/units")
def get_syllabus_units(
    syllabus_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Extract units and modules from syllabus."""
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus record not found.")

    return extract_syllabus_units(syllabus.extracted_text or "")

@router.get("/file/{file_id}/preview")
def get_file_chunks_preview(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Returns slide/page chunks preview with extraction status, OCR warnings,
    and structured excerpts for previewing uploaded lecture notes/slides.
    """
    cf = db.query(ContentFile).filter(ContentFile.id == file_id).first()
    if not cf:
        raise HTTPException(status_code=404, detail="Content file not found.")

    chunks = []
    if cf.chunks_json:
        try:
            chunks = json.loads(cf.chunks_json)
        except Exception:
            chunks = []

    warnings = []
    if cf.extraction_warnings:
        try:
            warnings = json.loads(cf.extraction_warnings)
        except Exception:
            warnings = [cf.extraction_warnings]

    return {
        "file_id": cf.id,
        "filename": cf.original_filename,
        "file_type": cf.file_type,
        "slide_or_page_count": cf.slide_or_page_count,
        "extraction_status": cf.extraction_status or "extracted",
        "extraction_warnings": warnings,
        "total_chunks": len(chunks),
        "chunks": chunks
    }

@router.get("/syllabus/{syllabus_id}/alignments")
def get_syllabus_alignments(
    syllabus_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Retrieve aggregated alignments of all uploaded content files against the syllabus units.
    Categorized into Strong alignment, Review recommended, and Unmatched.
    """
    content_files = db.query(ContentFile).filter(ContentFile.syllabus_id == syllabus_id).all()
    all_alignments = []
    total_strong = 0
    total_review = 0
    total_unmatched = 0
    all_unmatched_chunks = []

    for cf in content_files:
        if cf.alignments_json:
            try:
                data = json.loads(cf.alignments_json)
                aligns = data.get("alignments", [])
                all_alignments.extend(aligns)
                total_strong += data.get("strong_count", 0)
                total_review += data.get("review_count", 0)
                total_unmatched += data.get("unmatched_count", 0)
                all_unmatched_chunks.extend(data.get("unmatched_chunks", []))
            except Exception:
                pass
        elif cf.chunks_json:
            # On-the-fly alignment if not yet cached
            syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
            if syllabus and syllabus.extracted_text:
                try:
                    chunks = json.loads(cf.chunks_json)
                    syl_units = extract_syllabus_units(syllabus.extracted_text)
                    syl_cos = extract_course_outcomes(syllabus.extracted_text)
                    align_res = align_content_file_to_syllabus(chunks, syl_units, syl_cos, cf.original_filename)
                    cf.alignments_json = json.dumps(align_res)
                    db.commit()

                    all_alignments.extend(align_res.get("alignments", []))
                    total_strong += align_res.get("strong_count", 0)
                    total_review += align_res.get("review_count", 0)
                    total_unmatched += align_res.get("unmatched_count", 0)
                    all_unmatched_chunks.extend(align_res.get("unmatched_chunks", []))
                except Exception:
                    pass

    return {
        "syllabus_id": syllabus_id,
        "total_files": len(content_files),
        "total_chunks": len(all_alignments),
        "strong_count": total_strong,
        "review_count": total_review,
        "unmatched_count": total_unmatched,
        "alignments": all_alignments,
        "unmatched_chunks": all_unmatched_chunks
    }

@router.delete("/file/{file_id}")
def delete_content_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Delete uploaded content file and remove from disk."""
    cf = db.query(ContentFile).filter(ContentFile.id == file_id).first()
    if not cf:
        raise HTTPException(status_code=404, detail="Content file not found.")

    if cf.stored_filename:
        file_path = settings.UPLOAD_DIR / cf.stored_filename
        file_path.unlink(missing_ok=True)

    db.delete(cf)
    db.commit()
    return {"message": "Content file deleted successfully."}
