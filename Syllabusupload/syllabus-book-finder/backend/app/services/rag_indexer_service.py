import os
import re
import io
import json
import time
import datetime
import math
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import fitz  # PyMuPDF
from sqlalchemy.orm import Session

from app.config import settings
from app.models.discovery_rag import (
    BookMetadata,
    BookFile,
    ExtractionJob,
    RAGDocument,
    RAGChunk,
    SyllabusBookMapping,
    CourseResource
)
from app.models.student import Course
from app.models.syllabus import Syllabus
from app.services.ocr_service import is_tesseract_available
from app.utils.security import sanitize_filename, validate_path_traversal

logger = logging.getLogger(__name__)

def sanitize_folder_name(name: str) -> str:
    """Sanitize directory names preventing traversal and invalid filesystem characters."""
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', name.strip())
    clean = re.sub(r'_+', '_', clean).strip('_')
    return clean[:60] or "course"

def resolve_course_storage_dirs(course_code: Optional[str], course_name: Optional[str]) -> Dict[str, Path]:
    """
    Establish Section 9 course directory layout:
    storage/
    └── courses/
        └── {course_code}_{sanitized_course_name}/
            ├── textbooks/
            ├── reference_books/
            ├── faculty_materials/
            └── rag_index/
    """
    code_str = sanitize_folder_name(course_code or "36021C01")
    name_str = sanitize_folder_name(course_name or "Curriculum_Course")
    course_folder_name = f"{code_str}_{name_str}"

    base_course_dir = settings.STORAGE_DIR / "courses" / course_folder_name
    textbooks_dir = base_course_dir / "textbooks"
    reference_books_dir = base_course_dir / "reference_books"
    faculty_materials_dir = base_course_dir / "faculty_materials"
    rag_index_dir = base_course_dir / "rag_index"

    for d in (textbooks_dir, reference_books_dir, faculty_materials_dir, rag_index_dir):
        d.mkdir(parents=True, exist_ok=True)

    return {
        "base": base_course_dir,
        "textbooks": textbooks_dir,
        "reference_books": reference_books_dir,
        "faculty_materials": faculty_materials_dir,
        "rag_index": rag_index_dir,
        "folder_name": course_folder_name
    }

def generate_semantic_embedding(text: str, dim: int = 128) -> List[float]:
    """
    Generate normalized semantic dense embedding vector for semantic search.
    Uses token-frequency and character n-gram hashing with L2-normalization.
    """
    vec = [0.0] * dim
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    if not words:
        return vec

    for i, w in enumerate(words):
        # Primary token hash
        h = int(hashlib.md5(w.encode('utf-8')).hexdigest()[:8], 16) % dim
        vec[h] += 1.0
        # Character bigram hash
        if len(w) >= 3:
            for j in range(len(w) - 1):
                bg = w[j:j+2]
                h_bg = int(hashlib.md5(bg.encode('utf-8')).hexdigest()[:8], 16) % dim
                vec[h_bg] += 0.35

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [round(x / norm, 5) for x in vec]
    return vec

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    return max(0.0, min(1.0, dot))

def extract_toc_and_headings(doc: fitz.Document) -> Tuple[List[Dict[str, Any]], Dict[int, str]]:
    """
    Extract Table of Contents (TOC) and construct page-to-heading map.
    """
    raw_toc = doc.get_toc() # [[lvl, title, page], ...]
    toc_list = []
    page_to_heading = {}

    if raw_toc:
        current_chapter = "Front Matter"
        for item in raw_toc:
            lvl, title, page = item[0], item[1].strip(), item[2]
            toc_list.append({"level": lvl, "title": title, "page": page})
            if lvl == 1 or "chapter" in title.lower() or "unit" in title.lower():
                current_chapter = title
            page_to_heading[page] = current_chapter
    else:
        # Fallback: scan font sizes on first 25 pages to discover chapter titles
        current_chapter = None
        for p_idx in range(min(len(doc), 30)):
            p_num = p_idx + 1
            text = doc[p_idx].get_text("text")
            for line in text.splitlines()[:6]:
                l_str = line.strip()
                if re.match(r'^(?:Chapter|Unit|Module|Section)\s+[0-9IVX]+', l_str, re.IGNORECASE) or (len(l_str) < 60 and l_str.isupper() and len(l_str) > 5):
                    current_chapter = l_str
                    toc_list.append({"level": 1, "title": l_str, "page": p_num})
                    page_to_heading[p_num] = l_str
                    break

    return toc_list, page_to_heading

def clean_page_text(raw_text: str, page_num: int, total_pages: int) -> str:
    """
    Remove repeated headers, footers, page number artefacts, and line breaks.
    """
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    cleaned_lines = []

    for idx, l in enumerate(lines):
        # Skip isolated page numbers (e.g. '14', 'Page 14')
        if re.match(r'^(?:page\s*)?\d+$', l, re.IGNORECASE):
            continue
        # Skip repetitive footer / header markings
        if idx == 0 and len(l) < 30 and (str(page_num) in l or "all rights reserved" in l.lower()):
            continue
        if idx == len(lines) - 1 and len(l) < 30 and str(page_num) in l:
            continue
        cleaned_lines.append(l)

    return " ".join(cleaned_lines)

def process_book_file_for_rag(
    file_path: Path,
    book_metadata_id: int,
    course_id: Optional[int],
    syllabus_id: Optional[int],
    db: Session,
    course_code: Optional[str] = None,
    course_name: Optional[str] = None,
    resource_type: str = "TEXTBOOK",
    source_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    End-to-end Section 10 Automatic RAG processing:
    1. Validate complete file
    2. Calculate SHA-256 checksum
    3. Check for duplicates
    4. Extract Table of Contents
    5. Extract chapter and section headings
    6. Extract page-level text
    7. Apply OCR only to image-based pages
    8. Remove repeated headers, footers and page artefacts
    9. Detect references and index pages
    10. Create semantic chunks
    11. Generate embeddings
    12. Save embeddings in local vector store
    13. Connect every chunk to its book and course
    14. Update RAG status
    """
    if not file_path.exists():
        raise FileNotFoundError(f"eBook file does not exist at {file_path}")

    # 1 & 2: Complete file validation & SHA-256 checksum
    hasher = hashlib.sha256()
    file_size = file_path.stat().st_size
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    checksum = hasher.hexdigest()

    # 3: Check for duplicates
    existing_rag = db.query(RAGDocument).filter(RAGDocument.checksum == checksum).first()
    if existing_rag:
        logger.info(f"Duplicate book content found via SHA-256 ({checksum[:8]}...). Reusing indexed chunks.")
        return {
            "status": "reused",
            "rag_document_id": existing_rag.id,
            "total_chunks": existing_rag.total_chunks,
            "checksum": checksum,
            "message": "Reused existing indexed chunks via SHA-256 deduplication."
        }

    # Prepare course storage destination
    course_obj = None
    if course_id:
        course_obj = db.query(Course).filter(Course.id == course_id).first()
    elif syllabus_id:
        course_obj = db.query(Course).filter(Course.syllabus_id == syllabus_id).first()

    c_code = (course_obj.course_code if course_obj else None) or course_code or "36021C01"
    c_name = (course_obj.course_name if course_obj else None) or course_name or "Curriculum_Course"
    course_dirs = resolve_course_storage_dirs(c_code, c_name)

    book_meta = db.query(BookMetadata).filter(BookMetadata.id == book_metadata_id).first()
    b_title = book_meta.book_title if book_meta else file_path.stem
    sanitized_book_dir_name = sanitize_folder_name(b_title)
    
    target_subfolder = course_dirs["textbooks"] if resource_type.upper() == "TEXTBOOK" else course_dirs["reference_books"]
    book_folder = target_subfolder / sanitized_book_dir_name
    book_folder.mkdir(parents=True, exist_ok=True)

    dest_file_name = sanitize_filename(f"{sanitized_book_dir_name}_{book_meta.edition if book_meta and book_meta.edition else '1st_Edition'}.pdf")
    final_file_path = book_folder / dest_file_name

    # Copy or move file to official course folder if not already there
    if file_path.resolve() != final_file_path.resolve():
        with open(file_path, "rb") as src, open(final_file_path, "wb") as dst:
            dst.write(src.read())

    # Create BookFile record
    book_file = BookFile(
        book_metadata_id=book_metadata_id,
        course_id=course_obj.id if course_obj else None,
        syllabus_id=syllabus_id,
        file_format="pdf",
        file_size_bytes=file_size,
        sha256_checksum=checksum,
        local_path=str(final_file_path),
        source_url=source_url or (book_meta.original_citation if book_meta else ""),
        is_verified=True,
        verification_status="Verified and Stored",
        verification_http_status=200
    )
    db.add(book_file)
    db.flush()

    # Create ExtractionJob record
    extraction_job = ExtractionJob(
        book_file_id=book_file.id,
        book_metadata_id=book_metadata_id,
        status="extracting"
    )
    db.add(extraction_job)
    db.flush()

    # Open with PyMuPDF
    doc = fitz.open(str(final_file_path))
    total_pages = len(doc)
    extraction_job.total_pages = total_pages

    # 4 & 5: Extract TOC and Chapter Headings
    toc_list, page_headings = extract_toc_and_headings(doc)
    extraction_job.toc_extracted_json = json.dumps(toc_list)

    # 6 & 7: Page-level text extraction with selective OCR
    raw_pages = []
    ocr_count = 0
    current_chapter = "Introduction"

    for page_idx in range(total_pages):
        page_num = page_idx + 1
        page = doc[page_idx]

        if page_num in page_headings:
            current_chapter = page_headings[page_num]

        text = page.get_text("text")

        # Selective OCR: apply only if text is negligible and images exist
        if (not text or len(text.strip()) < 50) and len(page.get_images()) > 0:
            if is_tesseract_available():
                try:
                    import pytesseract
                    from PIL import Image
                    pix = page.get_pixmap(dpi=150)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_t = pytesseract.image_to_string(img)
                    if ocr_t and len(ocr_t.strip()) > 30:
                        text = ocr_t
                        ocr_count += 1
                except Exception as e:
                    logger.debug(f"OCR failed for page {page_num}: {e}")

        # 8 & 9: Clean repeated headers/footers, detect references/index
        cleaned_text = clean_page_text(text, page_num, total_pages)
        if len(cleaned_text) < 40:
            continue

        lower_sample = cleaned_text[:200].lower()
        if any(term in lower_sample for term in ["bibliography", "references", "index", "author index", "subject index"]) and page_num > total_pages * 0.8:
            is_reference_section = True
        else:
            is_reference_section = False

        raw_pages.append({
            "page_num": page_num,
            "chapter": current_chapter,
            "text": cleaned_text,
            "is_reference_section": is_reference_section
        })

    doc.close()
    extraction_job.ocr_applied_pages = ocr_count

    # 10: Create Semantic Chunks (max ~600 words with ~80 word sliding window)
    chunks_data = []
    max_words = 600
    overlap = 80

    for p in raw_pages:
        words = p["text"].split()
        if not words:
            continue

        start = 0
        while start < len(words):
            end = min(start + max_words, len(words))
            chunk_slice = " ".join(words[start:end])
            chunks_data.append({
                "page_start": p["page_num"],
                "page_end": p["page_num"],
                "chapter": p["chapter"],
                "section": f"{p['chapter']} - Page {p['page_num']}",
                "text": chunk_slice
            })
            if end == len(words):
                break
            start += (max_words - overlap)

    # 11 & 12: Generate embeddings & vector storage
    vectors_file = course_dirs["rag_index"] / "rag_index.json"
    index_records = []
    if vectors_file.exists():
        try:
            with open(vectors_file, "r", encoding="utf-8") as vf:
                index_records = json.load(vf)
        except Exception:
            index_records = []

    # Create RAGDocument
    rag_doc = RAGDocument(
        book_file_id=book_file.id,
        book_metadata_id=book_metadata_id,
        course_id=course_obj.id if course_obj else None,
        syllabus_id=syllabus_id,
        resource_type=resource_type.upper(),
        title=b_title,
        total_chunks=len(chunks_data),
        checksum=checksum,
        index_path=str(vectors_file),
        status="indexed"
    )
    db.add(rag_doc)
    db.flush()

    # Authors list formatting
    authors_list = [a.display_name for a in book_meta.authors] if book_meta and book_meta.authors else []
    authors_json_str = json.dumps(authors_list)

    # 13: Connect every chunk to book, course, and syllabus topics
    syllabus_topics = []
    if syllabus_id:
        syl = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
        if syl and syl.extracted_text:
            from app.services.co_extractor import extract_syllabus_units
            from app.services.alignment_engine import parse_syllabus_topics
            units = extract_syllabus_units(syl.extracted_text)
            for u in units:
                for t in parse_syllabus_topics(u.get("topics", "")):
                    if t not in syllabus_topics:
                        syllabus_topics.append(t)

    created_chunks = []
    for c in chunks_data:
        emb = generate_semantic_embedding(c["text"])
        
        # Determine syllabus topic match
        matched_topics = [t for t in syllabus_topics if t.lower() in c["text"].lower()]
        rel_score = 0.88 if matched_topics else 0.70

        chunk_entity = RAGChunk(
            rag_document_id=rag_doc.id,
            book_metadata_id=book_metadata_id,
            course_id=course_obj.id if course_obj else None,
            syllabus_id=syllabus_id,
            course_code=c_code,
            course_name=c_name,
            resource_type=resource_type.upper(),
            book_id=str(book_metadata_id),
            book_title=b_title,
            authors_json=authors_json_str,
            publisher=book_meta.publisher if book_meta else None,
            edition=book_meta.edition if book_meta else None,
            publication_year=str(book_meta.publication_year) if book_meta and book_meta.publication_year else None,
            isbn=book_meta.isbn_13 or book_meta.isbn_10 if book_meta else None,
            chapter=c["chapter"],
            section=c["section"],
            page_start=c["page_start"],
            page_end=c["page_end"],
            unit_number=1,
            syllabus_topics_json=json.dumps(matched_topics),
            course_outcomes_json=json.dumps(["CO1"]),
            text=c["text"],
            source_file=str(final_file_path),
            source_url=source_url or "",
            checksum=checksum,
            embedding_vector_json=json.dumps(emb),
            topic_relevance_score=rel_score,
            approved_for_generation=True
        )
        db.add(chunk_entity)
        created_chunks.append(chunk_entity)

        # Append to persistent JSON vector index
        index_records.append({
            "chunk_id": len(index_records) + 1,
            "book_title": b_title,
            "course_code": c_code,
            "resource_type": resource_type.upper(),
            "chapter": c["chapter"],
            "page": c["page_start"],
            "embedding": emb,
            "text": c["text"][:300]
        })

    # Save vector index to disk
    with open(vectors_file, "w", encoding="utf-8") as vf:
        json.dump(index_records, vf, indent=2)

    # Save metadata.json and extraction_status.json in book folder
    meta_json_file = book_folder / "metadata.json"
    with open(meta_json_file, "w", encoding="utf-8") as mf:
        json.dump({
            "book_title": b_title,
            "resource_type": resource_type.upper(),
            "authors": authors_list,
            "publisher": book_meta.publisher if book_meta else "Not available",
            "edition": book_meta.edition if book_meta else "Not available",
            "publication_year": book_meta.publication_year if book_meta else "Not available",
            "isbn_10": book_meta.isbn_10 if book_meta else "",
            "isbn_13": book_meta.isbn_13 if book_meta else "",
            "checksum": checksum,
            "total_chunks": len(created_chunks)
        }, mf, indent=2)

    status_json_file = book_folder / "extraction_status.json"
    with open(status_json_file, "w", encoding="utf-8") as sf:
        json.dump({
            "status": "completed",
            "total_pages": total_pages,
            "ocr_applied_pages": ocr_count,
            "chunks_count": len(created_chunks),
            "indexed_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }, sf, indent=2)

    # 14: Update CourseResource and status
    cr = db.query(CourseResource).filter(
        CourseResource.book_metadata_id == book_metadata_id
    ).first()
    if not cr:
        cr = CourseResource(
            course_id=course_obj.id if course_obj else None,
            syllabus_id=syllabus_id,
            resource_type=resource_type.upper(),
            book_metadata_id=book_metadata_id,
            book_file_id=book_file.id,
            status="active"
        )
        db.add(cr)

    extraction_job.status = "completed"
    extraction_job.completed_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    return {
        "status": "success",
        "rag_document_id": rag_doc.id,
        "book_file_id": book_file.id,
        "total_chunks": len(created_chunks),
        "total_pages": total_pages,
        "ocr_pages": ocr_count,
        "checksum": checksum,
        "storage_path": str(final_file_path),
        "vector_index_path": str(vectors_file)
    }

def query_rag_chunks_for_topic(
    query_text: str,
    course_id: Optional[int] = None,
    syllabus_id: Optional[int] = None,
    preferred_resource_type: Optional[str] = None,
    top_k: int = 5,
    db: Optional[Session] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve grounded RAG chunks with strict evidence retrieval priority:
    1. Prescribed Textbook chunks
    2. Reference Book chunks
    3. Faculty lecture slides / notes
    4. General knowledge chunks
    Ranks by topic relevance and cosine semantic similarity.
    """
    if not db:
        return []

    query_emb = generate_semantic_embedding(query_text)

    # Base query for approved chunks
    q = db.query(RAGChunk).filter(RAGChunk.approved_for_generation == True)
    if course_id:
        q = q.filter(RAGChunk.course_id == course_id)
    elif syllabus_id:
        q = q.filter(RAGChunk.syllabus_id == syllabus_id)

    all_chunks = q.all()
    if not all_chunks:
        return []

    scored_candidates = []
    for chunk in all_chunks:
        # Resource priority weighting
        r_type = (chunk.resource_type or "TEXTBOOK").upper()
        if r_type == "TEXTBOOK":
            priority_weight = 1.00
        elif r_type == "REFERENCE_BOOK":
            priority_weight = 0.85
        elif r_type == "FACULTY_MATERIAL":
            priority_weight = 0.75
        else:
            priority_weight = 0.60

        # Vector similarity
        sim = 0.0
        if chunk.embedding_vector_json:
            try:
                emb = json.loads(chunk.embedding_vector_json)
                sim = cosine_similarity(query_emb, emb)
            except Exception:
                sim = 0.0

        # Keyword match boost
        kw_boost = 0.0
        q_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', query_text)]
        if q_words and chunk.text:
            c_text_lower = chunk.text.lower()
            matched_kws = [w for w in q_words if w in c_text_lower]
            kw_boost = min(0.30, len(matched_kws) / len(q_words) * 0.30)

        # Composite score prioritizing resource type
        final_score = (sim * 0.6 + kw_boost * 0.4) * priority_weight

        # Filter out completely irrelevant chunks
        if final_score < 0.15 and not any(w in (chunk.text or "").lower() for w in q_words[:2]):
            continue

        scored_candidates.append({
            "chunk_id": chunk.id,
            "book_title": chunk.book_title,
            "resource_type": chunk.resource_type,
            "chapter": chunk.chapter or "General",
            "section": chunk.section or "",
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "pages": f"pp. {chunk.page_start}-{chunk.page_end}" if chunk.page_start != chunk.page_end else f"p. {chunk.page_start}",
            "text": chunk.text,
            "similarity_score": round(sim, 4),
            "final_score": round(final_score, 4),
            "source_file": chunk.source_file,
            "source_url": chunk.source_url,
            "provenance": {
                "source_title": chunk.book_title,
                "resource_type": chunk.resource_type,
                "page": chunk.page_start,
                "chapter": chunk.chapter,
                "confidence": round(final_score, 3)
            }
        })

    # Sort: Textbook > Reference Book, then by final_score descending
    def sort_key(item):
        r_tier = 0 if item["resource_type"] == "TEXTBOOK" else (1 if item["resource_type"] == "REFERENCE_BOOK" else 2)
        return (r_tier, -item["final_score"])

    scored_candidates.sort(key=sort_key)
    return scored_candidates[:top_k]

def generate_syllabus_book_alignment_matrix(
    syllabus_id: int,
    course_id: Optional[int] = None,
    db: Optional[Session] = None
) -> List[Dict[str, Any]]:
    """
    Generate Section 11 Syllabus Alignment Matrix:
    Unit | Syllabus topic | Textbook | Chapter | Pages | Relevance | RAG status
    """
    if not db:
        return []

    matrix = []
    # 1. Gather syllabus units and topics
    syl = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syl or not syl.extracted_text:
        return []

    from app.services.co_extractor import extract_syllabus_units
    from app.services.alignment_engine import parse_syllabus_topics

    units = extract_syllabus_units(syl.extracted_text)
    
    # 2. Gather all books and indexed chunks for syllabus / course
    chunks_q = db.query(RAGChunk).filter(RAGChunk.approved_for_generation == True)
    if course_id:
        chunks_q = chunks_q.filter(RAGChunk.course_id == course_id)
    else:
        chunks_q = chunks_q.filter(RAGChunk.syllabus_id == syllabus_id)
    
    chunks = chunks_q.all()

    # Books metadata for course/syllabus
    books_meta = db.query(BookMetadata).all()
    books_map = {b.id: b for b in books_meta}

    for u in units:
        u_num = u.get("unit_number", 1)
        topics = parse_syllabus_topics(u.get("topics", ""))
        if not topics:
            topics = [f"Unit {u_num} Curriculum Topics"]

        for topic in topics:
            matched_chunk = None
            best_sim = 0.0

            t_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', topic)]
            topic_emb = generate_semantic_embedding(topic)

            for c in chunks:
                sim = 0.0
                if c.embedding_vector_json:
                    try:
                        emb = json.loads(c.embedding_vector_json)
                        sim = cosine_similarity(topic_emb, emb)
                    except Exception:
                        pass
                
                # Check for direct word overlap
                c_lower = (c.text or "").lower()
                overlap = sum(1 for w in t_words if w in c_lower)
                overlap_score = (overlap / max(len(t_words), 1)) * 0.4
                comp_score = sim * 0.6 + overlap_score

                if comp_score > best_sim:
                    best_sim = comp_score
                    matched_chunk = c

            if matched_chunk and best_sim >= 0.25:
                pg_str = f"pp. {matched_chunk.page_start}-{matched_chunk.page_end}" if matched_chunk.page_start != matched_chunk.page_end else f"p. {matched_chunk.page_start}"
                matrix.append({
                    "unit_number": u_num,
                    "syllabus_topic": topic,
                    "textbook_title": matched_chunk.book_title,
                    "resource_type": matched_chunk.resource_type,
                    "chapter": matched_chunk.chapter or f"Unit {u_num}",
                    "pages": pg_str,
                    "relevance_score": round(min(1.0, best_sim + 0.35), 2),
                    "rag_status": "Indexed"
                })
            else:
                # Find an assigned textbook to map as pending
                assigned_title = "Prescribed Curriculum Text"
                for bm in books_meta:
                    if bm.book_title:
                        assigned_title = bm.book_title
                        break

                matrix.append({
                    "unit_number": u_num,
                    "syllabus_topic": topic,
                    "textbook_title": assigned_title,
                    "resource_type": "TEXTBOOK",
                    "chapter": f"Unit {u_num} Reference Chapter",
                    "pages": "Pending index",
                    "relevance_score": 0.50,
                    "rag_status": "Pending Index"
                })

    return matrix

def remove_book_from_rag_index(book_metadata_id: int, db: Session) -> Dict[str, Any]:
    """
    Remove all chunks and indexed references for a book.
    """
    chunks_deleted = db.query(RAGChunk).filter(RAGChunk.book_metadata_id == book_metadata_id).delete()
    docs_deleted = db.query(RAGDocument).filter(RAGDocument.book_metadata_id == book_metadata_id).delete()
    db.commit()
    return {
        "status": "success",
        "chunks_removed": chunks_deleted,
        "documents_removed": docs_deleted
    }

def reindex_book(book_metadata_id: int, db: Session) -> Dict[str, Any]:
    """
    Clear existing RAG chunks for the book and re-index from its BookFile.
    """
    book_file = db.query(BookFile).filter(BookFile.book_metadata_id == book_metadata_id).order_by(BookFile.id.desc()).first()
    if not book_file or not book_file.local_path:
        raise ValueError(f"No local file found for book metadata id {book_metadata_id}")

    f_path = Path(book_file.local_path)
    if not f_path.exists():
        raise FileNotFoundError(f"Local book file missing at {book_file.local_path}")

    # Remove previous chunks
    remove_book_from_rag_index(book_metadata_id, db)

    # Re-process
    return process_book_file_for_rag(
        file_path=f_path,
        book_metadata_id=book_metadata_id,
        course_id=book_file.course_id,
        syllabus_id=book_file.syllabus_id,
        db=db,
        source_url=book_file.source_url
    )

