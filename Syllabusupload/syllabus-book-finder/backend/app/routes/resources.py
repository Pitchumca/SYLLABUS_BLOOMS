import os
import datetime
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.template_and_resource import (
    ResourceRecord,
    StoredDocument,
    DocumentChunkModel,
    RightsVerificationLog,
    DownloadAuditLog
)
from app.models.user import User
from app.utils.auth import get_current_user_optional, require_faculty
from app.schemas.template_and_resource import (
    ResourceRecordResponse,
    LawfulAcquireRequest,
    RightsVerificationCheckResponse,
    DocumentChunkSchema
)
from app.services.lawful_acquisition_service import (
    classify_and_verify_rights,
    acquire_and_index_lawful_pdf
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resources", tags=["Lawful Resources & PDF Acquisition"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/verify-rights", response_model=RightsVerificationCheckResponse)
def check_rights_verification(
    payload: dict,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Verify lawful eligibility of a textbook / resource URL against the 10-Tier Framework.
    Rejects blocked shadow libraries and warns on commercial paywalls.
    """
    url = payload.get("source_url") or payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'source_url' parameter.")

    result = classify_and_verify_rights(url, payload)
    return result

@router.post("/acquire", response_model=ResourceRecordResponse)
def acquire_lawful_document(
    request: LawfulAcquireRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Lawfully acquire, verify magic %PDF- bytes, deduplicate via SHA-256,
    extract text page-by-page, align to syllabus units, and index into database.
    """
    user_id = current_user.id if current_user else None

    try:
        record = acquire_and_index_lawful_pdf(
            db=db,
            source_url=request.source_url,
            title=request.title,
            syllabus_id=request.syllabus_id,
            book_id=request.book_id,
            authors=request.authors,
            publisher=request.publisher,
            edition=request.edition,
            year=request.year,
            isbn=request.isbn,
            doi=request.doi,
            licence=request.licence,
            rights_statement=request.rights_statement,
            source_repository=request.source_repository,
            faculty_override=bool(request.faculty_override),
            override_justification=request.override_justification,
            user_id=user_id
        )
        return record
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Acquisition error for '{request.source_url}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to acquire lawful PDF: {str(e)}")

@router.get("/syllabus/{syllabus_id}", response_model=List[ResourceRecordResponse])
def list_syllabus_resources(
    syllabus_id: int,
    db: Session = Depends(get_db)
):
    """
    List all lawful documents acquired and indexed for a given syllabus.
    Includes rights status, chunk counts, and approval state.
    """
    records = db.query(ResourceRecord).filter(ResourceRecord.syllabus_id == syllabus_id).all()
    res = []
    for r in records:
        stored = r.stored_document
        chunks_count = len(stored.chunks) if stored else 0
        approved_units = list({c.unit_number for c in stored.chunks if c.approved_for_generation and c.unit_number} if stored else set())
        
        # Calculate overall syllabus alignment percentage
        align_avg = 0.0
        if stored and stored.chunks:
            align_avg = sum(c.alignment_score for c in stored.chunks) / len(stored.chunks)

        resp = ResourceRecordResponse.model_validate(r)
        resp.alignment_percentage = round(align_avg * 100, 1)
        resp.approved_units = approved_units
        if resp.stored_document:
            resp.stored_document.chunks_count = chunks_count
        res.append(resp)
    return res

@router.get("/{resource_id}", response_model=ResourceRecordResponse)
def get_resource_details(
    resource_id: int,
    db: Session = Depends(get_db)
):
    """Get full details of an acquired resource record."""
    rec = db.query(ResourceRecord).filter(ResourceRecord.id == resource_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Resource record not found.")
    return rec

@router.get("/{resource_id}/chunks", response_model=List[DocumentChunkSchema])
def get_resource_chunks(
    resource_id: int,
    unit_number: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Get indexed text chunks for an acquired resource, optionally filtered by syllabus unit."""
    rec = db.query(ResourceRecord).filter(ResourceRecord.id == resource_id).first()
    if not rec or not rec.stored_document:
        raise HTTPException(status_code=404, detail="Resource or stored document not found.")

    query = db.query(DocumentChunkModel).filter(DocumentChunkModel.stored_document_id == rec.stored_document.id)
    if unit_number is not None:
        query = query.filter(DocumentChunkModel.unit_number == unit_number)
    
    return query.order_by(DocumentChunkModel.page_number).all()

@router.put("/{resource_id}/approve")
def approve_resource_for_rag(
    resource_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Explicit faculty approval step before chunks can be used in RAG generation.
    Supports approving all units or a specific subset of units.
    """
    rec = db.query(ResourceRecord).filter(ResourceRecord.id == resource_id).first()
    if not rec or not rec.stored_document:
        raise HTTPException(status_code=404, detail="Resource not found.")

    approved = payload.get("approved", True)
    units_to_approve = payload.get("units") # list of int unit numbers or None for all

    chunks = db.query(DocumentChunkModel).filter(DocumentChunkModel.stored_document_id == rec.stored_document.id).all()
    updated_count = 0
    for c in chunks:
        if units_to_approve is None or c.unit_number in units_to_approve:
            c.approved_for_generation = approved
            updated_count += 1

    rec.status = "faculty_approved" if approved else "faculty_review_pending"
    db.commit()

    return {
        "resource_id": resource_id,
        "status": rec.status,
        "approved": approved,
        "updated_chunks_count": updated_count,
        "message": f"Successfully updated {updated_count} chunks for RAG generation."
    }

@router.delete("/{resource_id}")
def delete_resource_record(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Delete an acquired resource record, its stored file, and all document chunks."""
    rec = db.query(ResourceRecord).filter(ResourceRecord.id == resource_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Resource not found.")

    # Remove file on disk if stored
    if rec.stored_document and rec.stored_document.storage_path:
        file_p = rec.stored_document.storage_path
        if os.path.exists(file_p):
            try:
                os.remove(file_p)
            except Exception:
                pass

    db.delete(rec)
    db.commit()
    return {"message": "Resource and associated document chunks deleted successfully."}

@router.get("/audit/logs")
def get_download_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List recent lawful PDF download and verification audit logs."""
    logs = db.query(DownloadAuditLog).order_by(DownloadAuditLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "source_url": l.source_url,
            "http_status_code": l.http_status_code,
            "sha256_checksum": l.sha256_checksum,
            "file_size_bytes": l.file_size_bytes,
            "rights_status": l.rights_status,
            "status": l.status,
            "failure_reason": l.failure_reason,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None
        }
        for l in logs
    ]
