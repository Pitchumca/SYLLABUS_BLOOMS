import asyncio
import logging
import datetime
import uuid
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models.book import Book
from app.models.syllabus import Syllabus
from app.models.student import Course
from app.models.search_result import SearchResult
from app.models.discovery_rag import (
    BookMetadata, BookFile, RAGDocument, RAGChunk, DownloadJobModel
)
from app.services.access_states import PUBLIC_PDF_VERIFIED, BORROW_REQUIRED, PREVIEW_ONLY, METADATA_ONLY
from app.services.search_service import (
    search_single_book_sources_resilient,
    generate_fallback_discovery_links
)
from app.services.verification_service import pre_validate_candidate_url, verify_magic_bytes
from app.services.rag_indexer_service import (
    resolve_course_storage_dirs,
    process_book_file_for_rag
)

logger = logging.getLogger(__name__)

# In-memory store for active and completed search jobs
_JOB_STORE: Dict[str, Dict[str, Any]] = {}
_JOB_LOCK = asyncio.Lock()


def generate_job_id() -> str:
    """Generate a clean job identifier e.g. BOOKSEARCH-A1B2C3D4."""
    uid = uuid.uuid4().hex[:8].upper()
    return f"BOOKSEARCH-{uid}"


class BookSearchJobManager:
    """
    Manages asynchronous multi-book search, file verification, downloading,
    and RAG indexing with per-book exception isolation and status polling.
    """

    @classmethod
    async def create_job(
        cls,
        course_id: Optional[int],
        syllabus_id: Optional[int],
        book_ids: List[int],
        search_sources: List[str],
        find_accessible_files: bool = True,
        download_verified_files: bool = True,
        start_rag_indexing: bool = True,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Initialize a new search job and seed initial book records."""
        job_id = generate_job_id()
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Load books from database to seed results array
        books_data = []
        close_session = False
        target_db = db
        if target_db is None:
            try:
                target_db = SessionLocal()
                close_session = True
            except Exception:
                target_db = None

        try:
            if target_db is not None and book_ids:
                db_books = target_db.query(Book).filter(Book.id.in_(book_ids)).all()
                for b in db_books:
                    books_data.append({
                        "book_id": b.id,
                        "book_title": b.title,
                        "authors": b.authors or "",
                        "publisher": b.publisher or "",
                        "edition": b.edition or "",
                        "publication_year": b.publication_year or "",
                        "isbn": b.isbn or "",
                        "category": b.category or "Textbook",
                        "search_status": "PENDING",
                        "sources_checked": 0,
                        "candidates_found": 0,
                        "verified_files": 0,
                        "download_status": "PENDING",
                        "rag_status": "PENDING",
                        "errors": [],
                        "source_diagnostics": {},
                        "verified_download_url": None,
                        "local_file_path": None,
                        "confidence_score": 0.0,
                        "access_status": "METADATA_ONLY",
                        "remarks": ""
                    })
        finally:
            if close_session and target_db is not None:
                target_db.close()

        # Fallback if no books matched or database not passed
        if not books_data:
            for b_id in book_ids:
                books_data.append({
                    "book_id": b_id,
                    "book_title": f"Book #{b_id}",
                    "authors": "",
                    "search_status": "PENDING",
                    "sources_checked": 0,
                    "candidates_found": 0,
                    "verified_files": 0,
                    "download_status": "PENDING",
                    "rag_status": "PENDING",
                    "errors": [],
                    "source_diagnostics": {},
                    "verified_download_url": None,
                    "local_file_path": None,
                    "confidence_score": 0.0,
                    "access_status": "METADATA_ONLY",
                    "remarks": ""
                })

        job_record = {
            "job_id": job_id,
            "status": "QUEUED",
            "total_books": len(books_data),
            "completed_books": 0,
            "failed_books": 0,
            "current_book": books_data[0]["book_title"] if books_data else None,
            "current_stage": "QUEUED",
            "progress_percentage": 0,
            "message": "Book search started",
            "course_id": course_id,
            "syllabus_id": syllabus_id,
            "search_sources": search_sources,
            "find_accessible_files": find_accessible_files,
            "download_verified_files": download_verified_files,
            "start_rag_indexing": start_rag_indexing,
            "results": books_data,
            "created_at": now_str,
            "updated_at": now_str
        }

        async with _JOB_LOCK:
            _JOB_STORE[job_id] = job_record

        return job_record

    @classmethod
    async def get_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job status object."""
        async with _JOB_LOCK:
            return _JOB_STORE.get(job_id)

    @classmethod
    async def run_job_pipeline(cls, job_id: str):
        """
        Execute full asynchronous background search, verification, download,
        and RAG pipeline across each book independently.
        """
        async with _JOB_LOCK:
            job = _JOB_STORE.get(job_id)
            if not job:
                return
            job["status"] = "RUNNING"
            job["current_stage"] = "SEARCHING_METADATA"
            job["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        db = SessionLocal()
        try:
            total = job["total_books"]
            completed_count = 0
            failed_count = 0

            # Course metadata for folder storage
            course_code = "GEN101"
            course_name = "General_Curriculum"
            if job["course_id"]:
                c_obj = db.query(Course).filter(Course.id == job["course_id"]).first()
                if c_obj:
                    course_code = c_obj.course_code
                    course_name = c_obj.course_name
            elif job["syllabus_id"]:
                s_obj = db.query(Syllabus).filter(Syllabus.id == job["syllabus_id"]).first()
                if s_obj:
                    course_name = Path(s_obj.original_filename).stem

            course_dirs = resolve_course_storage_dirs(course_code, course_name)

            for idx, book_item in enumerate(job["results"]):
                b_id = book_item["book_id"]
                b_title = book_item["book_title"]

                async with _JOB_LOCK:
                    job["current_book"] = b_title
                    job["current_stage"] = "SEARCHING_METADATA"
                    job["progress_percentage"] = int(((idx) / max(1, total)) * 100)
                    job["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    book_item["search_status"] = "SEARCHING"

                # Process this book with complete exception isolation
                try:
                    await cls._process_single_book(
                        book_item=book_item,
                        job=job,
                        course_dirs=course_dirs,
                        course_code=course_code,
                        course_name=course_name,
                        db=db
                    )
                    completed_count += 1
                except Exception as exc:
                    logger.error(f"Error processing book #{b_id} ({b_title}): {exc}", exc_info=True)
                    failed_count += 1
                    book_item["search_status"] = "FAILED"
                    book_item["errors"].append(str(exc))
                    book_item["remarks"] = f"Processing error: {str(exc)}"

                async with _JOB_LOCK:
                    job["completed_books"] = completed_count
                    job["failed_books"] = failed_count
                    job["progress_percentage"] = int(((idx + 1) / max(1, total)) * 100)
                    job["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Finalize Job State
            async with _JOB_LOCK:
                if completed_count == total and total > 0:
                    job["status"] = "COMPLETED"
                    job["message"] = f"All {total} books processed successfully."
                elif completed_count > 0:
                    job["status"] = "PARTIALLY_COMPLETED"
                    job["message"] = f"{completed_count} books processed successfully. {failed_count} books failed."
                else:
                    job["status"] = "FAILED"
                    job["message"] = f"All {total} book searches failed."

                job["current_stage"] = "COMPLETED"
                job["progress_percentage"] = 100
                job["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        finally:
            db.close()

    @classmethod
    async def _process_single_book(
        cls,
        book_item: Dict[str, Any],
        job: Dict[str, Any],
        course_dirs: Dict[str, Path],
        course_code: str,
        course_name: str,
        db: Session
    ):
        """Isolated multi-step search and index pipeline for a single book."""
        b_id = book_item["book_id"]
        book_obj = db.query(Book).filter(Book.id == b_id).first()

        book_data = {
            "id": b_id,
            "title": book_obj.title if book_obj else book_item["book_title"],
            "authors": book_obj.authors if book_obj else book_item.get("authors", ""),
            "edition": book_obj.edition if book_obj else book_item.get("edition", ""),
            "publisher": book_obj.publisher if book_obj else book_item.get("publisher", ""),
            "publication_year": book_obj.publication_year if book_obj else book_item.get("publication_year", ""),
            "isbn": book_obj.isbn if book_obj else book_item.get("isbn", ""),
            "isbn_10": getattr(book_obj, "isbn_10", None) if book_obj else None,
            "isbn_13": getattr(book_obj, "isbn_13", None) if book_obj else None,
            "category": book_obj.category if book_obj else book_item.get("category", "Textbook")
        }

        # Stage 1: Resilient Multi-Provider Search
        async with _JOB_LOCK:
            job["current_stage"] = "SEARCHING_METADATA"

        search_outcome = await search_single_book_sources_resilient(
            book_data=book_data,
            requested_sources=job.get("search_sources"),
            db=db
        )

        candidates = search_outcome.get("candidates", [])
        source_diag = search_outcome.get("source_diagnostics", {})
        book_item["source_diagnostics"] = source_diag
        book_item["sources_checked"] = len(source_diag)
        book_item["candidates_found"] = len(candidates)
        book_item["search_status"] = "COMPLETED"

        # Check for provider timeouts or rate limits
        if any(v == "TIMEOUT" for v in source_diag.values()):
            book_item["remarks"] = "Some providers timed out; continuing with available sources."
        elif any(v == "RATE_LIMITED" for v in source_diag.values()):
            book_item["remarks"] = "Rate limit reached on some providers; others checked."

        # Stage 2: Compare and Select Best Candidate
        async with _JOB_LOCK:
            job["current_stage"] = "COMPARING_CANDIDATES"

        best_cand = candidates[0] if candidates else None
        if not best_cand:
            book_item["download_status"] = "NO_FILE_FOUND"
            book_item["rag_status"] = "METADATA_ONLY"
            book_item["access_status"] = "METADATA_ONLY"
            return

        book_item["confidence_score"] = best_cand.get("confidence_score", 0.0)
        book_item["access_status"] = best_cand.get("access_status", METADATA_ONLY)

        # Stage 3: File Verification
        download_url = best_cand.get("verified_download_url") or best_cand.get("access_url")
        is_accessible_file = False

        if job.get("find_accessible_files") and download_url and (
            best_cand.get("access_status") in (PUBLIC_PDF_VERIFIED, "PUBLIC_PDF_VERIFIED", "Verified open-access full text")
            or download_url.lower().endswith(".pdf")
            or download_url.lower().endswith(".epub")
        ):
            async with _JOB_LOCK:
                job["current_stage"] = "VERIFYING_SOURCES"

            v_res = await pre_validate_candidate_url(download_url, db=db)
            if v_res.get("is_valid"):
                is_accessible_file = True
                book_item["verified_files"] = 1
                book_item["verified_download_url"] = v_res.get("final_url") or download_url

        # Stage 4: Download Verified File
        downloaded_file_path = None
        if is_accessible_file and job.get("download_verified_files") and book_item.get("verified_download_url"):
            async with _JOB_LOCK:
                job["current_stage"] = "DOWNLOADING_FILES"
                book_item["download_status"] = "DOWNLOADING"

            try:
                sub_folder = "textbooks" if book_data.get("category") == "Textbook" else "reference_books"
                dest_dir = course_dirs[sub_folder]
                dest_dir.mkdir(parents=True, exist_ok=True)

                safe_title = "".join(c for c in book_data["title"] if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
                filename = f"{safe_title[:50]}_{b_id}.pdf"
                dest_path = dest_dir / filename

                import httpx
                async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0), follow_redirects=True) as client:
                    resp = await client.get(book_item["verified_download_url"])
                    if resp.status_code == 200:
                        content_bytes = resp.content
                        is_magic_ok, detected_mime = verify_magic_bytes(content_bytes)
                        if is_magic_ok:
                            with open(dest_path, "wb") as f:
                                f.write(content_bytes)
                            downloaded_file_path = dest_path
                            book_item["download_status"] = "COMPLETED"
                            book_item["local_file_path"] = str(dest_path)
                        else:
                            book_item["download_status"] = "FAILED"
                            book_item["errors"].append("Downloaded bytes do not match %PDF- magic signature.")
                    else:
                        book_item["download_status"] = "FAILED"
                        book_item["errors"].append(f"HTTP {resp.status_code} during file download.")
            except Exception as dl_err:
                book_item["download_status"] = "FAILED"
                book_item["errors"].append(f"Download failed: {str(dl_err)}")
        else:
            book_item["download_status"] = "NO_FILE_FOUND" if not is_accessible_file else "PENDING"

        # Stage 5 & 6: Text Extraction & RAG Indexing
        if downloaded_file_path and job.get("start_rag_indexing"):
            async with _JOB_LOCK:
                job["current_stage"] = "INDEXING_RAG"
                book_item["rag_status"] = "INDEXING"

            try:
                # Create or get BookMetadata entry
                bm = db.query(BookMetadata).filter(
                    BookMetadata.book_title == book_data["title"]
                ).first()
                if not bm:
                    bm = BookMetadata(
                        course_id=job.get("course_id"),
                        syllabus_id=job.get("syllabus_id"),
                        resource_type="TEXTBOOK" if book_data.get("category") == "Textbook" else "REFERENCE_BOOK",
                        book_title=book_data["title"],
                        publisher=book_data.get("publisher"),
                        edition=book_data.get("edition"),
                        publication_year=str(book_data.get("publication_year") or ""),
                        isbn_13=book_data.get("isbn_13") or book_data.get("isbn"),
                        metadata_confidence=round(book_item.get("confidence_score", 90.0) / 100.0, 2)
                    )
                    db.add(bm)
                    db.flush()

                rag_res = process_book_file_for_rag(
                    file_path=downloaded_file_path,
                    book_metadata_id=bm.id,
                    course_id=job.get("course_id"),
                    syllabus_id=job.get("syllabus_id"),
                    db=db,
                    course_code=course_code,
                    course_name=course_name,
                    resource_type="TEXTBOOK" if book_data.get("category") == "Textbook" else "REFERENCE_BOOK",
                    source_url=book_item.get("verified_download_url")
                )
                if rag_res.get("status") == "success":
                    book_item["rag_status"] = "INDEXED"
                else:
                    book_item["rag_status"] = "FAILED"
                    book_item["errors"].append(rag_res.get("message", "RAG indexing failed."))
            except Exception as rag_err:
                book_item["rag_status"] = "FAILED"
                book_item["errors"].append(f"RAG indexing exception: {str(rag_err)}")
        else:
            book_item["rag_status"] = "METADATA_ONLY"

        # Update candidate records in SearchResult table
        if candidates and book_obj:
            db.query(SearchResult).filter(SearchResult.book_id == b_id).delete()
            for cand in candidates[:5]:
                sr = SearchResult(
                    book_id=b_id,
                    source=cand.get("source", "Web Repository"),
                    title=cand.get("title", book_obj.title),
                    subtitle=cand.get("subtitle"),
                    authors=cand.get("authors", book_obj.authors),
                    publisher=cand.get("publisher", book_obj.publisher),
                    edition=cand.get("edition", book_obj.edition),
                    publication_year=cand.get("publication_year", book_obj.publication_year),
                    isbn=cand.get("isbn", book_obj.isbn),
                    access_type=cand.get("access_type", "Catalogue record"),
                    access_status=cand.get("access_status", METADATA_ONLY),
                    access_url=cand.get("access_url"),
                    verified_download_url=cand.get("verified_download_url"),
                    confidence_score=cand.get("confidence_score", 0.0),
                    verification_status=cand.get("verification_status", "Catalog Record"),
                    remarks=cand.get("remarks", "")
                )
                db.add(sr)
            book_obj.confidence_score = book_item.get("confidence_score", 0.0)
            db.commit()

    @classmethod
    async def retry_single_book(cls, job_id: str, book_id: int) -> Optional[Dict[str, Any]]:
        """Retry processing for a specific failed book within an existing job."""
        async with _JOB_LOCK:
            job = _JOB_STORE.get(job_id)
            if not job:
                return None

            target_book = None
            for b in job["results"]:
                if b["book_id"] == book_id:
                    target_book = b
                    break

            if not target_book:
                return None

            # Reset book status
            target_book["search_status"] = "SEARCHING"
            target_book["download_status"] = "PENDING"
            target_book["rag_status"] = "PENDING"
            target_book["errors"] = []
            target_book["remarks"] = "Retrying search..."
            job["status"] = "RUNNING"
            job["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Run retry asynchronously
        asyncio.create_task(cls._retry_worker(job_id, book_id))
        return job

    @classmethod
    async def _retry_worker(cls, job_id: str, book_id: int):
        """Worker task executing retry on a single book."""
        db = SessionLocal()
        try:
            async with _JOB_LOCK:
                job = _JOB_STORE.get(job_id)
                if not job:
                    return
                target_book = next((b for b in job["results"] if b["book_id"] == book_id), None)
                if not target_book:
                    return

            course_code = "GEN101"
            course_name = "General_Curriculum"
            if job["course_id"]:
                c_obj = db.query(Course).filter(Course.id == job["course_id"]).first()
                if c_obj:
                    course_code = c_obj.course_code
                    course_name = c_obj.course_name
            elif job["syllabus_id"]:
                s_obj = db.query(Syllabus).filter(Syllabus.id == job["syllabus_id"]).first()
                if s_obj:
                    course_name = Path(s_obj.original_filename).stem

            course_dirs = resolve_course_storage_dirs(course_code, course_name)

            try:
                await cls._process_single_book(
                    book_item=target_book,
                    job=job,
                    course_dirs=course_dirs,
                    course_code=course_code,
                    course_name=course_name,
                    db=db
                )
            except Exception as exc:
                target_book["search_status"] = "FAILED"
                target_book["errors"].append(str(exc))

            # Recalculate job summary status
            async with _JOB_LOCK:
                completed = sum(1 for b in job["results"] if b["search_status"] == "COMPLETED")
                failed = sum(1 for b in job["results"] if b["search_status"] == "FAILED")
                job["completed_books"] = completed
                job["failed_books"] = failed
                if failed == 0:
                    job["status"] = "COMPLETED"
                elif completed > 0:
                    job["status"] = "PARTIALLY_COMPLETED"
                else:
                    job["status"] = "FAILED"
                job["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        finally:
            db.close()
