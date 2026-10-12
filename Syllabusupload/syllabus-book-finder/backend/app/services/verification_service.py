import re
import io
import zipfile
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple
import httpx
from sqlalchemy.orm import Session

from app.models.discovery_rag import ResourceVerificationLog
from app.utils.security import validate_download_url_security

logger = logging.getLogger(__name__)

# Verification outcome labels (Section 7 & 8)
OUTCOME_VERIFIED = "VERIFIED"
OUTCOME_LINK_UNAVAILABLE = "LINK_UNAVAILABLE"          # 404
OUTCOME_ACCESS_REQUIRED = "ACCESS_REQUIRED"            # 401
OUTCOME_ACCESS_RESTRICTED = "ACCESS_RESTRICTED"        # 403
OUTCOME_RATE_LIMITED = "RATE_LIMITED"                  # 429
OUTCOME_REPO_UNAVAILABLE = "REPOSITORY_UNAVAILABLE"    # 500-599
OUTCOME_TIMEOUT = "TIMEOUT"                            # Connect/read timeout
OUTCOME_INVALID_FILE = "INVALID_FILE_RESPONSE"         # HTML instead of binary PDF/EPUB
OUTCOME_OVERSIZED = "OVERSIZED_FILE"

FRIENDLY_ERROR_MESSAGE = (
    "This file is currently unavailable from the selected source. "
    "The system is checking alternative sources."
)

MAX_VERIFY_SIZE_BYTES = 100 * 1024 * 1024  # 100MB ceiling
HEADER_RANGE_BYTES = 2048

def verify_magic_bytes(header_bytes: bytes) -> Tuple[bool, str]:
    """
    Check for %PDF- or EPUB mimetype container.
    """
    if not header_bytes or len(header_bytes) < 4:
        return False, "Empty or insufficient byte stream"

    # 1. PDF Check
    if b"%PDF-" in header_bytes[:1024]:
        return True, "application/pdf"

    # 2. EPUB (Zip archive with mimetype file starting at offset 30 containing application/epub+zip)
    if header_bytes[:4] == b"PK\x03\x04":
        try:
            zf = zipfile.ZipFile(io.BytesIO(header_bytes))
            if "mimetype" in zf.namelist():
                content = zf.read("mimetype").decode("utf-8", errors="ignore").strip()
                if "application/epub+zip" in content:
                    return True, "application/epub+zip"
        except Exception:
            # First 2048 bytes might not be complete zip, but check if contains 'mimetypeapplication/epub+zip'
            if b"mimetypeapplication/epub+zip" in header_bytes or b"application/epub+zip" in header_bytes:
                return True, "application/epub+zip"

    return False, "Unknown or invalid magic signature"

async def pre_validate_candidate_url(
    url: str,
    db: Optional[Session] = None,
    book_source_id: Optional[int] = None,
    book_file_id: Optional[int] = None,
    user_id: Optional[int] = None,
    client: Optional[httpx.AsyncClient] = None
) -> Dict[str, Any]:
    """
    9-Step Server-Side Pre-Validation Pipeline (Specification Sections 7 & 8):
    1. Resolve candidate URL & security checks (SSRF)
    2. Follow limited number of redirects (max 5)
    3. Confirm final response status (200 or 206)
    4. Confirm MIME type (application/pdf or application/epub+zip)
    5. Download small byte range (first 2048 bytes)
    6. Verify file signature (%PDF- or EPUB signature)
    7. Reject HTML login pages and error pages
    8. Check file size (within allowed bounds)
    9. Record verification outcome in ResourceVerificationLog
    """
    if not url or not url.strip():
        return {
            "is_valid": False,
            "outcome": OUTCOME_LINK_UNAVAILABLE,
            "status_label": "Link unavailable",
            "http_status": 404,
            "mime_type": None,
            "signature": None,
            "file_size": 0,
            "friendly_message": FRIENDLY_ERROR_MESSAGE,
            "user_can_download": False,
            "error_detail": "No URL provided."
        }

    # Step 1: Security validation (prevents SSRF to internal localhost/private subnets)
    try:
        validate_download_url_security(url)
    except Exception as ssrf_err:
        return {
            "is_valid": False,
            "outcome": OUTCOME_ACCESS_RESTRICTED,
            "status_label": "Access restricted",
            "http_status": 403,
            "mime_type": None,
            "signature": None,
            "file_size": 0,
            "friendly_message": FRIENDLY_ERROR_MESSAGE,
            "user_can_download": False,
            "error_detail": f"Security restriction: {str(ssrf_err)}"
        }

    close_client = False
    if client is None:
        client = httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=5,
            timeout=httpx.Timeout(8.0, connect=4.0)
        )
        close_client = True

    outcome = OUTCOME_LINK_UNAVAILABLE
    status_label = "Link unavailable"
    http_code = 0
    mime_type = None
    sig_valid = False
    sig_str = None
    file_size = 0
    final_url = url
    error_msg = None

    try:
        # Step 2 & 5: Stream initial bytes with Range header
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SyllabusBookFinder/1.0 (Academic Pre-Validator)",
            "Range": f"bytes=0-{HEADER_RANGE_BYTES - 1}"
        }

        async with client.stream("GET", url, headers=headers) as resp:
            final_url = str(resp.url)
            http_code = resp.status_code

            # Validate each redirect for SSRF safety
            for hist in resp.history:
                try:
                    validate_download_url_security(str(hist.url))
                except Exception:
                    raise PermissionError("Redirected to prohibited network destination.")

            # Step 8 status trapping (404, 401, 403, 429, 500-599)
            if http_code == 404:
                outcome = OUTCOME_LINK_UNAVAILABLE
                status_label = "Link unavailable"
                error_msg = "Resource not found (HTTP 404)."
            elif http_code == 401:
                outcome = OUTCOME_ACCESS_REQUIRED
                status_label = "Access required"
                error_msg = "Authentication or credentials required (HTTP 401)."
            elif http_code == 403:
                outcome = OUTCOME_ACCESS_RESTRICTED
                status_label = "Access restricted"
                error_msg = "Access restricted / forbidden (HTTP 403)."
            elif http_code == 429:
                outcome = OUTCOME_RATE_LIMITED
                status_label = "Rate limited"
                error_msg = "Upstream rate limit exceeded (HTTP 429)."
            elif 500 <= http_code <= 599:
                outcome = OUTCOME_REPO_UNAVAILABLE
                status_label = "Repository temporarily unavailable"
                error_msg = f"Server error at repository (HTTP {http_code})."
            elif http_code in (200, 206):
                # Step 4: Confirm MIME type
                ct = resp.headers.get("content-type", "").lower()
                mime_type = ct.split(";")[0].strip()

                cl = resp.headers.get("content-length")
                if cl and cl.isdigit():
                    file_size = int(cl)

                # Step 7: Reject HTML login/error pages
                if "text/html" in ct:
                    outcome = OUTCOME_INVALID_FILE
                    status_label = "Invalid file response"
                    error_msg = "Returned HTML page instead of PDF/EPUB binary."
                else:
                    # Step 5: Read initial byte range
                    initial_bytes = b""
                    async for chunk in resp.aiter_bytes():
                        initial_bytes += chunk
                        if len(initial_bytes) >= HEADER_RANGE_BYTES:
                            break

                    # Step 7 check for HTML in byte stream
                    lower_bytes = initial_bytes[:1024].lower()
                    if b"<!doctype html" in lower_bytes or b"<html" in lower_bytes or b"<head" in lower_bytes:
                        outcome = OUTCOME_INVALID_FILE
                        status_label = "Invalid file response"
                        error_msg = "Stream contains HTML text."
                    else:
                        # Step 6: Verify file signature
                        sig_valid, detected_format = verify_magic_bytes(initial_bytes)
                        if sig_valid:
                            sig_str = "%PDF-" if "pdf" in detected_format else "EPUB"
                            if file_size > MAX_VERIFY_SIZE_BYTES:
                                outcome = OUTCOME_OVERSIZED
                                status_label = "File size exceeded"
                                error_msg = f"Size ({file_size / (1024*1024):.1f} MB) exceeds maximum allowed limit."
                            else:
                                outcome = OUTCOME_VERIFIED
                                status_label = "Direct PDF Available" if "pdf" in detected_format else "Direct EPUB Available"
                                error_msg = None
                        else:
                            outcome = OUTCOME_INVALID_FILE
                            status_label = "Invalid file signature"
                            error_msg = "Initial bytes do not match %PDF- or EPUB signature."
            else:
                outcome = OUTCOME_REPO_UNAVAILABLE
                status_label = "Repository temporarily unavailable"
                error_msg = f"Unexpected response status HTTP {http_code}."

    except httpx.TimeoutException:
        outcome = OUTCOME_TIMEOUT
        status_label = "Verification pending"
        http_code = 408
        error_msg = "Repository connection timed out."
    except Exception as exc:
        outcome = OUTCOME_REPO_UNAVAILABLE
        status_label = "Repository temporarily unavailable"
        error_msg = str(exc)
    finally:
        if close_client:
            await client.aclose()

    is_valid = (outcome == OUTCOME_VERIFIED)

    # Step 9: Record verification result in ResourceVerificationLog
    if db is not None:
        try:
            log_entry = ResourceVerificationLog(
                book_source_id=book_source_id,
                book_file_id=book_file_id,
                source_url=url,
                final_url=final_url,
                http_status_code=http_code,
                mime_type=mime_type,
                is_valid_signature=sig_valid,
                file_signature=sig_str,
                file_size_bytes=file_size,
                verification_outcome=outcome,
                error_detail=error_msg,
                user_id=user_id
            )
            db.add(log_entry)
            db.commit()
        except Exception as log_err:
            logger.debug(f"Could not persist verification log: {log_err}")

    return {
        "is_valid": is_valid,
        "outcome": outcome,
        "status_label": status_label,
        "http_status": http_code,
        "mime_type": mime_type,
        "signature": sig_str,
        "file_size": file_size,
        "friendly_message": None if is_valid else FRIENDLY_ERROR_MESSAGE,
        "user_can_download": is_valid,
        "error_detail": error_msg,
        "final_url": final_url
    }
