import asyncio
import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.student import Course
from app.models.syllabus import Syllabus
from app.models.book import Book
from app.utils.auth import get_current_user, get_current_user_optional
from app.services.book_search_job_service import BookSearchJobManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Book Search & Indexing Pipeline"])


class BookSearchAndIndexRequest(BaseModel):
    book_ids: Optional[List[int]] = Field(default=None, description="List of book IDs to search and index")
    search_sources: Optional[List[str]] = Field(
        default=[
            "local_database",
            "open_library",
            "google_books",
            "internet_archive",
            "oer_commons",
            "crossref",
            "semantic_scholar",
            "doab"
        ],
        description="Search sources to query"
    )
    find_accessible_files: bool = Field(default=True, description="Verify if full-text files are accessible")
    download_verified_files: bool = Field(default=True, description="Download verified files to course folder")
    start_rag_indexing: bool = Field(default=True, description="Automatically chunk and index downloaded files for RAG")


class JobInitiationResponse(BaseModel):
    job_id: str
    status: str
    total_books: int
    message: str


def _resolve_course_and_syllabus(identifier: int, db: Session):
    """
    Resolve course and syllabus entities from an identifier that may be
    a course_id, a syllabus_id, or infer from associated books.
    """
    resolved_course = None
    resolved_syllabus = None

    # Try Course lookup
    course = db.query(Course).filter(Course.id == identifier).first()
    if course:
        resolved_course = course
        if course.syllabus_id:
            resolved_syllabus = db.query(Syllabus).filter(Syllabus.id == course.syllabus_id).first()

    # If course wasn't found by ID, try Syllabus lookup
    if not resolved_course:
        syllabus = db.query(Syllabus).filter(Syllabus.id == identifier).first()
        if syllabus:
            resolved_syllabus = syllabus
            resolved_course = db.query(Course).filter(Course.syllabus_id == syllabus.id).first()

    return resolved_course, resolved_syllabus


async def _start_pipeline_job(
    target_id: int,
    payload: BookSearchAndIndexRequest,
    db: Session,
    current_user: User
) -> JobInitiationResponse:
    """Core logic to initialize and launch book search & indexing pipeline."""
    course, syllabus = _resolve_course_and_syllabus(target_id, db)

    book_ids = payload.book_ids or []
    # If no book_ids provided, infer all books from resolved syllabus
    if not book_ids and syllabus:
        syl_books = db.query(Book).filter(Book.syllabus_id == syllabus.id).all()
        book_ids = [b.id for b in syl_books]

    # If still no book_ids, check if books exist directly with target_id as syllabus_id
    if not book_ids:
        syl_books = db.query(Book).filter(Book.syllabus_id == target_id).all()
        book_ids = [b.id for b in syl_books]

    # If course or syllabus cannot be found and no books match, return 404
    if not course and not syllabus and not book_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course or Syllabus with ID {target_id} was not found."
        )

    if not book_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No books found for this course/syllabus to search and index."
        )

    course_id = course.id if course else None
    syllabus_id = syllabus.id if syllabus else target_id

    # Create job record
    job = await BookSearchJobManager.create_job(
        course_id=course_id,
        syllabus_id=syllabus_id,
        book_ids=book_ids,
        search_sources=payload.search_sources,
        find_accessible_files=payload.find_accessible_files,
        download_verified_files=payload.download_verified_files,
        start_rag_indexing=payload.start_rag_indexing,
        db=db
    )

    # Launch background processing task
    asyncio.create_task(BookSearchJobManager.run_job_pipeline(job["job_id"]))

    return JobInitiationResponse(
        job_id=job["job_id"],
        status=job["status"],
        total_books=job["total_books"],
        message="Book discovery and indexing pipeline started"
    )


# 1. Canonical Endpoint: POST /api/courses/{course_id}/books/search-and-index/
@router.post(
    "/courses/{course_id}/books/search-and-index/",
    response_model=JobInitiationResponse,
    status_code=status.HTTP_202_ACCEPTED
)
@router.post(
    "/courses/{course_id}/books/search-and-index",
    response_model=JobInitiationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False
)
async def search_and_index_course_books(
    course_id: int,
    payload: BookSearchAndIndexRequest = BookSearchAndIndexRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiate asynchronous multi-repository book discovery, file verification,
    download, and RAG indexing for a course's prescribed books.
    Returns HTTP 202 Accepted with a job_id for progress polling.
    """
    return await _start_pipeline_job(course_id, payload, db, current_user)


# 2. Syllabus Alias Endpoint: POST /api/syllabus/{syllabus_id}/books/search-and-index/
@router.post(
    "/syllabus/{syllabus_id}/books/search-and-index/",
    response_model=JobInitiationResponse,
    status_code=status.HTTP_202_ACCEPTED
)
@router.post(
    "/syllabus/{syllabus_id}/books/search-and-index",
    response_model=JobInitiationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False
)
async def search_and_index_syllabus_books(
    syllabus_id: int,
    payload: BookSearchAndIndexRequest = BookSearchAndIndexRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Alias route supporting syllabus_id directly."""
    return await _start_pipeline_job(syllabus_id, payload, db, current_user)


# 3. Status Polling Endpoint: GET /api/book-search-jobs/{job_id}/
@router.get("/book-search-jobs/{job_id}/")
@router.get("/book-search-jobs/{job_id}", include_in_schema=False)
async def get_book_search_job_status(job_id: str):
    """
    Retrieve real-time status, stage progress, and per-book results for a search job.
    """
    job = await BookSearchJobManager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book search job '{job_id}' not found."
        )
    return job


# 4. Per-Book Retry Endpoint: POST /api/book-search-jobs/{job_id}/retry-book/{book_id}
@router.post("/book-search-jobs/{job_id}/retry-book/{book_id}/")
@router.post("/book-search-jobs/{job_id}/retry-book/{book_id}", include_in_schema=False)
async def retry_book_search(
    job_id: str,
    book_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Trigger an isolated retry for an individual failed or timed-out book within a job.
    """
    updated_job = await BookSearchJobManager.retry_single_book(job_id, book_id)
    if not updated_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' or book #{book_id} within the job was not found."
        )
    return {
        "message": f"Retry initiated for book #{book_id}",
        "job": updated_job
    }
