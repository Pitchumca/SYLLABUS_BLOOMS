import os
import re
import uuid
import socket
import ipaddress
import urllib.parse
from pathlib import Path
from typing import Tuple, List, Optional
from fastapi import HTTPException, UploadFile, status
from app.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".ppt", ".docx", ".txt"}
ALLOWED_MIME_TYPES = {
    "application/pdf", 
    "application/x-pdf", 
    "application/acrobat", 
    "applications/vnd.pdf", 
    "text/pdf", 
    "text/x-pdf",
    "application/octet-stream",
    "binary/octet-stream",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain"
}
PDF_MAGIC_BYTES = b"%PDF"
ZIP_MAGIC_BYTES = b"PK\x03\x04" # DOCX & PPTX are zip archives

APPROVED_HOSTNAMES = [
    "archive.org",
    "openstax.org",
    "doabooks.org",
    "oercommons.org",
    "ocw.mit.edu",
    "nptel.ac.in",
    "open.umn.edu",
    "pressbooks.pub",
    "openlibra.com",
    "libretexts.org",
    "gutenberg.org",
    "arxiv.org",
    "crossref.org",
    "api.crossref.org",
    "openlibrary.org",
    "googleapis.com",
    "books.google.com",
    "worldcat.org"
]

APPROVED_SUFFIXES = [".edu", ".ac.in", ".edu.au", ".ac.uk", ".edu.sg"]

def is_approved_hostname(hostname: str) -> bool:
    """Check if hostname is in whitelist or is a subdomain of an approved repository."""
    if not hostname:
        return False
    h = hostname.lower().strip()
    # Exact or subdomain of approved hostnames (e.g. dn790006.ca.archive.org ends with .archive.org)
    for approved in APPROVED_HOSTNAMES:
        if h == approved or h.endswith("." + approved):
            return True
    for suffix in APPROVED_SUFFIXES:
        if h.endswith(suffix):
            return True
    return False

def is_ip_private_or_restricted(ip_str: str) -> bool:
    """Verify if IP belongs to private, loopback, link-local or reserved ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private or
            ip.is_loopback or
            ip.is_link_local or
            ip.is_reserved or
            ip.is_multicast or
            ip.is_unspecified
        )
    except ValueError:
        return True

def validate_download_url_security(url: str) -> None:
    """
    Validate download URL for SSRF protection:
    1. Scheme must be HTTP or HTTPS
    2. Hostname must be in approved repositories
    3. Hostname must not resolve to localhost, private IP or internal network
    """
    if not url:
        raise ValueError("URL cannot be empty.")

    parsed = urllib.parse.urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"Disallowed URL scheme '{scheme}'. Only HTTP and HTTPS are permitted.")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("URL has no hostname.")

    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ValueError("Requests to localhost and loopback are strictly blocked.")

    if not is_approved_hostname(hostname):
        raise ValueError(f"Host '{hostname}' is not an approved repository hostname.")

    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if is_ip_private_or_restricted(ip_str):
                raise ValueError(f"Host '{hostname}' resolved to blocked private/internal IP ({ip_str}).")
    except socket.gaierror as ge:
        raise ValueError(f"Failed to resolve host '{hostname}': {ge}")

def sanitize_filename(filename: str) -> str:
    """Strip dangerous characters and directory separators from a filename."""
    clean_name = os.path.basename(filename)
    clean_name = re.sub(r'[^a-zA-Z0-9._-]', '_', clean_name)
    clean_name = clean_name.lstrip('.')
    if not clean_name:
        clean_name = "document.bin"
    return clean_name

def generate_safe_stored_filename(original_filename: str) -> str:
    """Generate a unique, safe filename for local storage."""
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".pdf"
    safe_token = uuid.uuid4().hex[:12]
    safe_base = re.sub(r'[^a-zA-Z0-9_-]', '_', Path(original_filename).stem)[:40]
    return f"{safe_base}_{safe_token}{ext}"

def validate_path_traversal(target_path: Path, base_dir: Path) -> Path:
    """Ensure that the resolved target path stays within the designated base directory."""
    resolved_target = target_path.resolve()
    resolved_base = base_dir.resolve()
    try:
        resolved_target.relative_to(resolved_base)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal attempt detected."
        )
    return resolved_target

def validate_uploaded_file(
    file: UploadFile, 
    header_bytes: bytes, 
    file_size: int,
    allowed_exts: set = None
):
    """Validate file type, magic header, and file size constraints."""
    ext = Path(file.filename or "").suffix.lower()
    valid_exts = allowed_exts if allowed_exts is not None else {".pdf"}

    if ext not in valid_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension '{ext}'. Allowed extensions: {', '.join(sorted(valid_exts))}."
        )

    if ext == ".pdf":
        if PDF_MAGIC_BYTES not in header_bytes[:1024]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Corrupted or invalid PDF header. The file does not contain a valid %PDF marker."
            )
    elif ext in [".docx", ".pptx"]:
        if not header_bytes.startswith(ZIP_MAGIC_BYTES):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupted or invalid {ext.upper()} archive header."
            )

    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

def sanitize_input_text(text: str) -> str:
    """Sanitize user-provided text to avoid null bytes, control characters, and excess whitespace."""
    if not text:
        return ""
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    return sanitized.strip()
