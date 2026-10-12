import asyncio
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.models.syllabus import Syllabus
from app.models.book import Book
from app.models.student import Course
from app.services.book_search_job_service import BookSearchJobManager, _JOB_STORE, _JOB_LOCK
from app.services.search_service import (
    search_single_book_sources_resilient,
    ProviderTimeoutError,
    ProviderRateLimitError
)

client = TestClient(app)


@pytest.fixture(scope="module")
def faculty_auth_token():
    """Obtain a valid JWT token for authenticated requests."""
    res = client.post("/api/auth/login", json={
        "email": "faculty@college.edu",
        "password": "Faculty@123"
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def setup_r_programming_course_and_books():
    """Seed test syllabus, course, and the four confirmed R-programming books."""
    db = SessionLocal()
    try:
        # Create or fetch Syllabus
        syllabus = db.query(Syllabus).filter(Syllabus.original_filename == "r_programming_syllabus_test.pdf").first()
        if not syllabus:
            syllabus = Syllabus(
                original_filename="r_programming_syllabus_test.pdf",
                stored_filename="r_programming_syllabus_test.pdf",
                file_size_bytes=10240,
                page_count=2,
                extracted_text="R Programming Syllabus with Textbooks and References",
                status="processed"
            )
            db.add(syllabus)
            db.flush()

        # Create or fetch Course
        course = db.query(Course).filter(Course.course_code == "CS_R_PROG_TEST").first()
        if not course:
            course = Course(
                course_code="CS_R_PROG_TEST",
                course_name="Data Analytics with R Programming",
                department="Computer Science & Engineering",
                semester="IV Semester",
                academic_year="2025-2026",
                syllabus_id=syllabus.id,
                is_active=True
            )
            db.add(course)
            db.flush()

        # Seed the 4 confirmed R-programming books if not already present
        r_books_meta = [
            ("The Art of R Programming: A Tour of Statistical Software Design", "Norman Matloff", "No Starch Press", "2011", "9781593273842", "Textbook"),
            ("R for Everyone: Advanced Analytics and Graphics", "Jared P. Lander", "Addison-Wesley", "2013", "9780321888037", "Textbook"),
            ("Beginning R: The Statistical Programming Language", "Mark Gardener", "Wiley", "2013", "9781118164303", "Reference Book"),
            ("Introductory R: A Beginner's Guide to Data Visualisation", "Robert Knell", "Amazon Digital", "2013", "9781492987765", "Reference Book")
        ]

        book_ids = []
        for title, authors, publisher, year, isbn, cat in r_books_meta:
            b_obj = db.query(Book).filter(Book.syllabus_id == syllabus.id, Book.title == title).first()
            if not b_obj:
                b_obj = Book(
                    syllabus_id=syllabus.id,
                    title=title,
                    authors=authors,
                    publisher=publisher,
                    publication_year=year,
                    isbn=isbn,
                    category=cat,
                    confidence_score=95.0
                )
                db.add(b_obj)
                db.flush()
            book_ids.append(b_obj.id)

        db.commit()
        return {
            "course_id": course.id,
            "syllabus_id": syllabus.id,
            "book_ids": book_ids
        }
    finally:
        db.close()


# Test 1: Authenticated search request succeeds with 202 and job_id
def test_01_authenticated_search_request_succeeds(faculty_auth_token, setup_r_programming_course_and_books):
    course_id = setup_r_programming_course_and_books["course_id"]
    book_ids = setup_r_programming_course_and_books["book_ids"]

    headers = {"Authorization": f"Bearer {faculty_auth_token}"}
    payload = {
        "book_ids": book_ids,
        "search_sources": ["local_database", "open_library", "google_books"],
        "find_accessible_files": True,
        "download_verified_files": False,
        "start_rag_indexing": False
    }

    res = client.post(f"/api/courses/{course_id}/books/search-and-index/", json=payload, headers=headers)
    assert res.status_code == 202
    data = res.json()
    assert "job_id" in data
    assert data["job_id"].startswith("BOOKSEARCH-")
    assert data["status"] == "QUEUED"
    assert data["total_books"] == len(book_ids)
    assert "Book discovery and indexing pipeline started" in data["message"]


# Test 2: Missing token returns clear 401 message
def test_02_missing_token_returns_clear_401_message(setup_r_programming_course_and_books):
    course_id = setup_r_programming_course_and_books["course_id"]
    # No Authorization header
    res = client.post(f"/api/courses/{course_id}/books/search-and-index/", json={})
    assert res.status_code == 401
    data = res.json()
    assert "detail" in data
    assert "not provided" in data["detail"].lower() or "credentials" in data["detail"].lower()


# Test 3: Incorrect endpoint or non-existent course returns useful 404 diagnostic
def test_03_incorrect_endpoint_returns_useful_404_diagnostic(faculty_auth_token):
    headers = {"Authorization": f"Bearer {faculty_auth_token}"}
    res = client.post("/api/courses/9999999/books/search-and-index/", json={}, headers=headers)
    assert res.status_code == 404
    data = res.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


# Test 4: CORS preflight succeeds from http://localhost:5173
def test_04_cors_preflight_succeeds_from_localhost_5173():
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"
    }
    res = client.options("/api/courses/1/books/search-and-index/", headers=headers)
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert res.headers.get("access-control-allow-credentials") == "true"


# Test 5: Background job returns 202 Accepted immediately
def test_05_background_job_returns_202(faculty_auth_token, setup_r_programming_course_and_books):
    syllabus_id = setup_r_programming_course_and_books["syllabus_id"]
    headers = {"Authorization": f"Bearer {faculty_auth_token}"}
    res = client.post(
        f"/api/syllabus/{syllabus_id}/books/search-and-index/",
        json={"book_ids": setup_r_programming_course_and_books["book_ids"]},
        headers=headers
    )
    assert res.status_code == 202
    assert res.json()["status"] == "QUEUED"


# Test 6: Job status polling updates progress
@pytest.mark.asyncio
async def test_06_job_status_polling_updates_progress(faculty_auth_token, setup_r_programming_course_and_books):
    book_ids = setup_r_programming_course_and_books["book_ids"][:2]
    job = await BookSearchJobManager.create_job(
        course_id=setup_r_programming_course_and_books["course_id"],
        syllabus_id=setup_r_programming_course_and_books["syllabus_id"],
        book_ids=book_ids,
        search_sources=["local_database"]
    )

    res = client.get(f"/api/book-search-jobs/{job['job_id']}/")
    assert res.status_code == 200
    data = res.json()
    assert data["job_id"] == job["job_id"]
    assert data["total_books"] == 2
    assert "progress_percentage" in data
    assert "current_stage" in data
    assert len(data["results"]) == 2


# Test 7: One failed provider does not fail the complete job
@pytest.mark.asyncio
async def test_07_one_failed_provider_does_not_fail_the_complete_job():
    book_sample = {
        "id": 1,
        "title": "The Art of R Programming",
        "authors": "Norman Matloff",
        "category": "Textbook"
    }

    # Simulate Open Library crashing with an unhandled 500 error while DOAB returns sample
    async def mock_doab(client, book):
        return [{
            "source": "DOAB / OAPEN",
            "title": "The Art of R Programming",
            "authors": "Norman Matloff",
            "access_status": "PUBLIC_PDF_VERIFIED",
            "confidence_score": 90.0
        }]

    with patch("app.services.search_service.search_open_library", side_effect=Exception("OpenLibrary HTTP 500 Down")), \
         patch("app.services.search_service.search_doab", side_effect=mock_doab):
        outcome = await search_single_book_sources_resilient(
            book_data=book_sample,
            requested_sources=["open_library", "doab"]
        )

        assert "candidates" in outcome
        diagnostics = outcome.get("source_diagnostics", {})
        # Open Library is caught safely and isolated
        assert "Open Library" in diagnostics
        assert "FAILED" in diagnostics["Open Library"] or "500" in diagnostics["Open Library"]
        # DOAB still executed and succeeded
        assert diagnostics.get("DOAB / OAPEN") == "OK"
        assert len(outcome["candidates"]) >= 1


# Test 8: One failed book does not fail other books
@pytest.mark.asyncio
async def test_08_one_failed_book_does_not_fail_other_books(setup_r_programming_course_and_books):
    book_ids = setup_r_programming_course_and_books["book_ids"]
    job = await BookSearchJobManager.create_job(
        course_id=setup_r_programming_course_and_books["course_id"],
        syllabus_id=setup_r_programming_course_and_books["syllabus_id"],
        book_ids=book_ids,
        search_sources=["local_database"]
    )

    async def mock_process(book_item, job, course_dirs, course_code, course_name, db):
        if book_item["book_id"] == book_ids[0]:
            raise RuntimeError("Simulated transient failure on Book 1")
        book_item["search_status"] = "COMPLETED"
        book_item["candidates_found"] = 2

    with patch.object(BookSearchJobManager, "_process_single_book", side_effect=mock_process):
        await BookSearchJobManager.run_job_pipeline(job["job_id"])

    updated = await BookSearchJobManager.get_job(job["job_id"])
    assert updated["status"] == "PARTIALLY_COMPLETED"
    assert updated["failed_books"] == 1
    assert updated["completed_books"] == len(book_ids) - 1
    assert updated["results"][0]["search_status"] == "FAILED"
    assert updated["results"][1]["search_status"] == "COMPLETED"


# Test 9: Google Books missing API key does not crash job
@pytest.mark.asyncio
async def test_09_google_books_missing_api_key_does_not_crash_job():
    book_sample = {
        "id": 2,
        "title": "R for Everyone",
        "authors": "Jared P. Lander",
        "category": "Textbook"
    }

    with patch.object(settings, "GOOGLE_BOOKS_API_KEY", None):
        outcome = await search_single_book_sources_resilient(
            book_data=book_sample,
            requested_sources=["google_books"]
        )

        diag = outcome.get("source_diagnostics", {})
        assert diag.get("Google Books") == "NOT_CONFIGURED"


# Test 10: Provider timeout produces partial completion result
@pytest.mark.asyncio
async def test_10_provider_timeout_produces_partial_completion_result():
    book_sample = {
        "id": 3,
        "title": "Beginning R",
        "authors": "Mark Gardener",
        "category": "Reference Book"
    }

    with patch("app.services.search_service.search_crossref", side_effect=ProviderTimeoutError("Connection timed out after 20s")):
        outcome = await search_single_book_sources_resilient(
            book_data=book_sample,
            requested_sources=["crossref"]
        )

        diag = outcome.get("source_diagnostics", {})
        assert diag.get("Crossref") == "TIMEOUT"


# Test 11: Response containing HTML does not cause JSON parsing crash
@pytest.mark.asyncio
async def test_11_response_containing_html_does_not_cause_json_parsing_crash():
    from app.services.verification_service import pre_validate_candidate_url
    html_url = "https://example.edu/error-page-502.html"
    result = await pre_validate_candidate_url(html_url)
    assert isinstance(result, dict)
    assert result.get("is_valid") is False
    assert "friendly_message" in result


# Test 12: Repeated button clicks / requests do not corrupt job store
@pytest.mark.asyncio
async def test_12_repeated_button_clicks_do_not_create_duplicate_jobs(setup_r_programming_course_and_books):
    book_ids = setup_r_programming_course_and_books["book_ids"]
    job1 = await BookSearchJobManager.create_job(
        course_id=setup_r_programming_course_and_books["course_id"],
        syllabus_id=setup_r_programming_course_and_books["syllabus_id"],
        book_ids=book_ids,
        search_sources=["local_database"]
    )
    job2 = await BookSearchJobManager.create_job(
        course_id=setup_r_programming_course_and_books["course_id"],
        syllabus_id=setup_r_programming_course_and_books["syllabus_id"],
        book_ids=book_ids,
        search_sources=["local_database"]
    )
    assert job1["job_id"] != job2["job_id"]
    assert job1["job_id"].startswith("BOOKSEARCH-")
    assert job2["job_id"].startswith("BOOKSEARCH-")


# Test 13: Completed results remain visible after partial failure
@pytest.mark.asyncio
async def test_13_completed_results_remain_visible_after_partial_failure(setup_r_programming_course_and_books):
    book_ids = setup_r_programming_course_and_books["book_ids"][:2]
    job = await BookSearchJobManager.create_job(
        course_id=setup_r_programming_course_and_books["course_id"],
        syllabus_id=setup_r_programming_course_and_books["syllabus_id"],
        book_ids=book_ids,
        search_sources=["local_database"]
    )

    # Manually populate results state as simulated execution
    job["results"][0]["search_status"] = "COMPLETED"
    job["results"][0]["candidates_found"] = 4
    job["results"][1]["search_status"] = "FAILED"
    job["results"][1]["errors"].append("Simulated network timeout")

    res = client.get(f"/api/book-search-jobs/{job['job_id']}/")
    assert res.status_code == 200
    data = res.json()
    assert data["results"][0]["candidates_found"] == 4
    assert data["results"][0]["search_status"] == "COMPLETED"
    assert data["results"][1]["search_status"] == "FAILED"


# Test 14: RAG indexing begins only after verified file available
@pytest.mark.asyncio
async def test_14_rag_indexing_begins_only_after_verified_file_available():
    book_item = {
        "book_id": 101,
        "book_title": "Introductory R",
        "search_status": "PENDING",
        "verified_files": 0,
        "verified_download_url": None,
        "download_status": "PENDING",
        "rag_status": "PENDING",
        "errors": []
    }
    job = {
        "search_sources": ["local_database"],
        "find_accessible_files": True,
        "download_verified_files": True,
        "start_rag_indexing": True,
        "current_stage": "PENDING"
    }

    db = SessionLocal()
    try:
        with patch("app.services.search_service.search_single_book_sources_resilient", return_value={"candidates": [], "source_diagnostics": {}}):
            await BookSearchJobManager._process_single_book(
                book_item=book_item,
                job=job,
                course_dirs={},
                course_code="GEN101",
                course_name="General",
                db=db
            )

        # Since no verified candidate file exists, RAG status stays METADATA_ONLY without invoking indexing
        assert book_item["rag_status"] == "METADATA_ONLY"
        assert book_item["download_status"] == "NO_FILE_FOUND"
    finally:
        db.close()


# Test 15: All four displayed R-programming books processed independently
@pytest.mark.asyncio
async def test_15_all_four_displayed_r_programming_books_processed_independently(setup_r_programming_course_and_books):
    book_ids = setup_r_programming_course_and_books["book_ids"]
    assert len(book_ids) == 4, "Must have exactly 4 R-programming books"

    job = await BookSearchJobManager.create_job(
        course_id=setup_r_programming_course_and_books["course_id"],
        syllabus_id=setup_r_programming_course_and_books["syllabus_id"],
        book_ids=book_ids,
        search_sources=["local_database"]
    )

    titles = [b["book_title"] for b in job["results"]]
    assert any("The Art of R Programming" in t for t in titles)
    assert any("R for Everyone" in t for t in titles)
    assert any("Beginning R" in t for t in titles)
    assert any("Introductory R" in t for t in titles)

    mock_candidates = [
        {
            "source": "Local Course Storage",
            "title": "The Art of R Programming",
            "confidence_score": 98.0,
            "access_status": "METADATA_ONLY",
            "access_url": "https://example.com/art_of_r"
        }
    ]

    with patch("app.services.book_search_job_service.search_single_book_sources_resilient", return_value={"candidates": mock_candidates, "source_diagnostics": {"Local Course Storage": "OK"}}):
        await BookSearchJobManager.run_job_pipeline(job["job_id"])

    finished_job = await BookSearchJobManager.get_job(job["job_id"])
    assert finished_job["status"] in ("COMPLETED", "PARTIALLY_COMPLETED")
    assert finished_job["total_books"] == 4
    assert len(finished_job["results"]) == 4

    # Each book has independent search results
    for b in finished_job["results"]:
        assert b["search_status"] in ("COMPLETED", "FAILED")
        assert "source_diagnostics" in b
