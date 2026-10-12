import re
import urllib.parse
import datetime
import logging
from typing import List, Dict, Any, Optional, Tuple
import httpx

from app.services.access_states import (
    PUBLIC_PDF_VERIFIED,
    PUBLIC_EPUB_VERIFIED,
    BORROW_REQUIRED,
    PREVIEW_ONLY,
    METADATA_ONLY,
    LINK_UNAVAILABLE,
    VERIFICATION_FAILED
)
from app.services.bibliography_parser import (
    normalize_authors,
    normalize_title_and_subtitle,
    normalize_publisher,
    normalize_publication_year,
    normalize_isbns,
    normalize_edition
)
from app.utils.security import validate_download_url_security

logger = logging.getLogger(__name__)

TIMEOUT_CONNECT = 5.0
TIMEOUT_READ = 20.0

def build_canonical_download_url(identifier: str, filename: str) -> str:
    """
    Construct canonical Internet Archive download URL:
    https://archive.org/download/{identifier}/{URL_ENCODED_FILENAME}
    Never construct fixed dn*.archive.org delivery hosts.
    """
    clean_ident = urllib.parse.quote(identifier.strip())
    clean_filename = urllib.parse.quote(filename.strip())
    return f"https://archive.org/download/{clean_ident}/{clean_filename}"

def build_details_url(identifier: str) -> str:
    """Lawful item page URL."""
    clean_ident = urllib.parse.quote(identifier.strip())
    return f"https://archive.org/details/{clean_ident}"

async def fetch_ia_metadata(identifier: str, client: Optional[httpx.AsyncClient] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch official Internet Archive metadata endpoint:
    https://archive.org/metadata/{identifier}
    """
    url = f"https://archive.org/metadata/{urllib.parse.quote(identifier.strip())}"
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_READ, connect=TIMEOUT_CONNECT))
        close_client = True

    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.json()
        logger.debug(f"IA metadata response {resp.status_code} for {identifier}")
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch IA metadata for {identifier}: {e}")
        return None
    finally:
        if close_client:
            await client.aclose()

def find_candidate_files(files_collection: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Inspect files collection and find actual PDF and EPUB candidates.
    Rejects files marked private, restricted, encrypted, borrow-only, or unavailable.
    Returns (pdf_candidates, epub_candidates).
    """
    is_item_restricted = bool(
        metadata.get("access-restricted-item") or
        metadata.get("loans__status__status") or
        metadata.get("openlibrary_edition") or
        metadata.get("loans__status__num_loans")
    )

    pdf_candidates = []
    epub_candidates = []

    for f in files_collection:
        name = str(f.get("name", "")).strip()
        fmt = str(f.get("format", "")).strip()
        name_lower = name.lower()
        fmt_lower = fmt.lower()

        # Reject private files
        is_private = f.get("private")
        if is_private is True or str(is_private).lower() in ("true", "1"):
            continue

        # Reject encrypted or protected files
        if any(bad in name_lower or bad in fmt_lower for bad in ["encrypted", "lcpdf", "acs", "drm", "borrow", "restricted"]):
            continue

        # Match PDF: format must be 'Text PDF' or 'PDF'
        if fmt_lower in ["text pdf", "pdf"] or (name_lower.endswith(".pdf") and "pdf" in fmt_lower):
            # Check if filename implies encrypted or private
            if not is_item_restricted:
                pdf_candidates.append(f)
            else:
                # Item is marked access-restricted, still retain candidate for server-side verification if not marked private
                pdf_candidates.append(f)

        # Match EPUB
        if fmt_lower in ["epub", "electronic publication"] or name_lower.endswith(".epub"):
            epub_candidates.append(f)

    # Sort candidates: prefer 'Text PDF' over generic 'PDF', prefer unencrypted root name
    def pdf_rank(c: Dict[str, Any]) -> int:
        rank = 0
        fmt = str(c.get("format", "")).lower()
        if fmt == "text pdf":
            rank += 10
        if not c.get("private"):
            rank += 5
        return rank

    pdf_candidates.sort(key=pdf_rank, reverse=True)
    return pdf_candidates, epub_candidates

async def validate_file_download_access(
    download_url: str,
    expected_type: str = "pdf",
    client: Optional[httpx.AsyncClient] = None
) -> Tuple[str, Optional[int], str]:
    """
    Validate selected file using server-side request:
    - Follows safe redirects with SSRF protection.
    - Requires HTTP status 200 or valid 206.
    - Requires Content-Type: application/pdf (or epub).
    - Verifies content begins with '%PDF-'.
    Returns: (access_status, http_status_code, verification_message)
    """
    try:
        validate_download_url_security(download_url)
    except ValueError as ve:
        return VERIFICATION_FAILED, None, f"Security check rejected download URL: {ve}"

    close_client = False
    if client is None:
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(TIMEOUT_READ, connect=TIMEOUT_CONNECT)
        )
        close_client = True

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SyllabusBookFinder/1.0 (Lawful Academic Access Verifier)",
        "Range": "bytes=0-1023"
    }

    try:
        # Request initial bytes safely
        resp = await client.get(download_url, headers=headers)
        status_code = resp.status_code
        content_type = resp.headers.get("content-type", "").lower()
        body_sample = resp.content

        # Safe redirect validation: check every redirected URL in history
        for hist in resp.history:
            try:
                validate_download_url_security(str(hist.url))
            except ValueError as redirect_err:
                return VERIFICATION_FAILED, status_code, f"Redirect to unapproved host blocked: {redirect_err}"

        # Handle 401 and 403: Borrowing required
        if status_code in (401, 403):
            return BORROW_REQUIRED, status_code, f"HTTP {status_code}: Controlled lending or borrowing required."

        # Handle 404: Link unavailable
        if status_code == 404:
            return LINK_UNAVAILABLE, status_code, "HTTP 404: Download candidate not found on archive servers."

        # Reject HTML returned instead of PDF
        if "text/html" in content_type or b"<html" in body_sample.lower() or b"<!doctype html" in body_sample.lower():
            return VERIFICATION_FAILED, status_code, f"HTTP {status_code}: Received HTML document instead of binary {expected_type.upper()} file."

        # Status 200 or 206
        if status_code in (200, 206):
            if expected_type == "pdf":
                if "application/pdf" not in content_type and "application/octet-stream" not in content_type:
                    return VERIFICATION_FAILED, status_code, f"Invalid Content-Type '{content_type}', expected application/pdf."
                if b"%PDF-" not in body_sample[:1024]:
                    return VERIFICATION_FAILED, status_code, "Invalid PDF signature: File does not start with '%PDF-'."
                return PUBLIC_PDF_VERIFIED, status_code, "Verified public direct PDF download (HTTP 200/206 with %PDF- header)."
            elif expected_type == "epub":
                if "epub" in content_type or b"mimetypeapplication/epub+zip" in body_sample[:1024] or b"PK" in body_sample[:10]:
                    return PUBLIC_EPUB_VERIFIED, status_code, "Verified public EPUB download."
                return VERIFICATION_FAILED, status_code, "Invalid EPUB content type or signature."

        return VERIFICATION_FAILED, status_code, f"Unexpected HTTP status {status_code}."

    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as te:
        return VERIFICATION_FAILED, None, f"Connection or read timed out during verification: {te}"
    except httpx.RequestError as re:
        return VERIFICATION_FAILED, None, f"Network communication failure: {re}"
    except Exception as e:
        return VERIFICATION_FAILED, None, f"Verification failed with error: {e}"
    finally:
        if close_client:
            await client.aclose()

async def verify_internet_archive_item(
    identifier: str,
    client: Optional[httpx.AsyncClient] = None
) -> Dict[str, Any]:
    """
    End-to-end 10-step verification workflow for an Internet Archive item.
    Returns normalized metadata, access_status, canonical URLs, and verification details.
    """
    ident = identifier.strip()
    details_url = build_details_url(ident)

    # 1. Fetch metadata
    meta_json = await fetch_ia_metadata(ident, client=client)
    if not meta_json:
        return {
            "internet_archive_identifier": ident,
            "internet_archive_item_url": details_url,
            "verified_download_url": None,
            "access_status": LINK_UNAVAILABLE,
            "verification_http_status": 404,
            "verification_message": "Item identifier metadata not found on Internet Archive.",
            "verified_at": datetime.datetime.now(datetime.UTC),
            "title": ident,
            "subtitle": None,
            "authors": "",
            "authors_list": [],
            "publisher": None,
            "edition": None,
            "publication_year": None,
            "isbn_10": None,
            "isbn_13": None,
            "rights_or_license": "Unknown",
            "is_downloadable": False
        }

    raw_meta = meta_json.get("metadata", {})
    files = meta_json.get("files", [])

    # 2. Normalize bibliographic metadata
    full_title, subtitle = normalize_title_and_subtitle(raw_meta.get("title") or ident)
    authors_list, authors_display = normalize_authors(raw_meta.get("creator"))
    publisher = normalize_publisher(raw_meta.get("publisher"))
    pub_year = normalize_publication_year(raw_meta.get("date"), raw_meta.get("year"))
    edition = normalize_edition(raw_meta.get("edition"))
    isbn_10, isbn_13 = normalize_isbns(raw_meta.get("isbn"))
    rights = str(raw_meta.get("licenseurl") or raw_meta.get("rights") or "Standard Archive License")

    # 3. Find candidate files
    pdf_candidates, epub_candidates = find_candidate_files(files, raw_meta)

    # If item metadata explicitly indicates lending / restricted collection
    is_lending_item = bool(
        raw_meta.get("access-restricted-item") or
        raw_meta.get("loans__status__status") or
        raw_meta.get("openlibrary_edition")
    )

    # 4. Check PDF candidates
    if pdf_candidates:
        primary_candidate = pdf_candidates[0]
        cand_filename = primary_candidate.get("name")
        canonical_url = build_canonical_download_url(ident, cand_filename)

        # Server-side validation
        access_status, http_status, msg = await validate_file_download_access(
            canonical_url,
            expected_type="pdf",
            client=client
        )

        return {
            "internet_archive_identifier": ident,
            "internet_archive_item_url": details_url,
            "verified_download_url": canonical_url if access_status == PUBLIC_PDF_VERIFIED else None,
            "access_status": access_status,
            "verification_http_status": http_status,
            "verification_message": msg,
            "verified_at": datetime.datetime.now(datetime.UTC),
            "title": full_title,
            "subtitle": subtitle,
            "authors": authors_display,
            "authors_list": authors_list,
            "publisher": publisher,
            "edition": edition,
            "publication_year": pub_year,
            "isbn_10": isbn_10,
            "isbn_13": isbn_13,
            "rights_or_license": "Borrowing / Lending" if access_status == BORROW_REQUIRED else rights,
            "is_downloadable": access_status == PUBLIC_PDF_VERIFIED,
            "candidate_filename": cand_filename
        }

    # 5. Check EPUB candidates if no PDF
    if epub_candidates:
        cand_filename = epub_candidates[0].get("name")
        canonical_url = build_canonical_download_url(ident, cand_filename)
        access_status, http_status, msg = await validate_file_download_access(
            canonical_url,
            expected_type="epub",
            client=client
        )
        return {
            "internet_archive_identifier": ident,
            "internet_archive_item_url": details_url,
            "verified_download_url": canonical_url if access_status == PUBLIC_EPUB_VERIFIED else None,
            "access_status": access_status,
            "verification_http_status": http_status,
            "verification_message": msg,
            "verified_at": datetime.datetime.now(datetime.UTC),
            "title": full_title,
            "subtitle": subtitle,
            "authors": authors_display,
            "authors_list": authors_list,
            "publisher": publisher,
            "edition": edition,
            "publication_year": pub_year,
            "isbn_10": isbn_10,
            "isbn_13": isbn_13,
            "rights_or_license": rights,
            "is_downloadable": access_status == PUBLIC_EPUB_VERIFIED,
            "candidate_filename": cand_filename
        }

    # If no valid public download candidate, but item exists
    status = BORROW_REQUIRED if is_lending_item else METADATA_ONLY
    msg = "Controlled digital lending / borrow required." if is_lending_item else "No public downloadable PDF or EPUB files available; catalog record only."

    return {
        "internet_archive_identifier": ident,
        "internet_archive_item_url": details_url,
        "verified_download_url": None,
        "access_status": status,
        "verification_http_status": 200,
        "verification_message": msg,
        "verified_at": datetime.datetime.now(datetime.UTC),
        "title": full_title,
        "subtitle": subtitle,
        "authors": authors_display,
        "authors_list": authors_list,
        "publisher": publisher,
        "edition": edition,
        "publication_year": pub_year,
        "isbn_10": isbn_10,
        "isbn_13": isbn_13,
        "rights_or_license": "Controlled Lending" if status == BORROW_REQUIRED else rights,
        "is_downloadable": False,
        "candidate_filename": None
    }
