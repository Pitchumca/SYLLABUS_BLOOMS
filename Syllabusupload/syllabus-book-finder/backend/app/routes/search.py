import json
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.syllabus import Syllabus
from app.models.book import Book
from app.models.search_result import SearchResult
from app.models.user import User
from app.schemas.search_result import SearchResultResponse
from app.services.search_service import search_single_book_sources, search_books_batch
from app.services.access_states import (
    PUBLIC_PDF_VERIFIED,
    BORROW_REQUIRED,
    LINK_UNAVAILABLE,
    METADATA_ONLY,
    VERIFICATION_FAILED
)
from app.services.download_job_service import (
    create_job,
    get_job,
    get_job_by_book_id,
    execute_auto_download_and_indexing_pipeline,
    JOB_STATE_COMPLETED,
    JOB_STATE_FAILED,
    JOB_STATE_DOWNLOADING,
    JOB_STATE_INDEXING_RAG
)
from app.services.internet_archive_service import verify_internet_archive_item
from app.utils.auth import get_current_user_optional

router = APIRouter(prefix="/search", tags=["Lawful Book Search & Verification"])

def _populate_search_result_model(book_id: int, r: Dict[str, Any]) -> SearchResult:
    """Helper to populate all independent fields into a SearchResult instance."""
    return SearchResult(
        book_id=book_id,
        source=r.get("source", "Search Engine"),
        title=r.get("title"),
        subtitle=r.get("subtitle"),
        authors=r.get("authors"),
        authors_json=json.dumps(r.get("authors_list", [])) if r.get("authors_list") else None,
        publisher=r.get("publisher"),
        edition=r.get("edition"),
        publication_year=r.get("publication_year"),
        isbn=r.get("isbn"),
        isbn_10=r.get("isbn_10"),
        isbn_13=r.get("isbn_13"),
        internet_archive_identifier=r.get("internet_archive_identifier"),
        internet_archive_item_url=r.get("internet_archive_item_url"),
        verified_download_url=r.get("verified_download_url"),
        access_status=r.get("access_status", "METADATA_ONLY"),
        access_type=r.get("access_type", "No verified access found"),
        rights_or_license=r.get("rights_or_license"),
        verification_http_status=r.get("verification_http_status"),
        verification_message=r.get("verification_message"),
        verified_at=r.get("verified_at"),
        local_file_path=r.get("local_file_path"),
        checksum_sha256=r.get("checksum_sha256"),
        access_url=r.get("access_url"),
        confidence_score=r.get("confidence_score", 0.0),
        verification_status=r.get("verification_status", "Unverified"),
        remarks=r.get("remarks")
    )

@router.post("/book/{book_id}", response_model=List[SearchResultResponse])
async def search_for_book(
    book_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Search lawful repositories (Google Books, Open Library, Crossref, IA) for a specific book.
    Stores and updates search results in the database with independent bibliographic and access fields.
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book record not found.")

    book_dict = {
        "id": book.id,
        "title": book.title,
        "authors": book.authors,
        "edition": book.edition,
        "publisher": book.publisher,
        "publication_year": book.publication_year,
        "isbn": book.isbn,
        "isbn_10": getattr(book, "isbn_10", None),
        "isbn_13": getattr(book, "isbn_13", None)
    }

    # Execute lawful search with official IA metadata verification
    results_data = await search_single_book_sources(book_dict, db=db)

    # Clear prior results for this book
    db.query(SearchResult).filter(SearchResult.book_id == book_id).delete()

    created_results = []
    top_score = 0.0
    verified_oa_candidate = None

    for r in results_data:
        sr = _populate_search_result_model(book.id, r)
        db.add(sr)
        created_results.append(sr)
        if sr.confidence_score > top_score:
            top_score = sr.confidence_score
        if sr.access_status == PUBLIC_PDF_VERIFIED and not verified_oa_candidate:
            verified_oa_candidate = sr

    book.confidence_score = top_score
    db.commit()

    for sr in created_results:
        db.refresh(sr)

    # If faculty auto-download setting is enabled and verified OA candidate exists
    auto_download_enabled = getattr(current_user, "auto_download_verified_oa", False)
    if auto_download_enabled and verified_oa_candidate:
        job = create_job(book_id=book.id, syllabus_id=book.syllabus_id)
        background_tasks.add_task(
            execute_auto_download_and_indexing_pipeline,
            job.job_id,
            book.id,
            SessionLocal,
            current_user.id if current_user else None
        )

    return created_results

@router.post("/syllabus/{syllabus_id}")
async def search_all_books_in_syllabus(
    syllabus_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Run lawful book access search across all books in a syllabus concurrently.
    Respects rate limits, verifies Internet Archive items officially, and stores normalized metadata.
    """
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")

    books = db.query(Book).filter(Book.syllabus_id == syllabus_id).all()
    if not books:
        raise HTTPException(status_code=400, detail="No books found in this syllabus to search.")

    books_payload = [
        {
            "id": b.id,
            "title": b.title,
            "authors": b.authors,
            "edition": b.edition,
            "publisher": b.publisher,
            "publication_year": b.publication_year,
            "isbn": b.isbn,
            "isbn_10": getattr(b, "isbn_10", None),
            "isbn_13": getattr(b, "isbn_13", None)
        }
        for b in books
    ]

    batch_results = await search_books_batch(books_payload, db=db)
    auto_download_enabled = getattr(current_user, "auto_download_verified_oa", False)
    auto_download_candidates = []

    for b in books:
        res_list = batch_results.get(b.id, [])
        if res_list:
            db.query(SearchResult).filter(SearchResult.book_id == b.id).delete()
            top_score = 0.0
            oa_candidate = None
            for r in res_list:
                sr = _populate_search_result_model(b.id, r)
                db.add(sr)
                if sr.confidence_score > top_score:
                    top_score = sr.confidence_score
                if sr.access_status == PUBLIC_PDF_VERIFIED and not oa_candidate:
                    oa_candidate = sr
            b.confidence_score = top_score
            if oa_candidate:
                auto_download_candidates.append(b.id)

    syllabus.status = "searched"
    db.commit()

    # Trigger automatic background jobs if setting is enabled
    started_jobs = []
    if auto_download_enabled:
        for b_id in auto_download_candidates:
            job = create_job(book_id=b_id, syllabus_id=syllabus_id)
            started_jobs.append(job.job_id)
            background_tasks.add_task(
                execute_auto_download_and_indexing_pipeline,
                job.job_id,
                b_id,
                SessionLocal,
                current_user.id if current_user else None
            )

    return {
        "message": f"Successfully executed lawful search for {len(books)} books.",
        "total_searched": len(books),
        "auto_download_jobs_started": len(started_jobs)
    }

def _do_get_search_results(
    syllabus_id: int,
    category: Optional[str],
    access_type: Optional[str],
    access_tier: Optional[str],
    source: Optional[str],
    verification_status: Optional[str],
    min_confidence: Optional[float],
    max_confidence: Optional[float],
    query_text: Optional[str],
    search: Optional[str],
    db: Session
):
    actual_access = access_type or access_tier
    actual_query = query_text or search

    books_query = db.query(Book).filter(Book.syllabus_id == syllabus_id)

    if category and category != "All":
        books_query = books_query.filter(Book.category == category)

    if actual_query:
        s = f"%{actual_query.strip()}%"
        books_query = books_query.filter(
            (Book.title.ilike(s)) |
            (Book.authors.ilike(s)) |
            (Book.publisher.ilike(s)) |
            (Book.isbn.ilike(s))
        )

    books = books_query.order_by(Book.id.asc()).all()
    results_list = []

    for b in books:
        res_q = db.query(SearchResult).filter(SearchResult.book_id == b.id)

        if actual_access and actual_access != "All":
            if actual_access in ["Open Access", "Verified open-access full text", "Public-domain full text", "PUBLIC_PDF_VERIFIED"]:
                res_q = res_q.filter(SearchResult.access_status == PUBLIC_PDF_VERIFIED)
            elif actual_access in ["Preview / Borrowing", "Preview available", "Borrowing available", "BORROW_REQUIRED"]:
                res_q = res_q.filter(SearchResult.access_status.in_([BORROW_REQUIRED, "PREVIEW_ONLY"]))
            elif actual_access in ["Catalogue / Publisher", "Catalogue record", "Publisher or purchase page", "METADATA_ONLY"]:
                res_q = res_q.filter(SearchResult.access_status == "METADATA_ONLY")
            elif actual_access in ["No Verified Access", "LINK_UNAVAILABLE", "VERIFICATION_FAILED"]:
                res_q = res_q.filter(SearchResult.access_status.in_([LINK_UNAVAILABLE, VERIFICATION_FAILED, "No verified access found"]))
            else:
                res_q = res_q.filter(SearchResult.access_type.ilike(f"%{actual_access}%"))

        if source and source != "All":
            res_q = res_q.filter(SearchResult.source.ilike(f"%{source}%"))

        if min_confidence is not None:
            res_q = res_q.filter(SearchResult.confidence_score >= min_confidence)
        if max_confidence is not None:
            res_q = res_q.filter(SearchResult.confidence_score <= max_confidence)

        res_items = res_q.order_by(SearchResult.confidence_score.desc()).all()
        top_res = res_items[0] if res_items else None

        # Check if stored file already exists for this book
        is_already_stored = bool(
            (top_res and top_res.local_file_path) or
            db.query(SearchResult).filter(SearchResult.book_id == b.id, SearchResult.local_file_path.isnot(None)).first()
        )

        results_list.append({
            "book_id": b.id,
            "category": b.category,
            "title": top_res.title if top_res and top_res.title else b.title,
            "subtitle": top_res.subtitle if top_res else getattr(b, "subtitle", None),
            "authors": top_res.authors if top_res and top_res.authors else b.authors,
            "authors_list": top_res.authors_list if top_res else [],
            "edition": top_res.edition if top_res and top_res.edition else b.edition,
            "publisher": top_res.publisher if top_res and top_res.publisher else b.publisher,
            "publication_year": top_res.publication_year if top_res and top_res.publication_year else b.publication_year,
            "isbn": top_res.isbn if top_res and top_res.isbn else b.isbn,
            "isbn_10": top_res.isbn_10 if top_res else getattr(b, "isbn_10", None),
            "isbn_13": top_res.isbn_13 if top_res else getattr(b, "isbn_13", None),
            "raw_citation": b.raw_citation,
            "is_reviewed": b.is_reviewed,
            "confidence_score": top_res.confidence_score if top_res else b.confidence_score,
            "access_status": top_res.access_status if top_res else "METADATA_ONLY",
            "access_type": top_res.access_type if top_res else "No verified access found",
            "access_url": top_res.access_url if top_res else None,
            "verified_download_url": top_res.verified_download_url if top_res else None,
            "internet_archive_identifier": top_res.internet_archive_identifier if top_res else None,
            "internet_archive_item_url": top_res.internet_archive_item_url if top_res else None,
            "rights_or_license": top_res.rights_or_license if top_res else None,
            "verification_http_status": top_res.verification_http_status if top_res else None,
            "verification_message": top_res.verification_message if top_res else None,
            "verified_at": top_res.verified_at.isoformat() if top_res and top_res.verified_at else None,
            "local_file_path": top_res.local_file_path if top_res else None,
            "checksum_sha256": top_res.checksum_sha256 if top_res else None,
            "is_stored": is_already_stored,
            "source": top_res.source if top_res else "None",
            "verification_status": top_res.verification_status if top_res else "Unverified",
            "remarks": top_res.remarks if top_res else "No search executed yet.",
            "all_results": [
                {
                    "id": r.id,
                    "source": r.source,
                    "title": r.title,
                    "subtitle": r.subtitle,
                    "authors": r.authors,
                    "authors_list": r.authors_list,
                    "publisher": r.publisher,
                    "edition": r.edition,
                    "publication_year": r.publication_year,
                    "isbn": r.isbn,
                    "isbn_10": r.isbn_10,
                    "isbn_13": r.isbn_13,
                    "access_status": r.access_status,
                    "access_type": r.access_type,
                    "access_url": r.access_url,
                    "verified_download_url": r.verified_download_url,
                    "internet_archive_identifier": r.internet_archive_identifier,
                    "internet_archive_item_url": r.internet_archive_item_url,
                    "rights_or_license": r.rights_or_license,
                    "verification_http_status": r.verification_http_status,
                    "verification_message": r.verification_message,
                    "verified_at": r.verified_at.isoformat() if r.verified_at else None,
                    "local_file_path": r.local_file_path,
                    "checksum_sha256": r.checksum_sha256,
                    "confidence_score": r.confidence_score,
                    "verification_status": r.verification_status,
                    "remarks": r.remarks
                }
                for r in res_items
            ]
        })

    return results_list

@router.get("/syllabus/{syllabus_id}")
def get_search_results_by_path(
    syllabus_id: int,
    category: Optional[str] = None,
    access_type: Optional[str] = None,
    access_tier: Optional[str] = None,
    source: Optional[str] = None,
    verification_status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    query_text: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get search results for a syllabus by path parameter."""
    return _do_get_search_results(
        syllabus_id=syllabus_id,
        category=category,
        access_type=access_type,
        access_tier=access_tier,
        source=source,
        verification_status=verification_status,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        query_text=query_text,
        search=search,
        db=db
    )

@router.get("/results")
def get_search_results(
    syllabus_id: int = Query(...),
    category: Optional[str] = None,
    access_type: Optional[str] = None,
    access_tier: Optional[str] = None,
    source: Optional[str] = None,
    verification_status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    query_text: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get search results for a syllabus by query parameter."""
    return _do_get_search_results(
        syllabus_id=syllabus_id,
        category=category,
        access_type=access_type,
        access_tier=access_tier,
        source=source,
        verification_status=verification_status,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        query_text=query_text,
        search=search,
        db=db
    )

# =============================================================================
# BACKGROUND DOWNLOAD JOB & VERIFICATION WORKFLOW ENDPOINTS
# =============================================================================

@router.post("/auto-download-jobs/{syllabus_id}")
async def trigger_syllabus_auto_download(
    syllabus_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Launch background automatic download and RAG indexing for verified open-access books.
    """
    books = db.query(Book).filter(Book.syllabus_id == syllabus_id).all()
    if not books:
        raise HTTPException(status_code=404, detail="No books found in this syllabus.")

    started_jobs = []
    for b in books:
        # Check if top search result is PUBLIC_PDF_VERIFIED
        top_sr = db.query(SearchResult).filter(
            SearchResult.book_id == b.id,
            SearchResult.access_status == PUBLIC_PDF_VERIFIED
        ).first()

        if top_sr:
            job = create_job(book_id=b.id, syllabus_id=syllabus_id)
            started_jobs.append({"book_id": b.id, "job_id": job.job_id, "title": b.title})
            background_tasks.add_task(
                execute_auto_download_and_indexing_pipeline,
                job.job_id,
                b.id,
                SessionLocal,
                current_user.id if current_user else None
            )

    return {
        "message": f"Launched {len(started_jobs)} automatic download and indexing jobs.",
        "jobs": started_jobs
    }

@router.post("/verify-and-download/{search_result_id}")
async def verify_and_download_result(
    search_result_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Execute background download & RAG indexing for a specific search result card.
    Triggered by the 'Download & Index' or 'Re-index' card button.
    """
    sr = db.query(SearchResult).filter(SearchResult.id == search_result_id).first()
    if not sr:
        raise HTTPException(status_code=404, detail="Search result record not found.")

    job = create_job(book_id=sr.book_id)
    background_tasks.add_task(
        execute_auto_download_and_indexing_pipeline,
        job.job_id,
        sr.book_id,
        SessionLocal,
        current_user.id if current_user else None
    )

    return {"message": "Download and indexing job initiated.", "job_id": job.job_id}

@router.post("/retry-verification/{search_result_id}")
async def retry_verification_for_result(
    search_result_id: int,
    db: Session = Depends(get_db)
):
    """
    Re-execute server-side verification for a search result item.
    Updates access_status, verified_download_url, and telemetry.
    """
    sr = db.query(SearchResult).filter(SearchResult.id == search_result_id).first()
    if not sr:
        raise HTTPException(status_code=404, detail="Search result record not found.")

    ident = sr.internet_archive_identifier
    if not ident and "archive.org" in (sr.access_url or ""):
        m = re.search(r"archive\.org/(?:details|download)/([^/]+)", sr.access_url or "")
        if m:
            ident = m.group(1)

    if not ident:
        sr.verification_message = "No Internet Archive identifier available for verification retry."
        sr.access_status = VERIFICATION_FAILED
        db.commit()
        return sr

    ia_res = await verify_internet_archive_item(ident)
    sr.access_status = ia_res["access_status"]
    sr.access_url = ia_res["verified_download_url"] if ia_res["is_downloadable"] else ia_res["internet_archive_item_url"]
    sr.verified_download_url = ia_res["verified_download_url"]
    sr.verification_http_status = ia_res["verification_http_status"]
    sr.verification_message = ia_res["verification_message"]
    sr.verified_at = ia_res["verified_at"]
    sr.access_type = "Verified open-access full text" if ia_res["is_downloadable"] else ("Borrowing available" if ia_res["access_status"] == BORROW_REQUIRED else "No verified access found")

    db.commit()
    db.refresh(sr)
    return sr

@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Poll live progress and status of a background download and indexing job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_dict()

@router.get("/jobs/by-book/{book_id}")
def get_job_for_book(book_id: int):
    """Retrieve the latest download job for a book ID."""
    job = get_job_by_book_id(book_id)
    if not job:
        return {"status": "none", "job": None}
    return {"status": "found", "job": job.to_dict()}
