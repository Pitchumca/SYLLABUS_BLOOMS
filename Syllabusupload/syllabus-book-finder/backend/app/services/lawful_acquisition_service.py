import os
import re
import io
import time
import hashlib
import urllib.parse
import urllib.request
import datetime
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import fitz # PyMuPDF
from sqlalchemy.orm import Session

from app.config import settings
from app.models.template_and_resource import (
    ResourceRecord,
    StoredDocument,
    DocumentChunkModel,
    RightsVerificationLog,
    DownloadAuditLog
)
from app.models.syllabus import Syllabus
from app.services.alignment_engine import parse_syllabus_topics

logger = logging.getLogger(__name__)

# Approved Open-Access & Academic Repositories Whitelist (Specification A2)
WHITELISTED_DOMAINS = [
    "archive.org",
    "doabooks.org",
    "openstax.org",
    "oercommons.org",
    "ocw.mit.edu",
    "nptel.ac.in",
    "open.umn.edu",
    "pressbooks.pub",
    "openlibra.com",
    "libretexts.org",
    "gutenberg.org",
    "arxiv.org"
]

# University & Institutional Domain Suffixes
INSTITUTIONAL_SUFFIXES = [".edu", ".ac.in", ".edu.au", ".ac.uk", ".edu.sg"]

# Strictly Blocked Copyright-Infringing Domains (Specification A2 Step 1)
BLOCKED_DOMAINS = [
    "sci-hub",
    "libgen",
    "z-lib",
    "zlibrary",
    "b-ok",
    "bookfi",
    "booksc",
    "torrent",
    "piratebay",
    "shadow-libraries"
]

# Commercial Paywalled Platforms requiring institutional proxy credentials
PAYWALLED_DOMAINS = [
    "sciencedirect.com",
    "springer.com",
    "wiley.com",
    "ieeexplore.ieee.org",
    "tandfonline.com",
    "jstor.org"
]

MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024 # 50 MB limit

def extract_domain(url: str) -> str:
    """Extract clean lower-case hostname from URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        return netloc
    except Exception:
        return ""

def classify_and_verify_rights(
    url: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Evaluate URL and metadata against the 10-Tier Lawful Access Framework.
    Verifies whitelist eligibility and rejects blocked shadow libraries.
    """
    domain = extract_domain(url)
    meta = metadata or {}
    meta_licence = meta.get("licence") or meta.get("license") or ""
    meta_access = meta.get("access_type") or ""

    reasons = []

    # 1. Blocklist check: Immediate rejection for shadow libraries
    for blocked in BLOCKED_DOMAINS:
        if blocked in domain:
            return {
                "is_eligible": False,
                "access_type": "Restricted access",
                "licence": None,
                "source_repository": "Blocked Repository",
                "domain": domain,
                "reasons": [f"Domain '{domain}' matches blocked copyright-infringing platform '{blocked}'."],
                "can_download_and_index": False,
                "warning": "Strictly blocked under intellectual property compliance. Shadow libraries and infringing sites are not permitted."
            }

    # 2. Commercial paywalled platform check
    for paywall in PAYWALLED_DOMAINS:
        if paywall in domain:
            return {
                "is_eligible": False,
                "access_type": "Restricted access",
                "licence": None,
                "source_repository": domain,
                "domain": domain,
                "reasons": [f"Domain '{domain}' is a commercial paywalled publisher requiring institutional subscription credentials."],
                "can_download_and_index": False,
                "warning": "Direct automated indexing of commercial paywalled content is restricted. Use institutional single sign-on or catalogue linking."
            }

    # 3. Whitelisted Open-Access & OER Repositories
    is_whitelisted = any(domain == w or domain.endswith("." + w) for w in WHITELISTED_DOMAINS)
    is_institutional = any(domain.endswith(suffix) for suffix in INSTITUTIONAL_SUFFIXES)

    if is_whitelisted or is_institutional:
        if "openstax.org" in domain:
            access_type = "Open-access PDF"
            licence = meta_licence or "CC-BY 4.0"
            repo = "OpenStax OER"
        elif "doabooks.org" in domain:
            access_type = "Open-access PDF"
            licence = meta_licence or "Creative Commons / Open Access"
            repo = "Directory of Open Access Books (DOAB)"
        elif "oercommons.org" in domain:
            access_type = "Open-access PDF"
            licence = meta_licence or "Creative Commons"
            repo = "OER Commons"
        elif "gutenberg.org" in domain:
            access_type = "Public-domain PDF"
            licence = "Public Domain"
            repo = "Project Gutenberg"
        elif "archive.org" in domain:
            if "publicdomain" in url.lower() or "pre1929" in url.lower():
                access_type = "Public-domain PDF"
                licence = "Public Domain"
            else:
                access_type = "Open-access PDF"
                licence = meta_licence or "Community Open Text"
            repo = "Internet Archive"
        elif is_institutional:
            access_type = "Institutionally licensed"
            licence = meta_licence or "Educational Open Courseware"
            repo = f"Institutional Repository ({domain})"
        else:
            access_type = "Open-access PDF"
            licence = meta_licence or "Open Access"
            repo = domain

        return {
            "is_eligible": True,
            "access_type": access_type,
            "licence": licence,
            "source_repository": repo,
            "domain": domain,
            "reasons": [f"Verified repository '{repo}' is in institutional lawful-access whitelist."],
            "can_download_and_index": True,
            "warning": None
        }

    # 4. Unknown or General Web Domains
    if meta_access in ["Open-access PDF", "Public-domain PDF", "Creative Commons"]:
        return {
            "is_eligible": True,
            "access_type": meta_access,
            "licence": meta_licence or "Creative Commons",
            "source_repository": domain or "Open Educational Source",
            "domain": domain,
            "reasons": ["Explicit open access/public domain license claimed."],
            "can_download_and_index": True,
            "warning": "Verify copyright notice on document front matter."
        }

    return {
        "is_eligible": False,
        "access_type": "Unknown rights status",
        "licence": None,
        "source_repository": domain,
        "domain": domain,
        "reasons": [f"Domain '{domain}' is not on the pre-approved open access whitelist."],
        "can_download_and_index": False,
        "warning": "Faculty confirmation required for educational fair dealing or public domain verification."
    }

def verify_magic_pdf_bytes(first_bytes: bytes) -> bool:
    """Verify that the initial stream contains the valid PDF signature %PDF-."""
    if not first_bytes or len(first_bytes) < 5:
        return False
    # Check anywhere within first 1024 bytes for %PDF-
    return b"%PDF-" in first_bytes[:1024]

def download_and_validate_pdf_stream(
    url: str,
    target_path: Path,
    max_size: int = MAX_PDF_SIZE_BYTES
) -> Dict[str, Any]:
    """
    Execute lawful pre-fetch checks and streaming download with magic-byte verification.
    Computes SHA-256 checksum and returns document metadata.
    """
    domain = extract_domain(url)
    for blocked in BLOCKED_DOMAINS:
        if blocked in domain:
            raise ValueError(f"Download rejected: Domain '{domain}' is blacklisted.")

    # Target directory setup
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Setup request with user agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SyllabusBookFinder/1.0 (Educational Academic Indexer)"
    }
    req = urllib.request.Request(url, headers=headers)

    # 1. Pre-fetch HEAD check (or safe GET stream if HEAD not supported)
    file_size = 0
    sha256 = hashlib.sha256()
    first_chunk = True

    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            status_code = response.getcode()
            content_type = response.headers.get("Content-Type", "").lower()
            content_len = response.headers.get("Content-Length")

            if content_len:
                try:
                    expected_len = int(content_len)
                    if expected_len > max_size:
                        raise ValueError(f"Content-Length ({expected_len / (1024*1024):.1f} MB) exceeds maximum limit ({max_size / (1024*1024)} MB).")
                except ValueError as ve:
                    if "exceeds" in str(ve):
                        raise

            # Stream chunks and check magic bytes on first chunk
            with open(target_path, "wb") as f_out:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break

                    if first_chunk:
                        if not verify_magic_pdf_bytes(chunk):
                            raise ValueError("Invalid document signature: Initial bytes do not match '%PDF-'.")
                        first_chunk = False

                    file_size += len(chunk)
                    if file_size > max_size:
                        raise ValueError(f"Download size exceeded maximum allowed limit of {max_size / (1024*1024)} MB.")

                    sha256.update(chunk)
                    f_out.write(chunk)

    except Exception as e:
        if target_path.exists():
            try:
                target_path.unlink()
            except Exception:
                pass
        raise RuntimeError(f"Failed to acquire PDF from '{url}': {str(e)}")

    return {
        "file_path": str(target_path),
        "file_size": file_size,
        "sha256_checksum": sha256.hexdigest(),
        "mime_type": "application/pdf",
        "original_filename": target_path.name
    }

def extract_and_chunk_pdf(
    file_path: str,
    max_chunk_words: int = 700,
    overlap_words: int = 80
) -> List[Dict[str, Any]]:
    """
    Extract substantive text page-by-page using PyMuPDF (fitz).
    Splits into overlapping word chunks while discarding empty or cover pages.
    """
    chunks = []
    doc = fitz.open(file_path)

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        text = page.get_text("text")

        if not text or len(text.strip()) < 60:
            # Skip empty or negligible cover/spacer pages
            continue

        # Check if page is front-matter or pure TOC
        lower_sample = text[:300].lower()
        if page_num <= 3 and any(t in lower_sample for t in ["table of contents", "contents", "all rights reserved"]):
            pass # Keep text if substantive, but record page

        words = text.split()
        if len(words) <= max_chunk_words:
            chunks.append({
                "page_number": page_num,
                "text": text.strip(),
                "token_count": len(words),
                "chapter": None,
                "heading": f"Page {page_num}"
            })
        else:
            # Split into sliding windows
            start = 0
            while start < len(words):
                end = min(start + max_chunk_words, len(words))
                chunk_slice = " ".join(words[start:end])
                chunks.append({
                    "page_number": page_num,
                    "text": chunk_slice,
                    "token_count": end - start,
                    "chapter": None,
                    "heading": f"Page {page_num} (Part {start // (max_chunk_words - overlap_words) + 1})"
                })
                if end == len(words):
                    break
                start += (max_chunk_words - overlap_words)

    doc.close()
    return chunks

def align_chunks_with_syllabus(
    chunks: List[Dict[str, Any]],
    units: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Align document chunks with syllabus units using topic keyword matching.
    Calculates alignment_score between 0.0 and 1.0.
    """
    if not units:
        return chunks

    for c in chunks:
        c_text = c["text"].lower()
        best_unit = None
        best_topic = None
        best_score = 0.0

        for u in units:
            u_num = int(u.get("number") or 1)
            u_title = str(u.get("title", "")).lower()
            u_topics = parse_syllabus_topics(u.get("topics", ""))

            # Score against unit title
            score = 0.0
            title_words = [w for w in re.findall(r'\b[a-zA-Z]{3,}\b', u_title) if w not in ["and", "the", "for", "with", "unit"]]
            matched_title_words = [w for w in title_words if w in c_text]
            if title_words:
                score += (len(matched_title_words) / len(title_words)) * 0.4

            # Score against unit topics
            matched_topics = []
            for t in u_topics:
                t_lower = t.lower().strip()
                if len(t_lower) > 3 and t_lower in c_text:
                    matched_topics.append(t)

            if u_topics:
                score += min(0.6, (len(matched_topics) / max(1, len(u_topics))) * 0.6)

            if score > best_score:
                best_score = score
                best_unit = u_num
                best_topic = matched_topics[0] if matched_topics else (u.get("title") or f"Unit {u_num}")

        if best_score >= 0.2:
            c["unit_number"] = best_unit
            c["topic"] = best_topic
            c["co_level"] = f"CO{best_unit}"
            c["alignment_score"] = round(min(1.0, best_score * 1.5), 2)
        else:
            c["unit_number"] = 1
            c["topic"] = units[0].get("title", "Unit 1")
            c["co_level"] = "CO1"
            c["alignment_score"] = 0.15

        # Strictly unapproved by default: requires faculty review before RAG
        c["approved_for_generation"] = False

    return chunks

def acquire_and_index_lawful_pdf(
    db: Session,
    source_url: str,
    title: str,
    syllabus_id: Optional[int] = None,
    book_id: Optional[int] = None,
    authors: Optional[str] = None,
    publisher: Optional[str] = None,
    edition: Optional[str] = None,
    year: Optional[str] = None,
    isbn: Optional[str] = None,
    doi: Optional[str] = None,
    licence: Optional[str] = None,
    rights_statement: Optional[str] = None,
    source_repository: Optional[str] = None,
    faculty_override: bool = False,
    override_justification: Optional[str] = None,
    user_id: Optional[int] = None
) -> ResourceRecord:
    """
    End-to-end execution of the Lawful Online PDF Acquisition Workflow:
    1. Rights Verification & Whitelist Check
    2. Download & Magic Bytes Verification
    3. SHA-256 Duplicate Check (Reuses document if already stored)
    4. PyMuPDF Text Extraction & Chunking
    5. Syllabus Alignment
    6. Audit Logging & Record Creation
    """
    # Step 1: Rights Verification
    rights_info = classify_and_verify_rights(source_url, {"licence": licence})

    if not rights_info["is_eligible"] and not faculty_override:
        # Blocked
        audit = DownloadAuditLog(
            user_id=user_id,
            source_url=source_url,
            final_url=source_url,
            http_status_code=403,
            rights_status=rights_info["access_type"],
            status="blocked_unauthorized",
            failure_reason="; ".join(rights_info["reasons"])
        )
        db.add(audit)
        db.commit()
        raise PermissionError(f"Rights verification failed: {'; '.join(rights_info['reasons'])}. {rights_info.get('warning', '')}")

    # Determine storage path
    res_dir = settings.BASE_DIR / "uploads" / "resources"
    res_dir.mkdir(parents=True, exist_ok=True)
    clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', title.lower()[:40]) + ".pdf"
    target_path = res_dir / f"{int(time.time())}_{clean_name}"

    # Step 2: Download & Validate Stream
    try:
        dl_res = download_and_validate_pdf_stream(source_url, target_path)
    except Exception as e:
        audit = DownloadAuditLog(
            user_id=user_id,
            source_url=source_url,
            final_url=source_url,
            rights_status=rights_info["access_type"],
            status="failed_verification",
            failure_reason=str(e)
        )
        db.add(audit)
        db.commit()
        raise

    sha256 = dl_res["sha256_checksum"]

    # Step 3: SHA-256 Duplicate Check against stored_documents
    existing_doc = db.query(StoredDocument).filter(StoredDocument.sha256_checksum == sha256).first()
    if existing_doc:
        # Clean up newly downloaded redundant file
        if target_path.exists():
            try:
                target_path.unlink()
            except Exception:
                pass

        # Create new ResourceRecord referencing existing document chunks
        rec = ResourceRecord(
            syllabus_id=syllabus_id,
            book_id=book_id,
            stored_document_id=existing_doc.id,
            resource_type="Open Educational Resource",
            title=title,
            authors=authors,
            publisher=publisher,
            edition=edition,
            year=year,
            isbn=isbn,
            doi=doi,
            source_repository=source_repository or rights_info["source_repository"],
            source_url=source_url,
            landing_page_url=source_url,
            access_type=rights_info["access_type"],
            licence=licence or rights_info["licence"],
            rights_statement=rights_statement or "Reused from verified institutional document storage.",
            rights_verified=True,
            rights_verified_by_id=user_id,
            rights_verified_at=datetime.datetime.now(datetime.UTC) if hasattr(datetime, "UTC") else datetime.datetime.utcnow(),
            faculty_owner_id=user_id,
            status="indexed"
        )
        db.add(rec)
        db.flush()

        audit = DownloadAuditLog(
            stored_document_id=existing_doc.id,
            user_id=user_id,
            source_url=source_url,
            final_url=source_url,
            http_status_code=200,
            sha256_checksum=sha256,
            file_size_bytes=existing_doc.file_size,
            rights_status=rights_info["access_type"],
            status="duplicate_skipped",
            failure_reason="Duplicate SHA-256 found. Reused existing indexed chunks."
        )
        db.add(audit)
        db.commit()
        db.refresh(rec)
        return rec

    # Step 4: Create ResourceRecord and StoredDocument
    rec = ResourceRecord(
        syllabus_id=syllabus_id,
        book_id=book_id,
        resource_type="Open Educational Resource",
        title=title,
        authors=authors,
        publisher=publisher,
        edition=edition,
        year=year,
        isbn=isbn,
        doi=doi,
        source_repository=source_repository or rights_info["source_repository"],
        source_url=source_url,
        landing_page_url=source_url,
        access_type=rights_info["access_type"],
        licence=licence or rights_info["licence"],
        rights_statement=rights_statement or f"Verified via {rights_info['source_repository']}.",
        rights_verified=True,
        rights_verified_by_id=user_id,
        rights_verified_at=datetime.datetime.now(datetime.UTC) if hasattr(datetime, "UTC") else datetime.datetime.utcnow(),
        faculty_owner_id=user_id,
        status="extracting"
    )
    db.add(rec)
    db.flush()

    stored_doc = StoredDocument(
        resource_record_id=rec.id,
        original_filename=dl_res["original_filename"],
        storage_path=dl_res["file_path"],
        mime_type=dl_res["mime_type"],
        file_size=dl_res["file_size"],
        sha256_checksum=sha256,
        acquisition_method="lawful_download",
        extraction_status="completed",
        ocr_required=False,
        version=1,
        active=True
    )
    db.add(stored_doc)
    db.flush()
    rec.stored_document_id = stored_doc.id

    # Step 5: Content Extraction & Chunking
    chunks = extract_and_chunk_pdf(dl_res["file_path"])
    stored_doc.page_count = max(c["page_number"] for c in chunks) if chunks else 1

    # Step 6: Syllabus Alignment
    syllabus_units = []
    if syllabus_id:
        from app.services.co_extractor import extract_syllabus_units
        syl = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
        if syl:
            syl_text = getattr(syl, "extracted_text", None) or getattr(syl, "raw_text", "")
            if syl_text:
                syllabus_units = extract_syllabus_units(syl_text)

    aligned_chunks = align_chunks_with_syllabus(chunks, syllabus_units)

    for ac in aligned_chunks:
        chunk_model = DocumentChunkModel(
            stored_document_id=stored_doc.id,
            page_number=ac["page_number"],
            chapter=ac.get("chapter"),
            heading=ac.get("heading"),
            text=ac["text"],
            token_count=ac["token_count"],
            unit_number=ac.get("unit_number"),
            topic=ac.get("topic"),
            co_level=ac.get("co_level"),
            alignment_score=ac.get("alignment_score", 0.0),
            approved_for_generation=False # Must be approved by faculty
        )
        db.add(chunk_model)

    rec.status = "faculty_review_pending"

    # Step 7: Audit & Verification Logs
    v_log = RightsVerificationLog(
        resource_record_id=rec.id,
        user_id=user_id,
        action="verify_passed" if not faculty_override else "faculty_override",
        rights_status=rights_info["access_type"],
        licence_found=rights_info.get("licence"),
        evidence_notes="; ".join(rights_info["reasons"]),
        faculty_override_justification=override_justification
    )
    db.add(v_log)

    audit = DownloadAuditLog(
        stored_document_id=stored_doc.id,
        user_id=user_id,
        source_url=source_url,
        final_url=source_url,
        http_status_code=200,
        sha256_checksum=sha256,
        file_size_bytes=dl_res["file_size"],
        rights_status=rights_info["access_type"],
        status="success"
    )
    db.add(audit)

    db.commit()
    db.refresh(rec)
    return rec
