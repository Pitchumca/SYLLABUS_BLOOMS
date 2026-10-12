import os
import io
import json
import fitz # PyMuPDF
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.models.discovery_rag import (
    BookMetadata,
    BookAuthor,
    BookSource,
    BookFile,
    DownloadJobModel,
    ExtractionJob,
    RAGDocument,
    RAGChunk,
    CourseResource
)
from app.models.syllabus import Syllabus
from app.services.book_parser import detect_and_parse_books_structured
from app.services.bibliography_parser import (
    normalize_publisher,
    normalize_edition,
    normalize_isbns,
    parse_author_details,
    clean_citation_punctuation,
    format_isbn_display,
    calculate_metadata_confidence,
    CANONICAL_PUBLISHERS
)
from app.services.match_engine import (
    calculate_transparent_match_score,
    calculate_match_confidence,
    MATCH_EXACT,
    MATCH_PROBABLE,
    MATCH_DIFFERENT_EDITION,
    MATCH_RELATED,
    MATCH_METADATA_ONLY,
    MATCH_REJECTED
)
from app.services.verification_service import (
    verify_magic_bytes,
    pre_validate_candidate_url,
    OUTCOME_VERIFIED,
    OUTCOME_INVALID_FILE,
    OUTCOME_LINK_UNAVAILABLE,
    FRIENDLY_ERROR_MESSAGE
)
from app.services.search_service import (
    build_search_queries,
    consolidate_candidate_sources
)
from app.services.rag_indexer_service import (
    resolve_course_storage_dirs,
    generate_semantic_embedding,
    cosine_similarity,
    extract_toc_and_headings,
    process_book_file_for_rag,
    query_rag_chunks_for_topic,
    generate_syllabus_book_alignment_matrix,
    remove_book_from_rag_index
)
from app.services.word_template_service import generate_question_paper_docx


def create_dummy_pdf(num_pages: int = 3, text_per_page: str = "Sample Chapter Content") -> bytes:
    """Create a minimal valid binary PDF with PyMuPDF in memory."""
    doc = fitz.open()
    words = text_per_page.split()
    lines = [' '.join(words[j:j+12]) for j in range(0, len(words), 12)] if len(words) > 20 else [text_per_page]
    formatted_text = '\n'.join(lines)
    for idx in range(num_pages):
        page = doc.new_page(width=800, height=3000)
        page.insert_text((50, 50), f"Chapter {idx + 1}: Introduction to Data Structures and Algorithms\n{formatted_text}", fontsize=8)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# =============================================================================
# ACCEPTANCE CRITERION 1: Separate extraction of textbooks and reference books
# =============================================================================
def test_01_separate_extraction_textbooks_and_reference_books():
    syllabus_sample = """
    COURSE OBJECTIVES:
    To understand data structures and algorithms.

    TEXT BOOKS:
    1. Cormen, Thomas H., Charles E. Leiserson, Ronald L. Rivest, and Clifford Stein. Introduction to Algorithms. 3rd ed., MIT Press, 2009. ISBN: 978-0262033848.
    2. Weiss, Mark Allen. Data Structures and Algorithm Analysis in C++. 4th ed., Pearson, 2014.

    REFERENCE BOOKS:
    1. Sedgewick, Robert, and Kevin Wayne. Algorithms. 4th ed., Addison-Wesley Professional, 2011.
    2. Aho, Alfred V., John E. Hopcroft, and Jeffrey D. Ullman. Data Structures and Algorithms. Pearson, 1983.
    """
    structured = detect_and_parse_books_structured(syllabus_sample)
    assert len(structured) >= 4

    textbooks = [b for b in structured if b["resource_type"] == "TEXTBOOK"]
    ref_books = [b for b in structured if b["resource_type"] == "REFERENCE_BOOK"]

    assert len(textbooks) >= 2
    assert len(ref_books) >= 2

    tb_titles = [b["book_title"].lower() for b in textbooks]
    assert any("introduction to algorithms" in t for t in tb_titles)
    assert any("data structures and algorithm analysis" in t for t in tb_titles)

    ref_titles = [b["book_title"].lower() for b in ref_books]
    assert any("algorithms" in t for t in ref_titles)


# =============================================================================
# ACCEPTANCE CRITERION 2: Bibliographic field isolation without naive comma splits
# =============================================================================
def test_02_bibliographic_field_isolation():
    citation = "Silberschatz, Abraham, Peter B. Galvin, and Greg Gagne. Operating System Concepts: Essentials. 9th ed., Vol. 1, John Wiley & Sons, 2012. ISBN: 978-1118063330."
    parsed_structured = detect_and_parse_books_structured(f"TEXTBOOKS:\n1. {citation}")
    assert len(parsed_structured) >= 1
    book = parsed_structured[0]

    assert book["book_title"] == "Operating System Concepts"
    assert "Essentials" in (book.get("subtitle") or "")
    assert book["edition"] == "9th Edition"
    assert book["publisher"] == "John Wiley & Sons"
    assert str(book["publication_year"]) == "2012"
    assert book["isbn_13"] == "9781118063330"

    authors = book["authors"]
    assert len(authors) == 3
    assert authors[0]["family_name"] == "Silberschatz"
    assert authors[0]["given_name"] == "Abraham"
    assert authors[1]["display_name"] == "Peter B. Galvin"
    assert authors[2]["display_name"] == "Greg Gagne"


# =============================================================================
# ACCEPTANCE CRITERION 3: Canonical publisher normalization
# =============================================================================
def test_03_canonical_publisher_normalization():
    assert normalize_publisher("Morgan Kaufmann Publishers") == "Morgan Kaufmann"
    assert normalize_publisher("morgan kaufmann") == "Morgan Kaufmann"
    assert normalize_publisher("Pearson Education India") == "Pearson"
    assert normalize_publisher("Prentice Hall of India") == "Prentice Hall"
    assert normalize_publisher("PHI Learning") == "PHI Learning"
    assert normalize_publisher("Tata McGraw-Hill") == "McGraw-Hill"
    assert normalize_publisher("Addison-Wesley Professional") == "Addison-Wesley"
    assert normalize_publisher("John Wiley and Sons") == "John Wiley & Sons"


# =============================================================================
# ACCEPTANCE CRITERION 4: Standardized edition normalization
# =============================================================================
def test_04_standardized_edition_normalization():
    assert normalize_edition("2nd") == "2nd Edition"
    assert normalize_edition("2") == "2nd Edition"
    assert normalize_edition("Second Edition") == "2nd Edition"
    assert normalize_edition("3rd ed.") == "3rd Edition"
    assert normalize_edition("4th Edition") == "4th Edition"
    assert normalize_edition("1st") == "1st Edition"
    assert normalize_edition("revised edition") == "Revised Edition"
    assert normalize_edition(None) == "Not available"


# =============================================================================
# ACCEPTANCE CRITERION 5: Multi-source search query generation
# =============================================================================
def test_05_multi_source_search_and_query_generation():
    book = {
        "title": "Computer Networks: A Systems Approach",
        "authors": "Larry L. Peterson, Bruce S. Davie",
        "edition": "5th Edition",
        "publisher": "Morgan Kaufmann",
        "publication_year": "2011",
        "isbn": "978-0123850591"
    }
    queries = build_search_queries(book)
    q_types = [qt for qt, _ in queries]
    q_strings = [qs for _, qs in queries]

    assert "isbn" in q_types
    assert any("isbn:9780123850591" in qs for qs in q_strings)
    assert any("Computer Networks" in qs for qs in q_strings)


# =============================================================================
# ACCEPTANCE CRITERION 6: Transparent candidate match weights
# =============================================================================
def test_06_transparent_candidate_match_weights():
    query = {
        "title": "Operating System Concepts",
        "authors": "Abraham Silberschatz, Peter B. Galvin",
        "publisher": "John Wiley & Sons",
        "edition": "9th Edition",
        "publication_year": "2012",
        "isbn": "9781118063330"
    }
    exact_cand = {
        "title": "Operating System Concepts",
        "authors": "Silberschatz, Galvin",
        "publisher": "Wiley",
        "edition": "9th Edition",
        "publication_year": "2012",
        "isbn": "978-1118063330"
    }
    score, classification, summary, breakdown = calculate_transparent_match_score(query, exact_cand)
    assert score >= 95.0
    assert classification == MATCH_EXACT
    assert breakdown["isbn"] == 40.0
    assert breakdown["title"] == 25.0
    assert breakdown["author"] == 15.0

    # Different Edition candidate
    diff_ed_cand = {
        "title": "Operating System Concepts",
        "authors": "Silberschatz, Galvin",
        "publisher": "Wiley",
        "edition": "8th Edition",
        "publication_year": "2008"
    }
    score_ed, class_ed, _, breakdown_ed = calculate_transparent_match_score(query, diff_ed_cand)
    assert class_ed == MATCH_DIFFERENT_EDITION
    assert breakdown_ed["edition"] == 0.0


# =============================================================================
# ACCEPTANCE CRITERION 7: Candidate deduplication and canonical consolidation
# =============================================================================
def test_07_candidate_consolidation_and_canonical_id():
    book_data = {
        "title": "Database System Concepts",
        "authors": "Abraham Silberschatz, Henry F. Korth",
        "resource_type": "TEXTBOOK"
    }
    candidates = [
        {
            "source": "Google Books",
            "title": "Database System Concepts",
            "authors": "Abraham Silberschatz, Henry F. Korth",
            "publisher": "McGraw-Hill",
            "edition": "6th Edition",
            "publication_year": "2010",
            "isbn_13": "9780073523323",
            "access_status": "PREVIEW_ONLY"
        },
        {
            "source": "Internet Archive",
            "title": "Database System Concepts",
            "authors": "Silberschatz, Korth",
            "verified_download_url": "https://archive.org/download/dbconcepts/dbconcepts.pdf",
            "access_status": "PUBLIC_PDF_VERIFIED",
            "publication_year": "2010"
        }
    ]
    consolidated = consolidate_candidate_sources(book_data, candidates)

    assert consolidated["canonical_book_id"].startswith("book_")
    assert "Google Books" in consolidated["metadata_sources"]
    assert "Internet Archive" in consolidated["file_sources"]
    assert consolidated["best_download_source"] == "Internet Archive"
    assert consolidated["is_verified_downloadable"] is True
    assert consolidated["status"] == "available"


# =============================================================================
# ACCEPTANCE CRITERION 8: Server-side pre-validation verifies %PDF- signature
# =============================================================================
def test_08_server_side_prevalidation_magic_bytes():
    valid_pdf_header = b"%PDF-1.5 \n%Binary\x00\x01\x02\x03"
    is_valid, mime = verify_magic_bytes(valid_pdf_header)
    assert is_valid is True
    assert mime == "application/pdf"

    invalid_html_header = b"<!DOCTYPE html><html><head><title>404 Not Found</title></head>"
    is_valid_html, mime_html = verify_magic_bytes(invalid_html_header)
    assert is_valid_html is False


# =============================================================================
# ACCEPTANCE CRITERION 9: Trapping 404/401/403/500 without exposing raw error
# =============================================================================
@pytest.mark.asyncio
async def test_09_error_trapping_never_exposes_raw_error_pages():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.history = []

    res = await pre_validate_candidate_url("http://example.com/missing.pdf")
    # Even if offline, pre_validate_candidate_url handles exceptions and returns friendly error
    assert res["is_valid"] is False
    assert FRIENDLY_ERROR_MESSAGE in res["friendly_message"]
    assert res["user_can_download"] is False


# =============================================================================
# ACCEPTANCE CRITERION 10: Course folder storage layout
# =============================================================================
def test_10_course_folder_storage_layout():
    dirs = resolve_course_storage_dirs("CS8401", "Design and Analysis of Algorithms")
    assert dirs["base"].exists()
    assert dirs["textbooks"].exists()
    assert dirs["reference_books"].exists()
    assert dirs["rag_index"].exists()
    assert "CS8401_Design_and_Analysis_of_Algorithms" in dirs["folder_name"]


# =============================================================================
# ACCEPTANCE CRITERION 11 & 12: Book metadata, extraction status, and SHA-256 deduplication
# =============================================================================
def test_11_and_12_metadata_files_and_sha256_deduplication(db_session, tmp_path):
    pdf_bytes = create_dummy_pdf(3, "Detailed Unit on Graph Algorithms and Shortest Paths")
    pdf_file = tmp_path / "test_algorithms.pdf"
    pdf_file.write_bytes(pdf_bytes)

    book_meta = BookMetadata(
        book_title="Test Algorithms Book",
        publisher="Test Publishing",
        edition="1st Edition",
        publication_year="2022",
        resource_type="TEXTBOOK",
        metadata_confidence=95.0
    )
    db_session.add(book_meta)
    db_session.commit()

    # First run: process for RAG
    res1 = process_book_file_for_rag(
        file_path=pdf_file,
        book_metadata_id=book_meta.id,
        course_id=None,
        syllabus_id=None,
        db=db_session,
        course_code="CS301",
        course_name="Data_Structures",
        resource_type="TEXTBOOK"
    )
    assert res1["status"] == "success"
    assert res1["total_pages"] == 3
    assert res1["total_chunks"] >= 3

    # Verify metadata.json and extraction_status.json exist
    stored_path = Path(res1["storage_path"])
    book_folder = stored_path.parent
    assert (book_folder / "metadata.json").exists()
    assert (book_folder / "extraction_status.json").exists()

    with open(book_folder / "metadata.json", "r", encoding="utf-8") as mf:
        m_data = json.load(mf)
        assert m_data["book_title"] == "Test Algorithms Book"
        assert m_data["resource_type"] == "TEXTBOOK"

    with open(book_folder / "extraction_status.json", "r", encoding="utf-8") as sf:
        s_data = json.load(sf)
        assert s_data["status"] == "completed"
        assert s_data["total_pages"] == 3

    # Second run with same file (SHA-256 duplicate detection)
    res2 = process_book_file_for_rag(
        file_path=pdf_file,
        book_metadata_id=book_meta.id,
        course_id=None,
        syllabus_id=None,
        db=db_session,
        course_code="CS301",
        course_name="Data_Structures",
        resource_type="TEXTBOOK"
    )
    assert res2["status"] == "reused"
    assert res2["checksum"] == res1["checksum"]


# =============================================================================
# ACCEPTANCE CRITERION 13: Table of Contents & chapter headings extraction
# =============================================================================
def test_13_toc_and_chapter_headings_extraction():
    doc = fitz.open()
    doc.new_page().insert_text((50, 50), "Chapter 1: Foundational Data Structures\nArrays and Linked Lists")
    doc.new_page().insert_text((50, 50), "Chapter 2: Advanced Search Trees\nBinary Trees and AVL Trees")
    
    toc, page_headings = extract_toc_and_headings(doc)
    doc.close()

    assert len(toc) >= 1 or len(page_headings) >= 1
    # Check that chapter heading was recognized
    found_chapters = list(page_headings.values())
    assert any("chapter" in h.lower() for h in found_chapters)


# =============================================================================
# ACCEPTANCE CRITERION 14: Semantic chunks created (~600 words with ~80-word overlap)
# =============================================================================
def test_14_semantic_sliding_window_chunks(db_session, tmp_path):
    long_content = " ".join([f"term_{i} algorithm efficiency analysis" for i in range(750)])
    pdf_bytes = create_dummy_pdf(2, long_content)
    test_pdf = tmp_path / "long_textbook.pdf"
    test_pdf.write_bytes(pdf_bytes)

    book_meta = BookMetadata(
        book_title="Comprehensive Algorithms",
        resource_type="TEXTBOOK"
    )
    db_session.add(book_meta)
    db_session.commit()

    res = process_book_file_for_rag(
        file_path=test_pdf,
        book_metadata_id=book_meta.id,
        course_id=None,
        syllabus_id=None,
        db=db_session,
        course_code="CS101",
        course_name="CompSci",
        resource_type="TEXTBOOK"
    )
    assert res["status"] == "success"
    # Should have split the 750-word page into multiple overlapping chunks
    assert res["total_chunks"] >= 3


# =============================================================================
# ACCEPTANCE CRITERION 15: Vector embeddings generated and saved in local index
# =============================================================================
def test_15_semantic_vector_embeddings_and_rag_index():
    v1 = generate_semantic_embedding("Binary search trees and dynamic programming")
    v2 = generate_semantic_embedding("Binary search trees and AVL balanced algorithms")
    v3 = generate_semantic_embedding("Photosynthesis in cellular plant biology")

    assert len(v1) == 128
    assert len(v2) == 128

    sim_related = cosine_similarity(v1, v2)
    sim_unrelated = cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated
    assert sim_related >= 0.35


# =============================================================================
# ACCEPTANCE CRITERION 16: Syllabus alignment matrix generated
# =============================================================================
def test_16_syllabus_book_alignment_matrix(db_session):
    syl = Syllabus(
        original_filename="Data_Structures_Syllabus.pdf",
        stored_filename="Data_Structures_Syllabus.pdf",
        file_size_bytes=1024,
        extracted_text="""
        UNIT I: LINEAR DATA STRUCTURES
        Arrays, Stacks, Queues, Linked Lists.
        UNIT II: NON-LINEAR DATA STRUCTURES
        Trees, Binary Search Trees, Graphs, Breadth-First Search.
        """
    )
    db_session.add(syl)
    db_session.flush()

    matrix = generate_syllabus_book_alignment_matrix(syllabus_id=syl.id, db=db_session)
    assert len(matrix) >= 2
    # Verify mandatory matrix columns
    for row in matrix:
        assert "unit_number" in row
        assert "syllabus_topic" in row
        assert "textbook_title" in row
        assert "chapter" in row
        assert "pages" in row
        assert "relevance_score" in row
        assert "rag_status" in row


# =============================================================================
# ACCEPTANCE CRITERION 17: Grounded question evidence priority (Textbook > Reference > Slides)
# =============================================================================
def test_17_grounded_question_generation_evidence_priority(db_session):
    # Insert a Textbook chunk and a Reference Book chunk with identical text
    c_textbook = RAGChunk(
        book_title="Prescribed Core Textbook",
        resource_type="TEXTBOOK",
        chapter="Chapter 3: Stacks and Queues",
        page_start=45,
        page_end=48,
        text="A stack is a linear data structure following Last-In-First-Out (LIFO) order.",
        embedding_vector_json=json.dumps(generate_semantic_embedding("stacks linear LIFO")),
        approved_for_generation=True,
        topic_relevance_score=0.9
    )
    c_ref = RAGChunk(
        book_title="Supplementary Reference Book",
        resource_type="REFERENCE_BOOK",
        chapter="Chapter 8: Data Types",
        page_start=110,
        page_end=112,
        text="A stack is a linear data structure following Last-In-First-Out (LIFO) order.",
        embedding_vector_json=json.dumps(generate_semantic_embedding("stacks linear LIFO")),
        approved_for_generation=True,
        topic_relevance_score=0.9
    )
    db_session.add(c_textbook)
    db_session.add(c_ref)
    db_session.commit()

    retrieved = query_rag_chunks_for_topic("stack linear data structure LIFO", top_k=2, db=db_session)
    assert len(retrieved) >= 2
    # First chunk retrieved MUST be the Textbook chunk
    assert retrieved[0]["resource_type"] == "TEXTBOOK"
    assert retrieved[1]["resource_type"] == "REFERENCE_BOOK"


# =============================================================================
# ACCEPTANCE CRITERION 18: Word export source citation toggle
# =============================================================================
def test_18_word_export_provenance_citation_toggle(tmp_path):
    paper_data = {
        "institution_name": "AVIT College of Engineering",
        "department": "Computer Science",
        "course_name": "Data Structures",
        "course_code": "CS8401",
        "exam_name": "End Semester Exam",
        "duration": "3 Hours",
        "max_marks": "100"
    }
    questions = [
        {
            "section_name": "Part A",
            "question_number": "1",
            "question_text": "Define Stack and explain push and pop operations.",
            "marks": 2,
            "co_level": "CO1",
            "bloom_level": "L1 - Remember",
            "status": "approved",
            "source_filename": "Operating_System_Concepts.pdf",
            "source_page_or_slide": "Page 45"
        }
    ]

    # Export without citations (default for student exam paper)
    doc_student = generate_question_paper_docx(
        paper_data=paper_data,
        questions=questions,
        export_approved_only=True,
        include_citations=False
    )
    assert Path(doc_student).exists()
    import docx
    d_stu = docx.Document(doc_student)
    stu_full_text = " ".join([p.text for p in d_stu.paragraphs] + [c.text for t in d_stu.tables for r in t.rows for c in r.cells])
    assert "[Source:" not in stu_full_text

    # Export with citations enabled (for faculty review / answer key)
    doc_faculty = generate_question_paper_docx(
        paper_data=paper_data,
        questions=questions,
        export_approved_only=True,
        include_citations=True
    )
    assert Path(doc_faculty).exists()
    d_fac = docx.Document(doc_faculty)
    fac_full_text = " ".join([p.text for p in d_fac.paragraphs] + [c.text for t in d_fac.tables for r in t.rows for c in r.cells])
    assert "[Source:" in fac_full_text
    assert "Page 45" in fac_full_text
