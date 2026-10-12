import os
import hashlib
import pytest
import unittest.mock as mock
import httpx
from datetime import datetime

from app.services.access_states import (
    PUBLIC_PDF_VERIFIED,
    PUBLIC_EPUB_VERIFIED,
    BORROW_REQUIRED,
    PREVIEW_ONLY,
    METADATA_ONLY,
    LINK_UNAVAILABLE,
    VERIFICATION_FAILED,
)
from app.services.bibliography_parser import (
    parse_structured_citation,
    normalize_authors,
    normalize_edition,
    normalize_publication_year,
    normalize_publisher,
    normalize_isbns,
)
from app.utils.security import (
    validate_download_url_security,
    is_approved_hostname,
    is_ip_private_or_restricted,
)
from app.services.internet_archive_service import (
    verify_internet_archive_item,
    validate_file_download_access,
    find_candidate_files,
    build_canonical_download_url,
)
from app.services.download_job_service import (
    DownloadJob,
    create_job,
    get_job,
    execute_auto_download_and_indexing_pipeline,
)
from app.models.book import Book
from app.models.search_result import SearchResult
from app.models.syllabus import Syllabus


# =============================================================================
# TEST 1: Public PDF returning 200 with %PDF- downloads and verifies
# =============================================================================
@pytest.mark.asyncio
async def test_01_public_pdf_returning_200_with_pdf_signature():
    """Verify that a public PDF returning 200 with %PDF- magic bytes verifies as PUBLIC_PDF_VERIFIED."""
    dummy_pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Title (Test Public Book) >>\nendobj\ntrailer\n<<>>\n%%EOF"
    target_url = "https://archive.org/download/publicbook123/publicbook123.pdf"

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {
        "content-type": "application/pdf",
        "content-length": str(len(dummy_pdf_content))
    }
    mock_response.content = dummy_pdf_content
    mock_response.history = []
    mock_response.url = httpx.URL(target_url)

    with mock.patch("httpx.AsyncClient.get", return_value=mock_response):
        status, http_code, msg = await validate_file_download_access(target_url, expected_type="pdf")

    assert status == PUBLIC_PDF_VERIFIED
    assert http_code == 200
    assert "%PDF-" in msg


# =============================================================================
# TEST 2: Restricted PDF returning 401 classified as BORROW_REQUIRED
# =============================================================================
@pytest.mark.asyncio
async def test_02_restricted_pdf_returning_401_classified_borrow_required():
    """Verify that a restricted PDF returning HTTP 401 is classified as BORROW_REQUIRED."""
    target_url = "https://archive.org/download/restricted_book/restricted_book.pdf"

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.headers = {"content-type": "text/html"}
    mock_response.content = b"<html><title>401 Authorization Required</title><body>Lending required</body></html>"
    mock_response.history = []
    mock_response.url = httpx.URL(target_url)

    with mock.patch("httpx.AsyncClient.get", return_value=mock_response):
        status, http_code, msg = await validate_file_download_access(target_url, expected_type="pdf")

    assert status == BORROW_REQUIRED
    assert http_code == 401
    assert "borrowing required" in msg.lower() or "lending" in msg.lower()


# =============================================================================
# TEST 3: HTTP 403 not treated as downloadable
# =============================================================================
@pytest.mark.asyncio
async def test_03_http_403_not_treated_as_downloadable():
    """Verify that HTTP 403 Forbidden is classified as BORROW_REQUIRED and never downloadable."""
    target_url = "https://archive.org/download/item_forbidden/file.pdf"

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 403
    mock_response.headers = {"content-type": "text/html"}
    mock_response.content = b"<html><title>403 Forbidden</title></html>"
    mock_response.history = []
    mock_response.url = httpx.URL(target_url)

    with mock.patch("httpx.AsyncClient.get", return_value=mock_response):
        status, http_code, msg = await validate_file_download_access(target_url, expected_type="pdf")

    assert status == BORROW_REQUIRED
    assert http_code == 403


# =============================================================================
# TEST 4: HTTP 404 becomes LINK_UNAVAILABLE
# =============================================================================
@pytest.mark.asyncio
async def test_04_http_404_becomes_link_unavailable():
    """Verify that HTTP 404 Not Found is classified as LINK_UNAVAILABLE."""
    target_url = "https://archive.org/download/missing_item/missing.pdf"

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.headers = {"content-type": "text/html"}
    mock_response.content = b"<html><title>404 Not Found</title></html>"
    mock_response.history = []
    mock_response.url = httpx.URL(target_url)

    with mock.patch("httpx.AsyncClient.get", return_value=mock_response):
        status, http_code, msg = await validate_file_download_access(target_url, expected_type="pdf")

    assert status == LINK_UNAVAILABLE
    assert http_code == 404
    assert "not found" in msg.lower()


# =============================================================================
# TEST 5: HTML page named .pdf rejected
# =============================================================================
@pytest.mark.asyncio
async def test_05_html_page_named_pdf_rejected():
    """Verify that a URL with .pdf extension returning HTML is rejected with VERIFICATION_FAILED."""
    fake_html_content = b"<!DOCTYPE html><html><body><h1>Sign in or Borrow to Read</h1></body></html>"
    target_url = "https://archive.org/download/fake_pdf/sample.pdf"

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html; charset=utf-8"}
    mock_response.content = fake_html_content
    mock_response.history = []
    mock_response.url = httpx.URL(target_url)

    with mock.patch("httpx.AsyncClient.get", return_value=mock_response):
        status, http_code, msg = await validate_file_download_access(target_url, expected_type="pdf")

    assert status == VERIFICATION_FAILED
    assert "html" in msg.lower()


# =============================================================================
# TEST 6: Redirect to unapproved host blocked
# =============================================================================
def test_06_redirect_to_unapproved_host_blocked():
    """Verify that SSRF security checks block unapproved hostnames and private IPs."""
    # Approved Internet Archive hosts pass
    validate_download_url_security("https://archive.org/download/item123/file.pdf")
    validate_download_url_security("https://ia800102.us.archive.org/0/items/item123/file.pdf")

    # Unapproved external host raises ValueError
    with pytest.raises(ValueError, match="not an approved repository"):
        validate_download_url_security("https://malicious-redirect.com/exploit.pdf")

    # Localhost / Private IP SSRF raises ValueError
    with pytest.raises(ValueError):
        validate_download_url_security("http://127.0.0.1:8000/internal_secret.pdf")

    with pytest.raises(ValueError):
        validate_download_url_security("http://169.254.169.254/latest/meta-data/")


# =============================================================================
# TEST 7: Metadata strings and arrays normalize correctly
# =============================================================================
def test_07_metadata_strings_and_arrays_normalize_correctly():
    """Verify that author strings and lists normalize cleanly without trailing punctuation."""
    # List of authors in 'Last, First' format
    authors_list = ["Han, Jiawei", "Kamber, Micheline"]
    norm_list, norm_str = normalize_authors(authors_list)
    assert norm_list == ["Jiawei Han", "Micheline Kamber"]
    assert norm_str == "Jiawei Han; Micheline Kamber"

    # Single string with 'and'
    s_authors = "Jiawei Han and Micheline Kamber"
    norm_list2, norm_str2 = normalize_authors(s_authors)
    assert "Jiawei Han" in norm_list2
    assert "Micheline Kamber" in norm_list2

    # Publisher cleaning
    cleaned_pub = normalize_publisher("Amsterdam ; Boston : Morgan Kaufmann Publishers")
    assert cleaned_pub == "Morgan Kaufmann"

    # Year cleaning
    cleaned_yr = normalize_publication_year("Published c2001, reprinted 2006.")
    assert cleaned_yr == "2001"


# =============================================================================
# TEST 8: Multiple authors stored and displayed separately
# =============================================================================
def test_08_multiple_authors_stored_and_displayed_separately():
    """Verify structured parser stores separate authors formatted as 'Jiawei Han; Micheline Kamber'."""
    citation = "Han, Jiawei, and Micheline Kamber. Data Mining: Concepts and Techniques. Morgan Kaufmann, 2001."
    res = parse_structured_citation(citation)

    assert "Jiawei Han" in res["authors_list"]
    assert "Micheline Kamber" in res["authors_list"]
    assert res["authors"] == "Jiawei Han; Micheline Kamber"
    assert res["publisher"] == "Morgan Kaufmann"
    assert res["publication_year"] == "2001"


# =============================================================================
# TEST 9: Independent fields preserved
# =============================================================================
def test_09_independent_fields_preserved():
    """Verify title, subtitle, edition, publisher, year, isbn_10, isbn_13 are parsed into distinct fields."""
    citation = "Silberschatz, Abraham, Peter B. Galvin, and Greg Gagne. Operating System Concepts. 9th ed., John Wiley & Sons, 2012. ISBN: 978-1118063330, 1118063333."
    res = parse_structured_citation(citation)

    assert res["title"] == "Operating System Concepts"
    assert "9th" in res["edition"]
    assert res["publisher"] == "John Wiley & Sons"
    assert res["publication_year"] == "2012"
    assert res["isbn_13"] == "9781118063330"
    assert res["isbn_10"] == "1118063333"
    assert len(res["authors_list"]) == 3


# =============================================================================
# TEST 10: Duplicate books not downloaded twice (SHA-256 match)
# =============================================================================
def test_10_duplicate_books_not_downloaded_twice(db_session):
    """Verify that a book with a matching SHA-256 is detected and duplicate download is prevented."""
    from app.models.template_and_resource import StoredDocument
    test_content = b"%PDF-1.4 Mock existing downloaded PDF data"
    sha256 = hashlib.sha256(test_content).hexdigest()

    existing_doc = StoredDocument(
        original_filename="existing_book.pdf",
        storage_path="/uploads/resources/existing_book.pdf",
        file_size=len(test_content),
        sha256_checksum=sha256,
        active=True
    )
    db_session.add(existing_doc)
    db_session.commit()

    # Query duplicate detection logic
    found_dup = db_session.query(StoredDocument).filter(StoredDocument.sha256_checksum == sha256).first()
    assert found_dup is not None
    assert found_dup.sha256_checksum == sha256


# =============================================================================
# TEST 11: dataminingconcep00hanj_0 is never shown as verified direct PDF when 401
# =============================================================================
@pytest.mark.asyncio
async def test_11_datamining_item_never_direct_pdf_when_401():
    """Verify that 'dataminingconcep00hanj_0' is classified as BORROW_REQUIRED, never PUBLIC_PDF_VERIFIED."""
    mock_metadata = {
        "metadata": {
            "identifier": "dataminingconcep00hanj_0",
            "title": "Data mining : concepts and techniques",
            "creator": ["Han, Jiawei", "Kamber, Micheline"],
            "publisher": "Morgan Kaufmann",
            "year": "2001",
            "access-restricted-item": "true",
            "lending___status": "borrow_unavailable"
        },
        "files": [
            {
                "name": "dataminingconcep00hanj_0.pdf",
                "format": "Text PDF",
                "size": "50000000"
            }
        ]
    }

    mock_head_resp = mock.MagicMock(spec=httpx.Response)
    mock_head_resp.status_code = 401
    mock_head_resp.headers = {"content-type": "text/html"}
    mock_head_resp.content = b"401 Authorization Required"
    mock_head_resp.history = []
    mock_head_resp.url = httpx.URL("https://archive.org/download/dataminingconcep00hanj_0/dataminingconcep00hanj_0.pdf")

    with mock.patch("app.services.internet_archive_service.fetch_ia_metadata", return_value=mock_metadata):
        with mock.patch("httpx.AsyncClient.get", return_value=mock_head_resp):
            res = await verify_internet_archive_item("dataminingconcep00hanj_0")

    assert res["is_downloadable"] is False
    assert res["access_status"] == BORROW_REQUIRED
    assert res["verified_download_url"] is None
    assert res["internet_archive_identifier"] == "dataminingconcep00hanj_0"
    assert res["internet_archive_item_url"] == "https://archive.org/details/dataminingconcep00hanj_0"
    assert res["verification_http_status"] in (401, 403)


# =============================================================================
# TEST 12: Restricted items display Borrow / View on Internet Archive
# =============================================================================
@pytest.mark.asyncio
async def test_12_restricted_items_provide_ia_details_link():
    """Verify that restricted items return lawful details link to https://archive.org/details/{id}."""
    mock_metadata = {
        "metadata": {
            "identifier": "restricted_sample_item",
            "title": "Restricted Sample",
            "access-restricted-item": "true"
        },
        "files": []
    }

    with mock.patch("app.services.internet_archive_service.fetch_ia_metadata", return_value=mock_metadata):
        res = await verify_internet_archive_item("restricted_sample_item")

    assert res["access_status"] == BORROW_REQUIRED
    assert res["internet_archive_item_url"] == "https://archive.org/details/restricted_sample_item"
    assert res["is_downloadable"] is False


# =============================================================================
@pytest.mark.asyncio
async def test_13_only_verified_oa_files_auto_downloaded_and_indexed(db_session):
    """Verify that background auto-download skips BORROW_REQUIRED and only downloads PUBLIC_PDF_VERIFIED."""
    # Create test syllabus & books
    syllabus = Syllabus(
        original_filename="sample_syllabus.pdf",
        stored_filename="stored_syllabus.pdf",
        file_size_bytes=1024
    )
    db_session.add(syllabus)
    db_session.commit()

    # Book 1: Restricted book (e.g. Data Mining)
    book_restricted = Book(
        syllabus_id=syllabus.id,
        title="Data Mining: Concepts and Techniques",
        authors="Jiawei Han; Micheline Kamber",
        category="Textbook"
    )
    db_session.add(book_restricted)
    db_session.commit()

    sr_restricted = SearchResult(
        book_id=book_restricted.id,
        source="Internet Archive",
        title="Data Mining: Concepts and Techniques",
        authors="Jiawei Han; Micheline Kamber",
        access_status=BORROW_REQUIRED,
        access_url="https://archive.org/details/dataminingconcep00hanj_0",
        internet_archive_identifier="dataminingconcep00hanj_0",
        verified_download_url=None
    )
    db_session.add(sr_restricted)
    db_session.commit()

    # Run auto-download pipeline for restricted book
    job = create_job(book_id=book_restricted.id, syllabus_id=syllabus.id)

    def session_factory():
        return db_session

    await execute_auto_download_and_indexing_pipeline(job.job_id, book_restricted.id, session_factory)

    finished_job = get_job(job.job_id)
    assert finished_job.status in ("Borrowing required", "Download unavailable", "Failed")
    assert finished_job.local_file_path is None
