import os
import re
import time
import uuid
import hashlib
import datetime
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

import fitz  # PyMuPDF
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.services.access_states import (
    PUBLIC_PDF_VERIFIED,
    PUBLIC_EPUB_VERIFIED,
    BORROW_REQUIRED,
    PREVIEW_ONLY,
    METADATA_ONLY,
    LINK_UNAVAILABLE,
    VERIFICATION_FAILED
)
from app.utils.security import (
    validate_download_url_security,
    sanitize_filename,
    validate_path_traversal
)
from app.models.template_and_resource import (
    ResourceRecord,
    StoredDocument,
    DocumentChunkModel,
    RightsVerificationLog,
    DownloadAuditLog
)
from app.models.discovery_rag import (
    BookMetadata,
    BookFile,
    DownloadJobModel,
    CourseResource
)
from app.models.search_result import SearchResult
from app.models.book import Book
from app.models.syllabus import Syllabus
from app.services.ocr_service import is_tesseract_available
from app.services.rag_indexer_service import process_book_file_for_rag

logger = logging.getLogger(__name__)

# Specification States for Background Download Job
JOB_STATE_SEARCHING = "Searching"
JOB_STATE_METADATA_MATCHED = "Metadata matched"
JOB_STATE_CHECKING_ACCESS = "Checking licence/access"
JOB_STATE_VERIFYING_FILE = "Verifying file"
JOB_STATE_DOWNLOADING = "Downloading"
JOB_STATE_EXTRACTING_TEXT = "Extracting text"
JOB_STATE_INDEXING_RAG = "Indexing for RAG"
JOB_STATE_COMPLETED = "Completed"
JOB_STATE_BORROW_REQUIRED = "Borrowing required"
JOB_STATE_DOWNLOAD_UNAVAILABLE = "Download unavailable"
JOB_STATE_FAILED = "Failed"
JOB_STATE_CANCELLED = "Cancelled"
JOB_STATE_PAUSED = "Paused"

MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

class DownloadJob:
    def __init__(self, job_id: str, book_id: Optional[int] = None, syllabus_id: Optional[int] = None, course_id: Optional[int] = None):
        self.job_id = job_id
        self.book_id = book_id
        self.syllabus_id = syllabus_id
        self.course_id = course_id
        self.state = JOB_STATE_SEARCHING
        self.progress = 5
        self.message = "Job initialized"
        self.error: Optional[str] = None
        self.result: Dict[str, Any] = {}
        self.is_cancelled = False
        self.created_at = datetime.datetime.now(datetime.UTC)
        self.updated_at = datetime.datetime.now(datetime.UTC)

    def update(
        self,
        state: str,
        progress: int,
        message: str,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ):
        self.state = state
        self.progress = progress
        self.message = message
        if error:
            self.error = error
        if result:
            self.result.update(result)
        self.updated_at = datetime.datetime.now(datetime.UTC)

        if db:
            try:
                db_job = db.query(DownloadJobModel).filter(DownloadJobModel.job_uuid == self.job_id).first()
                if db_job:
                    db_job.status = state
                    db_job.progress_pct = progress
                    db_job.message = message
                    if error:
                        db_job.error_message = error
                    if self.result:
                        db_job.result_json = json.dumps(self.result)
                    db.commit()
            except Exception as e:
                logger.debug(f"Syncing DownloadJobModel failed: {e}")

    @property
    def status(self) -> str:
        return self.state

    @property
    def local_file_path(self) -> Optional[str]:
        return self.result.get("local_file_path")

    @property
    def checksum_sha256(self) -> Optional[str]:
        return self.result.get("sha256_checksum")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "book_id": self.book_id,
            "syllabus_id": self.syllabus_id,
            "course_id": self.course_id,
            "state": self.state,
            "status": self.state,
            "progress": self.progress,
            "progress_pct": self.progress,
            "message": self.message,
            "current_step": self.message,
            "error": self.error,
            "is_cancelled": self.is_cancelled,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

# Global in-memory job registry
_job_registry: Dict[str, DownloadJob] = {}

def get_job(job_id: str) -> Optional[DownloadJob]:
    return _job_registry.get(job_id)

def get_job_by_book_id(book_id: int) -> Optional[DownloadJob]:
    for job in reversed(list(_job_registry.values())):
        if job.book_id == book_id:
            return job
    return None

def create_job(
    book_id: Optional[int] = None,
    syllabus_id: Optional[int] = None,
    course_id: Optional[int] = None,
    db: Optional[Session] = None
) -> DownloadJob:
    job_id = str(uuid.uuid4())
    job = DownloadJob(job_id=job_id, book_id=book_id, syllabus_id=syllabus_id, course_id=course_id)
    _job_registry[job_id] = job
    if db:
        try:
            db_job = DownloadJobModel(
                job_uuid=job_id,
                book_metadata_id=book_id,
                syllabus_id=syllabus_id,
                course_id=course_id,
                status=JOB_STATE_SEARCHING,
                progress_pct=5,
                message="Job initialized"
            )
            db.add(db_job)
            db.commit()
        except Exception as e:
            logger.debug(f"Failed to persist DownloadJobModel: {e}")
    return job

def cancel_job(job_id: str, db: Optional[Session] = None) -> bool:
    job = get_job(job_id)
    if job:
        job.is_cancelled = True
        job.update(JOB_STATE_CANCELLED, job.progress, "Job cancelled by faculty.", db=db)
    if db:
        try:
            db_job = db.query(DownloadJobModel).filter(DownloadJobModel.job_uuid == job_id).first()
            if db_job:
                db_job.is_cancelled = True
                db_job.status = JOB_STATE_CANCELLED
                db_job.message = "Job cancelled by faculty."
                db.commit()
        except Exception as e:
            logger.debug(f"Failed to set cancel in db: {e}")
    return True


async def stream_download_pdf(
    url: str,
    target_path: Path,
    max_size: int = MAX_PDF_SIZE_BYTES
) -> Dict[str, Any]:
    """
    Download PDF file stream safely with size limits, timeout, and signature verification.
    """
    validate_download_url_security(url)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SyllabusBookFinder/1.0"
    }

    sha256 = hashlib.sha256()
    file_size = 0
    first_chunk = True

    async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(40.0, connect=8.0)) as client:
        # Check every redirect hop for SSRF
        async with client.stream("GET", url, headers=headers) as response:
            for hist in response.history:
                validate_download_url_security(str(hist.url))

            if response.status_code not in (200, 206):
                raise ValueError(f"Server returned HTTP {response.status_code}")

            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type:
                raise ValueError("Server returned HTML document instead of binary PDF.")

            with open(target_path, "wb") as f_out:
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    if not chunk:
                        continue

                    if first_chunk:
                        if b"<html" in chunk.lower() or b"<!doctype html" in chunk.lower():
                            raise ValueError("Received HTML error page instead of PDF.")
                        if b"%PDF-" not in chunk[:1024]:
                            raise ValueError("File does not start with valid %PDF- marker.")
                        first_chunk = False

                    file_size += len(chunk)
                    if file_size > max_size:
                        raise ValueError(f"File size exceeded maximum allowed limit ({max_size / (1024*1024):.1f} MB).")

                    sha256.update(chunk)
                    f_out.write(chunk)

    return {
        "file_path": str(target_path),
        "file_size": file_size,
        "sha256_checksum": sha256.hexdigest(),
        "mime_type": "application/pdf",
        "original_filename": target_path.name
    }

def extract_text_and_chunks(file_path: str, max_chunk_words: int = 700, overlap_words: int = 80) -> Tuple[List[Dict[str, Any]], int]:
    """
    Extract text page-by-page. If a page has no usable embedded text, run OCR fallback.
    Returns (chunks, total_pages).
    """
    chunks = []
    doc = fitz.open(file_path)
    total_pages = len(doc)

    for page_idx in range(total_pages):
        page = doc[page_idx]
        page_num = page_idx + 1
        text = page.get_text("text")

        # Check for empty or non-embedded text page
        if not text or len(text.strip()) < 50:
            # Fallback to OCR if tesseract available
            if is_tesseract_available():
                try:
                    import pytesseract
                    from PIL import Image
                    pix = page.get_pixmap(dpi=150)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_text = pytesseract.image_to_string(img)
                    if ocr_text and len(ocr_text.strip()) > 30:
                        text = ocr_text
                except Exception as ocr_err:
                    logger.debug(f"OCR fallback failed on page {page_num}: {ocr_err}")

        if not text or len(text.strip()) < 40:
            continue

        words = text.split()
        if len(words) <= max_chunk_words:
            chunks.append({
                "page_number": page_num,
                "text": text.strip(),
                "token_count": len(words),
                "heading": f"Page {page_num}"
            })
        else:
            start = 0
            part = 1
            while start < len(words):
                end = min(start + max_chunk_words, len(words))
                chunk_slice = " ".join(words[start:end])
                chunks.append({
                    "page_number": page_num,
                    "text": chunk_slice,
                    "token_count": end - start,
                    "heading": f"Page {page_num} (Part {part})"
                })
                if end == len(words):
                    break
                start += (max_chunk_words - overlap_words)
                part += 1

    doc.close()
    return chunks, total_pages

async def execute_auto_download_and_indexing_pipeline(
    job_id: str,
    book_id: int,
    db_session_factory,
    user_id: Optional[int] = None
):
    """
    End-to-end background job executing Requirement 5 & 6:
    1. Searching
    2. Metadata matched
    3. Checking licence/access
    4. Verifying file
    5. Downloading
    6. Extracting text
    7. Indexing for RAG
    8. Completed (or Borrowing required / Download unavailable / Failed)
    """
    job = get_job(job_id)
    if not job:
        return

    from app.services.internet_archive_service import verify_internet_archive_item
    from app.services.search_service import search_single_book_sources
    from app.services.match_engine import calculate_match_confidence

    db: Session = db_session_factory()
    try:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            job.update(JOB_STATE_FAILED, 100, "Book not found", error="Book record not found in database.")
            return

        syllabus_id = book.syllabus_id
        job.syllabus_id = syllabus_id

        # 1. State: Searching
        if job.is_cancelled:
            return
        job.update(JOB_STATE_SEARCHING, 10, f"Searching authorized repositories for '{book.title}'...", db=db)
        book_payload = {
            "id": book.id,
            "title": book.title,
            "authors": book.authors,
            "edition": book.edition,
            "publisher": book.publisher,
            "publication_year": book.publication_year,
            "isbn": book.isbn
        }

        search_results = await search_single_book_sources(book_payload, db=db)
        if job.is_cancelled:
            return
        if not search_results:
            job.update(JOB_STATE_DOWNLOAD_UNAVAILABLE, 100, "No repository matches found for citation.", db=db)
            return

        # 2. State: Metadata matched
        job.update(JOB_STATE_METADATA_MATCHED, 25, f"Matched {len(search_results)} repository candidates.", db=db)

        # Find best candidate: prioritize verified open / Internet Archive / Open Library
        best_candidate = None
        for r in search_results:
            if r.get("source") == "Internet Archive" or "archive.org" in (r.get("access_url") or ""):
                best_candidate = r
                break
        if not best_candidate:
            best_candidate = search_results[0]

        ident = best_candidate.get("internet_archive_identifier")
        if not ident and "archive.org" in (best_candidate.get("access_url") or ""):
            m = re.search(r"archive\.org/(?:details|download)/([^/]+)", best_candidate.get("access_url") or "")
            if m:
                ident = m.group(1)

        # 3. State: Checking licence/access
        if job.is_cancelled:
            return
        job.update(JOB_STATE_CHECKING_ACCESS, 40, f"Evaluating licensing and rights for {best_candidate.get('source')}...", db=db)

        if ident:
            # 4. State: Verifying file (10-step IA verification)
            job.update(JOB_STATE_VERIFYING_FILE, 50, f"Verifying server-side download access for IA item '{ident}'...", db=db)
            ia_verification = await verify_internet_archive_item(ident)
            access_status = ia_verification["access_status"]

            if access_status == BORROW_REQUIRED:
                job.update(
                    JOB_STATE_BORROW_REQUIRED,
                    100,
                    f"Controlled digital lending required for '{book.title}'. Direct download is restricted.",
                    result={"access_status": BORROW_REQUIRED, "details_url": ia_verification["internet_archive_item_url"]},
                    db=db
                )
                return

            if access_status in (LINK_UNAVAILABLE, METADATA_ONLY):
                job.update(
                    JOB_STATE_DOWNLOAD_UNAVAILABLE,
                    100,
                    f"Item is catalogue-only or download link unavailable.",
                    result={"access_status": access_status},
                    db=db
                )
                return

            if access_status == VERIFICATION_FAILED:
                job.update(
                    JOB_STATE_FAILED,
                    100,
                    f"Verification failed: {ia_verification['verification_message']}",
                    error=ia_verification['verification_message'],
                    db=db
                )
                return

            download_url = ia_verification.get("verified_download_url")
        else:
            download_url = best_candidate.get("verified_download_url") or best_candidate.get("access_url")
            access_status = best_candidate.get("access_status", METADATA_ONLY)

            if not download_url or access_status != PUBLIC_PDF_VERIFIED:
                job.update(
                    JOB_STATE_DOWNLOAD_UNAVAILABLE,
                    100,
                    "No verified public download URL found for this record.",
                    result={"access_status": access_status},
                    db=db
                )
                return

        # 5. State: Downloading
        if job.is_cancelled:
            return
        job.update(JOB_STATE_DOWNLOADING, 65, f"Downloading verified PDF from {download_url}...", db=db)
        res_dir = settings.BASE_DIR / "uploads" / "resources"
        res_dir.mkdir(parents=True, exist_ok=True)
        safe_name = sanitize_filename(f"{int(time.time())}_{book.title[:30]}.pdf")
        target_path = res_dir / safe_name

        try:
            dl_result = await stream_download_pdf(download_url, target_path)
        except Exception as dl_err:
            if target_path.exists():
                target_path.unlink(missing_ok=True)
            job.update(JOB_STATE_FAILED, 100, f"Download failed: {dl_err}", error=str(dl_err), db=db)
            return

        if job.is_cancelled:
            if target_path.exists():
                target_path.unlink(missing_ok=True)
            return

        sha256 = dl_result["sha256_checksum"]

        # Duplicate detection (Requirement 8 test 10: "Duplicate books are not downloaded twice")
        existing_doc = db.query(StoredDocument).filter(StoredDocument.sha256_checksum == sha256).first()
        if existing_doc:
            target_path.unlink(missing_ok=True)
            job.update(
                JOB_STATE_COMPLETED,
                100,
                "Duplicate PDF detected via SHA-256. Reused existing indexed chunks.",
                result={
                    "stored_document_id": existing_doc.id,
                    "sha256_checksum": sha256,
                    "is_duplicate": True
                },
                db=db
            )
            # Update search result with verified local path
            sr = db.query(SearchResult).filter(SearchResult.book_id == book.id).first()
            if sr:
                sr.local_file_path = existing_doc.storage_path
                sr.checksum_sha256 = sha256
                sr.access_status = PUBLIC_PDF_VERIFIED
                db.commit()
            return

        # 6. State: Extracting text
        if job.is_cancelled:
            return
        job.update(JOB_STATE_EXTRACTING_TEXT, 80, "Extracting substantive text page-by-page (PyMuPDF / OCR)...", db=db)
        chunks, total_pages = extract_text_and_chunks(str(target_path))

        # 7. State: Indexing for RAG
        if job.is_cancelled:
            return
        job.update(JOB_STATE_INDEXING_RAG, 90, f"Indexing {len(chunks)} chunks for syllabus alignment...", db=db)

        # Create ResourceRecord & StoredDocument
        rec = ResourceRecord(
            syllabus_id=syllabus_id,
            book_id=book.id,
            resource_type="Open Educational Resource",
            title=book.title,
            authors=book.authors,
            publisher=book.publisher,
            edition=book.edition,
            year=book.publication_year,
            isbn=book.isbn,
            source_repository=best_candidate.get("source", "Internet Archive"),
            source_url=download_url,
            landing_page_url=best_candidate.get("access_url"),
            access_type="Open-access PDF",
            licence="Verified Open Access",
            rights_statement="Server-side verified public download.",
            rights_verified=True,
            status="indexed"
        )
        db.add(rec)
        db.flush()

        stored_doc = StoredDocument(
            resource_record_id=rec.id,
            original_filename=dl_result["original_filename"],
            storage_path=dl_result["file_path"],
            mime_type=dl_result["mime_type"],
            file_size=dl_result["file_size"],
            sha256_checksum=sha256,
            acquisition_method="lawful_download",
            extraction_status="completed",
            page_count=total_pages,
            active=True
        )
        db.add(stored_doc)
        db.flush()
        rec.stored_document_id = stored_doc.id

        # Insert chunks into legacy DocumentChunkModel
        for c in chunks:
            chunk_m = DocumentChunkModel(
                stored_document_id=stored_doc.id,
                page_number=c["page_number"],
                heading=c.get("heading"),
                text=c["text"],
                token_count=c["token_count"],
                unit_number=1,
                co_level="CO1",
                alignment_score=0.8,
                approved_for_generation=True
            )
            db.add(chunk_m)

        # Course Folder & Section 10 RAG Indexing
        try:
            book_meta = db.query(BookMetadata).filter(
                (BookMetadata.id == book.id) | (BookMetadata.book_title == book.title)
            ).first()
            if not book_meta:
                book_meta = BookMetadata(
                    syllabus_id=syllabus_id,
                    resource_type="TEXTBOOK",
                    book_title=book.title,
                    publisher=book.publisher,
                    edition=book.edition,
                    publication_year=str(book.publication_year) if book.publication_year else None,
                    isbn_10=book.isbn if len(str(book.isbn or "")) == 10 else None,
                    isbn_13=book.isbn if len(str(book.isbn or "")) == 13 else None,
                    metadata_confidence=90.0,
                    original_citation=f"{book.authors}. {book.title}. {book.publisher or ''}."
                )
                db.add(book_meta)
                db.flush()

            rag_res = process_book_file_for_rag(
                file_path=target_path,
                book_metadata_id=book_meta.id,
                course_id=job.course_id,
                syllabus_id=syllabus_id,
                db=db,
                resource_type=book_meta.resource_type or "TEXTBOOK",
                source_url=download_url
            )
            job.result.update(rag_res)
        except Exception as rag_err:
            logger.warning(f"Error in course storage RAG indexing: {rag_err}", exc_info=True)

        # Update SearchResult record
        sr = db.query(SearchResult).filter(SearchResult.book_id == book.id).first()
        if sr:
            sr.local_file_path = dl_result["file_path"]
            sr.checksum_sha256 = sha256
            sr.access_status = PUBLIC_PDF_VERIFIED
            sr.verified_download_url = download_url
            sr.verification_http_status = 200
            sr.verification_message = "Successfully downloaded and indexed for RAG."
            sr.verified_at = datetime.datetime.now(datetime.UTC)

        db.commit()

        # 8. State: Completed
        job.update(
            JOB_STATE_COMPLETED,
            100,
            f"Successfully downloaded '{book.title}' and indexed {len(chunks)} pages into curriculum storage.",
            result={
                "resource_record_id": rec.id,
                "stored_document_id": stored_doc.id,
                "file_path": dl_result["file_path"],
                "sha256_checksum": sha256,
                "total_chunks": len(chunks)
            },
            db=db
        )

    except Exception as e:
        logger.error(f"Error in auto-download pipeline for book {book_id}: {e}", exc_info=True)
        job.update(JOB_STATE_FAILED, 100, f"Pipeline error: {str(e)}", error=str(e), db=db)
    finally:
        db.close()

def retry_job(job_id: str, db_session_factory) -> Optional[DownloadJob]:
    job = get_job(job_id)
    if not job or not job.book_id:
        return None
    job.is_cancelled = False
    job.update(JOB_STATE_SEARCHING, 5, "Retrying job...")
    asyncio.create_task(
        execute_auto_download_and_indexing_pipeline(
            job_id=job.job_id,
            book_id=job.book_id,
            db_session_factory=db_session_factory
        )
    )
    return job

