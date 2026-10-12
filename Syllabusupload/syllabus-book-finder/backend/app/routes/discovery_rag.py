import os
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.config import settings
from app.models.syllabus import Syllabus
from app.models.book import Book
from app.models.discovery_rag import (
    BookMetadata,
    BookAuthor,
    BookSource,
    BookFile,
    DownloadJobModel,
    ExtractionJob,
    RAGDocument,
    RAGChunk,
    CourseResource,
    ResourceVerificationLog
)
from app.models.student import Course
from app.schemas.discovery import (
    BookMetadataStructuredSchema,
    ConsolidatedBookSchema,
    CandidateSourceRecord,
    PreValidationResultSchema,
    SyllabusCoverageRowSchema,
    BookMetadataUpdateRequest
)
from app.services.book_parser import detect_and_parse_books_structured
from app.services.bibliography_parser import (
    normalize_publisher,
    normalize_edition,
    normalize_isbns,
    clean_citation_punctuation,
    format_isbn_display
)
from app.services.search_service import (
    search_multi_source_and_consolidate,
    search_single_book_sources
)
from app.services.verification_service import (
    pre_validate_candidate_url,
    OUTCOME_VERIFIED,
    FRIENDLY_ERROR_MESSAGE
)
from app.services.download_job_service import (
    create_job,
    get_job,
    cancel_job,
    retry_job,
    execute_auto_download_and_indexing_pipeline,
    JOB_STATE_SEARCHING,
    JOB_STATE_COMPLETED,
    JOB_STATE_FAILED,
    JOB_STATE_CANCELLED
)
from app.services.rag_indexer_service import (
    process_book_file_for_rag,
    generate_syllabus_book_alignment_matrix,
    query_rag_chunks_for_topic,
    remove_book_from_rag_index,
    reindex_book,
    resolve_course_storage_dirs
)
from app.utils.security import validate_path_traversal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discovery", tags=["Book Discovery & RAG"])

@router.post("/parse")
def parse_syllabus_resources(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Extract textbooks and reference books separately into structured bibliographies.
    Avoids naive comma splitting; captures given/family names, canonical publishers,
    standardized editions, and confidence metrics.
    """
    syllabus_id = payload.get("syllabus_id")
    custom_text = payload.get("custom_text")

    if not syllabus_id and not custom_text:
        raise HTTPException(status_code=400, detail="Either syllabus_id or custom_text is required.")

    text_to_parse = custom_text or ""
    if syllabus_id:
        syl = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
        if not syl:
            raise HTTPException(status_code=404, detail="Syllabus not found.")
        if not text_to_parse:
            text_to_parse = syl.extracted_text or ""

    if not text_to_parse.strip():
        raise HTTPException(status_code=400, detail="No syllabus content available to parse.")

    # Run robust section & bibliographic parser
    parsed_structured = detect_and_parse_books_structured(text_to_parse)

    textbooks = []
    reference_books = []
    created_metadata_records = []

    # Clean existing BookMetadata for this syllabus to avoid duplicate stacking
    if syllabus_id:
        existing_meta = db.query(BookMetadata).filter(BookMetadata.syllabus_id == syllabus_id).all()
        for em in existing_meta:
            db.delete(em)
        db.commit()

    for item in parsed_structured:
        r_type = item.get("resource_type", "TEXTBOOK").upper()
        confidence = item.get("metadata_confidence", 85.0)

        # Create BookMetadata
        b_meta = BookMetadata(
            syllabus_id=syllabus_id,
            resource_type=r_type,
            book_title=item.get("book_title", "Untitled Book"),
            subtitle=item.get("subtitle"),
            publisher=item.get("publisher", "Not available"),
            edition=item.get("edition", "Not available"),
            publication_year=str(item.get("publication_year")) if item.get("publication_year") else "Not available",
            volume=item.get("volume"),
            doi=item.get("doi"),
            isbn_10=item.get("isbn_10"),
            isbn_13=item.get("isbn_13"),
            original_citation=item.get("original_citation"),
            metadata_confidence=confidence,
            is_reviewed=False
        )
        db.add(b_meta)
        db.flush()

        # Add authors
        for idx, author_dict in enumerate(item.get("authors", [])):
            author_obj = BookAuthor(
                book_metadata_id=b_meta.id,
                given_name=author_dict.get("given_name"),
                family_name=author_dict.get("family_name"),
                display_name=author_dict.get("display_name", "Author"),
                role=author_dict.get("role", "author"),
                order_index=idx
            )
            db.add(author_obj)

        # Connect CourseResource
        course_res = CourseResource(
            syllabus_id=syllabus_id,
            resource_type=r_type,
            book_metadata_id=b_meta.id,
            status="discovered"
        )
        db.add(course_res)

        formatted_record = {
            "id": b_meta.id,
            "resource_type": r_type,
            "book_title": b_meta.book_title,
            "subtitle": b_meta.subtitle,
            "authors": [a.get("display_name") for a in item.get("authors", [])],
            "authors_display": ", ".join([a.get("display_name") for a in item.get("authors", [])]),
            "publisher": b_meta.publisher,
            "edition": b_meta.edition,
            "publication_year": b_meta.publication_year,
            "volume": b_meta.volume,
            "doi": b_meta.doi,
            "isbn_10": b_meta.isbn_10,
            "isbn_13": b_meta.isbn_13,
            "isbn_display": format_isbn_display(b_meta.isbn_13 or b_meta.isbn_10),
            "original_citation": b_meta.original_citation,
            "metadata_confidence": confidence,
            "rag_status": "Pending Index",
            "is_verified_downloadable": False
        }

        if r_type == "TEXTBOOK":
            textbooks.append(formatted_record)
        else:
            reference_books.append(formatted_record)

        created_metadata_records.append(formatted_record)

    db.commit()

    return {
        "status": "success",
        "total_books": len(created_metadata_records),
        "textbooks_count": len(textbooks),
        "reference_books_count": len(reference_books),
        "textbooks": textbooks,
        "reference_books": reference_books,
        "all_books": created_metadata_records
    }

@router.get("/books")
def list_discovery_books(
    syllabus_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    resource_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    List extracted textbooks and reference books with full bibliographic fields,
    provenance, and RAG index status.
    """
    q = db.query(BookMetadata)
    if syllabus_id:
        q = q.filter(BookMetadata.syllabus_id == syllabus_id)
    if resource_type:
        q = q.filter(BookMetadata.resource_type == resource_type.upper())

    records = q.all()
    results = []

    for b in records:
        # Check files
        b_file = db.query(BookFile).filter(BookFile.book_metadata_id == b.id).order_by(BookFile.id.desc()).first()
        # Check RAG doc
        rag_doc = db.query(RAGDocument).filter(RAGDocument.book_metadata_id == b.id).first()

        authors_list = [a.display_name for a in b.authors]
        authors_display = ", ".join(authors_list) if authors_list else "Author not stated"

        rag_status = "Pending Index"
        if rag_doc and rag_doc.status == "indexed":
            rag_status = "Indexed"
        elif b_file:
            rag_status = "Downloaded (Unindexed)"

        results.append({
            "id": b.id,
            "resource_type": b.resource_type,
            "book_title": b.book_title,
            "subtitle": b.subtitle,
            "authors": authors_list,
            "authors_display": authors_display,
            "publisher": b.publisher or "Not available",
            "edition": b.edition or "Not available",
            "publication_year": b.publication_year or "Not available",
            "volume": b.volume,
            "doi": b.doi,
            "isbn_10": b.isbn_10,
            "isbn_13": b.isbn_13,
            "isbn_display": format_isbn_display(b.isbn_13 or b.isbn_10),
            "original_citation": b.original_citation,
            "metadata_confidence": b.metadata_confidence,
            "is_verified_downloadable": bool(b_file and b_file.is_verified),
            "local_file_path": b_file.local_path if b_file else None,
            "file_size": b_file.file_size_bytes if b_file else 0,
            "rag_status": rag_status,
            "total_chunks": rag_doc.total_chunks if rag_doc else 0,
            "is_reviewed": b.is_reviewed
        })

    return {
        "total": len(results),
        "books": results
    }

@router.post("/search")
async def search_book_sources(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Search 13 repositories for a book, pre-validate candidate download URLs,
    and return consolidated duplicate-free results with 7-factor match scores.
    """
    book_id = payload.get("book_id")
    book_payload = {
        "title": payload.get("title") or payload.get("book_title", ""),
        "authors": payload.get("authors", ""),
        "publisher": payload.get("publisher", ""),
        "edition": payload.get("edition", ""),
        "publication_year": payload.get("publication_year", ""),
        "isbn": payload.get("isbn") or payload.get("isbn_13") or payload.get("isbn_10", ""),
        "resource_type": payload.get("resource_type", "TEXTBOOK")
    }

    if book_id:
        bm = db.query(BookMetadata).filter(BookMetadata.id == book_id).first()
        if bm:
            book_payload["title"] = bm.book_title
            authors_str = ", ".join([a.display_name for a in bm.authors])
            book_payload["authors"] = authors_str
            book_payload["publisher"] = bm.publisher
            book_payload["edition"] = bm.edition
            book_payload["publication_year"] = bm.publication_year
            book_payload["isbn"] = bm.isbn_13 or bm.isbn_10
            book_payload["resource_type"] = bm.resource_type

    syllabus_topic = payload.get("syllabus_topic")
    consolidated = await search_multi_source_and_consolidate(book_payload, syllabus_topic=syllabus_topic, db=db)
    return consolidated

@router.post("/verify-link")
async def verify_download_link(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Interactive 9-step server-side pre-validation endpoint for candidate links.
    Returns HTTP status, magic byte confirmation, file size, and friendly error message.
    """
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required for verification.")

    book_source_id = payload.get("book_source_id")
    book_file_id = payload.get("book_file_id")

    result = await pre_validate_candidate_url(
        url=url,
        db=db,
        book_source_id=book_source_id,
        book_file_id=book_file_id
    )
    return result

@router.post("/download-and-index")
async def start_download_and_index_job(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Launch background download and RAG indexing pipeline.
    Progresses through the 13 specification states with live progress reporting.
    """
    book_id = payload.get("book_id")
    syllabus_id = payload.get("syllabus_id")
    course_id = payload.get("course_id")

    if not book_id:
        raise HTTPException(status_code=400, detail="book_id is required.")

    # Create job in registry and DB
    job = create_job(book_id=book_id, syllabus_id=syllabus_id, course_id=course_id, db=db)

    # Launch background task
    import asyncio
    asyncio.create_task(
        execute_auto_download_and_indexing_pipeline(
            job_id=job.job_id,
            book_id=book_id,
            db_session_factory=SessionLocal
        )
    )

    return {
        "job_id": job.job_id,
        "status": job.state,
        "progress": job.progress,
        "message": f"Download and RAG indexing pipeline started for book {book_id}."
    }

@router.post("/download-all-verified")
async def download_all_verified(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Batch download all verified books for a syllabus or course.
    """
    syllabus_id = payload.get("syllabus_id")
    if not syllabus_id:
        raise HTTPException(status_code=400, detail="syllabus_id is required.")

    # Find books in syllabus
    books = db.query(BookMetadata).filter(BookMetadata.syllabus_id == syllabus_id).all()
    started_jobs = []

    import asyncio
    for b in books:
        # Check if already downloaded
        existing_file = db.query(BookFile).filter(BookFile.book_metadata_id == b.id).first()
        if existing_file and existing_file.local_path and Path(existing_file.local_path).exists():
            continue

        job = create_job(book_id=b.id, syllabus_id=syllabus_id, db=db)
        asyncio.create_task(
            execute_auto_download_and_indexing_pipeline(
                job_id=job.job_id,
                book_id=b.id,
                db_session_factory=SessionLocal
            )
        )
        started_jobs.append({"book_id": b.id, "book_title": b.book_title, "job_id": job.job_id})

    return {
        "message": f"Started {len(started_jobs)} batch download and indexing jobs.",
        "count": len(started_jobs),
        "jobs": started_jobs
    }

@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Retrieve live job status, progress percentage, current step, and error details.
    """
    job = get_job(job_id)
    if job:
        return job.to_dict()

    # Fallback to database record
    db_job = db.query(DownloadJobModel).filter(DownloadJobModel.job_uuid == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found.")

    res_dict = {}
    if db_job.result_json:
        try:
            res_dict = json.loads(db_job.result_json)
        except Exception:
            res_dict = {}

    return {
        "job_id": db_job.job_uuid,
        "book_id": db_job.book_metadata_id,
        "syllabus_id": db_job.syllabus_id,
        "course_id": db_job.course_id,
        "state": db_job.status,
        "status": db_job.status,
        "progress": db_job.progress_pct,
        "progress_pct": db_job.progress_pct,
        "message": db_job.message,
        "current_step": db_job.message,
        "error": db_job.error_message,
        "is_cancelled": db_job.is_cancelled,
        "result": res_dict,
        "created_at": db_job.created_at.isoformat() if db_job.created_at else None,
        "updated_at": db_job.updated_at.isoformat() if db_job.updated_at else None
    }

@router.post("/jobs/{job_id}/cancel")
def cancel_running_job(job_id: str, db: Session = Depends(get_db)):
    """
    Cancel an in-progress download job.
    """
    success = cancel_job(job_id, db=db)
    return {
        "job_id": job_id,
        "status": JOB_STATE_CANCELLED,
        "success": success,
        "message": "Job cancellation request processed."
    }

@router.post("/jobs/{job_id}/retry")
def retry_download_job(job_id: str):
    """
    Retry a failed or cancelled download job.
    """
    retried = retry_job(job_id, SessionLocal)
    if not retried:
        raise HTTPException(status_code=404, detail="Job not found or invalid book id for retry.")

    return {
        "job_id": retried.job_id,
        "status": retried.state,
        "message": "Job retry initiated."
    }

@router.get("/file/{book_id}")
def stream_book_file(book_id: int, db: Session = Depends(get_db)):
    """
    Safely stream local eBook file (PDF/EPUB) with path traversal validation.
    Never exposes raw error pages.
    """
    book_file = db.query(BookFile).filter(BookFile.book_metadata_id == book_id).order_by(BookFile.id.desc()).first()
    if not book_file or not book_file.local_path:
        raise HTTPException(status_code=404, detail="No local file indexed for this book.")

    file_path = Path(book_file.local_path)
    try:
        validate_path_traversal(file_path.parent, file_path.name)
    except Exception as sec_err:
        raise HTTPException(status_code=403, detail="Access denied: invalid file path.")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=FRIENDLY_ERROR_MESSAGE)

    media_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else "application/epub+zip"
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name
    )

@router.get("/coverage-matrix")
def get_syllabus_coverage_matrix(
    syllabus_id: int = Query(...),
    course_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Retrieve Section 11 Syllabus Alignment Matrix:
    Unit | Syllabus topic | Textbook | Chapter | Pages | Relevance | RAG status
    """
    matrix = generate_syllabus_book_alignment_matrix(
        syllabus_id=syllabus_id,
        course_id=course_id,
        db=db
    )
    return {
        "syllabus_id": syllabus_id,
        "total_topics": len(matrix),
        "alignment_matrix": matrix
    }

@router.post("/reindex")
def reindex_existing_book(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Re-index book chunks and update vector store.
    """
    book_id = payload.get("book_id")
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id is required.")

    try:
        res = reindex_book(book_id, db=db)
        return {
            "status": "success",
            "book_id": book_id,
            "reindexing_summary": res
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/index/{book_id}")
def remove_book_index(book_id: int, db: Session = Depends(get_db)):
    """
    Remove book from local RAG index.
    """
    result = remove_book_from_rag_index(book_id, db=db)
    return {
        "status": "success",
        "book_id": book_id,
        "details": result
    }

@router.post("/merge")
def merge_duplicate_books(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Merge duplicate book records into canonical book entity.
    """
    primary_id = payload.get("primary_book_id")
    secondary_ids = payload.get("secondary_book_ids", [])

    if not primary_id or not secondary_ids:
        raise HTTPException(status_code=400, detail="primary_book_id and secondary_book_ids are required.")

    primary = db.query(BookMetadata).filter(BookMetadata.id == primary_id).first()
    if not primary:
        raise HTTPException(status_code=404, detail="Primary book record not found.")

    merged_count = 0
    for sid in secondary_ids:
        if sid == primary_id:
            continue
        sec = db.query(BookMetadata).filter(BookMetadata.id == sid).first()
        if not sec:
            continue

        # Reassign files and sources
        db.query(BookFile).filter(BookFile.book_metadata_id == sid).update({"book_metadata_id": primary_id})
        db.query(BookSource).filter(BookSource.book_metadata_id == sid).update({"book_metadata_id": primary_id})
        db.query(RAGDocument).filter(RAGDocument.book_metadata_id == sid).update({"book_metadata_id": primary_id})
        db.query(RAGChunk).filter(RAGChunk.book_metadata_id == sid).update({"book_metadata_id": primary_id})
        db.query(CourseResource).filter(CourseResource.book_metadata_id == sid).delete()

        db.delete(sec)
        merged_count += 1

    db.commit()
    return {
        "status": "success",
        "primary_book_id": primary_id,
        "merged_count": merged_count
    }

@router.put("/metadata/{book_id}")
def edit_book_metadata(book_id: int, payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Edit and normalize book metadata manually.
    """
    bm = db.query(BookMetadata).filter(BookMetadata.id == book_id).first()
    if not bm:
        raise HTTPException(status_code=404, detail="Book metadata record not found.")

    if "book_title" in payload:
        bm.book_title = payload["book_title"]
    if "publisher" in payload:
        bm.publisher = normalize_publisher(payload["publisher"])
    if "edition" in payload:
        bm.edition = normalize_edition(payload["edition"])
    if "publication_year" in payload:
        bm.publication_year = str(payload["publication_year"])
    if "resource_type" in payload:
        bm.resource_type = payload["resource_type"].upper()
    if "isbn_10" in payload:
        bm.isbn_10 = payload["isbn_10"]
    if "isbn_13" in payload:
        bm.isbn_13 = payload["isbn_13"]

    bm.is_reviewed = True
    db.commit()
    db.refresh(bm)

    return {
        "status": "success",
        "book_id": bm.id,
        "book_title": bm.book_title,
        "resource_type": bm.resource_type,
        "publisher": bm.publisher,
        "edition": bm.edition,
        "publication_year": bm.publication_year,
        "isbn_10": bm.isbn_10,
        "isbn_13": bm.isbn_13
    }
