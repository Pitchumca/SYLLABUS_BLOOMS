import os
import io
import json
import pytest
import fitz
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, Base, engine
from app.models.user import User
from app.models.syllabus import Syllabus
from app.models.template_and_resource import (
    ResourceRecord,
    StoredDocument,
    DocumentChunkModel,
    QuestionPaperTemplate,
    ExtractedBlueprint
)
from app.services.lawful_acquisition_service import (
    classify_and_verify_rights,
    verify_magic_pdf_bytes,
    extract_and_chunk_pdf,
    align_chunks_with_syllabus,
    acquire_and_index_lawful_pdf
)
from app.services.question_generator import (
    validate_type_bloom_compatibility,
    normalize_question_types,
    synthesize_combined_type_question,
    synthesize_grounded_question,
    generate_questions_from_blueprint
)
from app.services.template_extractor import validate_extracted_blueprint
from app.services.pdf_template_service import generate_question_paper_pdf

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="module")
def sample_faculty_user(db_session):
    user = db_session.query(User).filter(User.email == "faculty_tester@avit.ac.in").first()
    if not user:
        user = User(
            email="faculty_tester@avit.ac.in",
            password_hash="dummy_hash_for_tests",
            role="faculty",
            full_name="Dr. Tester, Ph.D.",
            department="Computer Science & Engineering",
            designation="Professor",
            employee_id="FAC-TEST-001",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user

@pytest.fixture(scope="module")
def sample_syllabus(db_session, sample_faculty_user):
    syl = db_session.query(Syllabus).filter(Syllabus.original_filename == "syllabus_r_test.pdf").first()
    if not syl:
        syl = Syllabus(
            original_filename="syllabus_r_test.pdf",
            stored_filename="syllabus_r_test.pdf",
            file_size_bytes=1024,
            extracted_text="""
            Aarupadai Veedu Institute of Technology
            Department of Computer Science and Engineering
            Course Code: TEST35021
            Course Title: Advanced R Programming
            Semester: V
            Unit 1: Introduction to Vectors and Matrices, Recycling rules, S3 classes
            Unit 2: Data Manipulation, Lists and Arrays, String processing
            Unit 3: Functional Programming, Sapply and Lapply, Plotting and Graphics
            Unit 4: Linear and Generalized Linear Models, Hypothesis Testing, OLS Regression
            Unit 5: Clustering, K-Means, Interfacing and Production Workflows
            """,
            faculty_id=sample_faculty_user.id
        )
        db_session.add(syl)
        db_session.commit()
        db_session.refresh(syl)
    return syl


# =============================================================================
# MODULE A: LAWFUL ONLINE PDF ACQUISITION & RIGHTS VERIFICATION TESTS
# =============================================================================

def test_lawful_whitelist_classification():
    """Verify approved open access repositories pass and blocked sites are rejected."""
    # 1. OpenStax repository check
    os_res = classify_and_verify_rights("https://openstax.org/books/introductory-statistics/pages/1-introduction")
    assert os_res["is_eligible"] is True
    assert os_res["can_download_and_index"] is True
    assert "Open-access" in os_res["access_type"]

    # 2. DOAB repository check
    doab_res = classify_and_verify_rights("https://directory.doabooks.org/handle/20.500.12854/12345")
    assert doab_res["is_eligible"] is True
    assert doab_res["can_download_and_index"] is True

    # 3. Institutional domain check (.edu / .ac.in)
    mit_res = classify_and_verify_rights("https://ocw.mit.edu/courses/6-0001-introduction-to-cs/lecture.pdf")
    assert mit_res["is_eligible"] is True
    assert "Institutionally licensed" in mit_res["access_type"]

    # 4. Shadow Library Blocklist check
    scihub_res = classify_and_verify_rights("https://sci-hub.se/10.1000/182")
    assert scihub_res["is_eligible"] is False
    assert scihub_res["can_download_and_index"] is False
    assert "Restricted access" in scihub_res["access_type"]

    libgen_res = classify_and_verify_rights("https://libgen.is/book/index.php?id=999")
    assert libgen_res["is_eligible"] is False
    assert libgen_res["can_download_and_index"] is False

    # 5. Commercial paywalled platform check
    sd_res = classify_and_verify_rights("https://www.sciencedirect.com/science/article/pii/S002200000000000")
    assert sd_res["is_eligible"] is False
    assert "commercial paywalled" in sd_res["reasons"][0].lower()


def test_magic_bytes_and_chunking(tmp_path):
    """Verify %PDF- magic byte validator and PyMuPDF text chunking."""
    # Valid PDF bytes
    valid_header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    assert verify_magic_pdf_bytes(valid_header) is True

    # Invalid non-PDF bytes (e.g. HTML or random bytes)
    invalid_header = b"<!DOCTYPE html><html><head><title>Error</title></head><body>"
    assert verify_magic_pdf_bytes(invalid_header) is False

    # Create dummy PDF for PyMuPDF chunking test
    import fitz
    pdf_path = tmp_path / "sample_oer.pdf"
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((50, 72), "Unit 1: Introduction to Vectors and R Recycling Rules.\n" * 20)
    page2 = doc.new_page()
    page2.insert_text((50, 72), "Unit 4: Generalized Linear Models and Logistic Regression in R.\n" * 25)
    doc.save(str(pdf_path))
    doc.close()

    chunks = extract_and_chunk_pdf(str(pdf_path), max_chunk_words=100, overlap_words=20)
    assert len(chunks) >= 2
    assert chunks[0]["page_number"] == 1
    assert "Vectors" in chunks[0]["text"]

    # Syllabus alignment
    units = [
        {"number": 1, "title": "Vectors and Recycling", "topics": "Vectors, Recycling rule, Mode"},
        {"number": 4, "title": "Generalized Linear Models", "topics": "GLM, Logistic regression"}
    ]
    aligned = align_chunks_with_syllabus(chunks, units)
    assert aligned[0]["unit_number"] in [1, 4]
    assert aligned[0]["approved_for_generation"] is False # strictly unapproved until faculty review


def test_lawful_acquire_service_and_duplicate_prevention(db_session, sample_syllabus, sample_faculty_user, tmp_path, monkeypatch):
    """Test full acquisition workflow and verify SHA-256 duplicate reuse."""
    import fitz
    test_pdf_path = tmp_path / "test_openstax.pdf"
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((50, 72), "OpenStax Chapter 1: Introduction to Statistics and R Programming.\nVectors and Matrices.")
    doc.save(str(test_pdf_path))
    doc.close()

    pdf_bytes = test_pdf_path.read_bytes()

    # Mock download_and_validate_pdf_stream to avoid actual internet request
    def mock_download(url, target_path, max_size=None):
        target_path.write_bytes(pdf_bytes)
        import hashlib
        return {
            "file_path": str(target_path),
            "file_size": len(pdf_bytes),
            "sha256_checksum": hashlib.sha256(pdf_bytes).hexdigest(),
            "mime_type": "application/pdf",
            "original_filename": "openstax_stats.pdf"
        }

    monkeypatch.setattr("app.services.lawful_acquisition_service.download_and_validate_pdf_stream", mock_download)

    # 1. First Acquisition
    rec1 = acquire_and_index_lawful_pdf(
        db=db_session,
        source_url="https://openstax.org/details/books/intro-stats",
        title="Introductory Statistics (OpenStax)",
        syllabus_id=sample_syllabus.id,
        source_repository="OpenStax",
        user_id=sample_faculty_user.id
    )
    assert rec1.id is not None
    assert rec1.stored_document is not None
    assert len(rec1.stored_document.chunks) > 0

    # 2. Second Acquisition with same file (SHA-256 Duplicate Check)
    rec2 = acquire_and_index_lawful_pdf(
        db=db_session,
        source_url="https://openstax.org/details/books/intro-stats-mirror",
        title="Introductory Statistics Mirror",
        syllabus_id=sample_syllabus.id,
        source_repository="OpenStax",
        user_id=sample_faculty_user.id
    )
    assert rec2.id != rec1.id
    # Should point to the SAME stored_document ID (duplicate skipped)
    assert rec2.stored_document.id == rec1.stored_document.id


# =============================================================================
# MODULE B & C: BLUEPRINT EXTRACTION VALIDATION (B6) & TEMPLATE SLOTS
# =============================================================================

def test_blueprint_validation_engine_b6():
    """Test Section B6 validation: calculates total marks and validates internal choice."""
    valid_blueprint = {
        "institution": "AVIT",
        "maximum_marks": 50,
        "sections": [
            {
                "section_name": "Part A",
                "question_count": 5,
                "marks_per_question": 2,
                "section_total": 10,
                "or_choice": False,
                "questions": [
                    {"question_number": "1", "marks": 2, "bloom_level": "L1", "co": "CO1", "question_types": ["mcq"]},
                    {"question_number": "2", "marks": 2, "bloom_level": "L1", "co": "CO1", "question_types": ["mcq"]},
                    {"question_number": "3", "marks": 2, "bloom_level": "L2", "co": "CO2", "question_types": ["short_answer"]},
                    {"question_number": "4", "marks": 2, "bloom_level": "L2", "co": "CO2", "question_types": ["short_answer"]},
                    {"question_number": "5", "marks": 2, "bloom_level": "L2", "co": "CO3", "question_types": ["short_answer"]}
                ]
            },
            {
                "section_name": "Part B",
                "question_count": 2,
                "marks_per_question": 20,
                "section_total": 40,
                "or_choice": True,
                "questions": [
                    {"question_number": "6(a)", "marks": 20, "bloom_level": "L3", "co": "CO4", "or_pair_with": "6(b)", "question_types": ["programming"]},
                    {"question_number": "6(b)", "marks": 20, "bloom_level": "L3", "co": "CO4", "or_pair_with": "6(a)", "question_types": ["programming"]},
                    {"question_number": "7(a)", "marks": 20, "bloom_level": "L4", "co": "CO5", "or_pair_with": "7(b)", "question_types": ["programming"]},
                    {"question_number": "7(b)", "marks": 20, "bloom_level": "L4", "co": "CO5", "or_pair_with": "7(a)", "question_types": ["programming"]}
                ]
            }
        ]
    }

    val = validate_extracted_blueprint(valid_blueprint)
    assert val["is_valid"] is True
    assert val["reconciled"] is True
    assert val["calculated_total_marks"] == 50
    assert len(val["errors"]) == 0

    # Invalidate total marks
    invalid_bp = dict(valid_blueprint)
    invalid_bp["maximum_marks"] = 100 # Mismatch
    val_bad = validate_extracted_blueprint(invalid_bp)
    assert val_bad["is_valid"] is False
    assert any("reconcile" in e.lower() or "mismatch" in e.lower() for e in val_bad["errors"])


def test_template_controlled_slot_generation(sample_syllabus):
    """Test that generator strictly follows extracted template slots and question numbers."""
    extracted_blueprint = {
        "sections": [
            {
                "name": "Section I",
                "questions_count": 2,
                "marks_per_question": 2,
                "has_internal_choice": False,
                "questions": [
                    {"question_number": "Q1", "marks": 2, "bloom_level": "L1 - Remember", "co_level": "CO1", "question_types": ["mcq"]},
                    {"question_number": "Q2", "marks": 2, "bloom_level": "L2 - Understand", "co_level": "CO2", "question_types": ["short_answer"]}
                ]
            },
            {
                "name": "Section II",
                "questions_count": 1,
                "marks_per_question": 13,
                "has_internal_choice": True,
                "questions": [
                    {"question_number": "Q3(a)", "marks": 13, "bloom_level": "L3 - Apply", "co_level": "CO3", "or_pair_with": "Q3(b)", "question_types": ["programming"]},
                    {"question_number": "Q3(b)", "marks": 13, "bloom_level": "L3 - Apply", "co_level": "CO3", "or_pair_with": "Q3(a)", "question_types": ["programming"]}
                ]
            }
        ]
    }

    units = [
        {"number": 1, "title": "Introduction to R", "topics": "Vectors, Matrices"},
        {"number": 2, "title": "Data Structures", "topics": "Lists, Data Frames"},
        {"number": 3, "title": "Functions", "topics": "Custom functions, Sapply"}
    ]

    out_q = generate_questions_from_blueprint(
        blueprint=extracted_blueprint,
        syllabus_text=sample_syllabus.extracted_text,
        course_outcomes=[{"code": "CO1"}, {"code": "CO2"}, {"code": "CO3"}],
        units=units
    )

    assert len(out_q) == 4
    assert out_q[0]["question_number"] == "Q1"
    assert out_q[1]["question_number"] == "Q2"
    assert out_q[2]["question_number"] == "Q3(a)"
    assert out_q[3]["question_number"] == "Q3(b)"
    assert out_q[2]["or_pair_id"] == out_q[3]["or_pair_id"]
    assert out_q[2]["or_equivalence_score"] >= 80.0


# =============================================================================
# MODULE D: MULTI-SELECT QUESTION TYPES & COMBINATION SYNTHESIS
# =============================================================================

def test_bloom_compatibility_matrix():
    """Verify Bloom compatibility validation warns on pedagogically misaligned combinations."""
    # 1. Compatible: MCQ at L1
    is_comp, warns = validate_type_bloom_compatibility(["mcq"], "L1 - Remember")
    assert is_comp is True
    assert len(warns) == 0

    # 2. Incompatible: Assertion-Reason at L1
    is_comp, warns = validate_type_bloom_compatibility(["assertion_reason"], "L1 - Remember")
    assert is_comp is False
    assert len(warns) == 1
    assert "Assertion Reason" in warns[0]

    # 3. Compatible: Programming at L3
    is_comp, warns = validate_type_bloom_compatibility(["programming"], "L3 - Apply")
    assert is_comp is True

    # 4. Incompatible: Case Study at L2
    is_comp, warns = validate_type_bloom_compatibility(["case_study"], "L2 - Understand")
    assert is_comp is False


def test_combined_question_synthesis():
    """Verify that combined types synthesize unified prompts, proportional mark split, and separate rubrics."""
    unit = {"number": "1", "title": "Vectors and Recycling in R", "topics": "Recycling Rule, S3 Classes"}

    # Combination: Programming + Descriptive (15 Marks)
    q = synthesize_grounded_question(
        unit=unit,
        topic="Vectors and Recycling in R",
        bloom_level="L4 - Analyze",
        marks=15,
        co_level="CO1",
        question_type=["programming", "descriptive"]
    )

    assert "Part I (Programming" in q["question_text"]
    assert "Part II (Descriptive" in q["question_text"]
    assert "### Part I:" in q["model_answer"]
    assert "### Part II:" in q["model_answer"]
    assert "Part I (" in q["marking_scheme"]
    assert "Part II (" in q["marking_scheme"]

    # Check rubric separation
    rubric = json.loads(q["rubric_json"])
    assert len(rubric["criteria"]) == 2
    marks_sum = sum(c["marks"] for c in rubric["criteria"])
    assert marks_sum == 15

    # Combination: Output Prediction + Debugging (5 Marks)
    q_dbg = synthesize_grounded_question(
        unit=unit,
        topic="Vectors and Functions",
        bloom_level="L3 - Apply",
        marks=5,
        co_level="CO1",
        question_type="code_snippet_analysis + debugging"
    )
    assert "Part I (Output Prediction" in q_dbg["question_text"]
    assert "Part II (Code Debugging" in q_dbg["question_text"]
    assert q_dbg["marks"] == 5


# =============================================================================
# EXPORT SEPARATION: STUDENT FACING VS FACULTY WITH SOLUTIONS
# =============================================================================

def test_export_separation_student_vs_faculty(sample_syllabus):
    """Verify student-facing exports strictly omit solutions, keys, and rubrics."""
    paper_dict = {
        "id": 999,
        "institution_name": "Aarupadai Veedu Institute of Technology",
        "course_name": "Advanced R Programming",
        "course_code": "TEST35021",
        "programme": "B.E. Computer Science and Engineering",
        "regulation": "2021",
        "academic_year": "2024-2025",
        "semester": "V",
        "department": "Computer Science & Engineering",
        "exam_name": "Semester Examination",
        "duration": "3 Hours",
        "max_marks": 50,
        "instructions": "Answer all questions.",
        "questions": [
            {
                "id": 1,
                "section_name": "Part A",
                "question_number": "1",
                "question_text": "What is the recycling rule in R vector arithmetic?",
                "marks": 2,
                "co_level": "CO1",
                "bloom_level": "L2 - Understand",
                "question_type": "short_answer",
                "model_answer": "TOP SECRET MODEL ANSWER: In R shorter vectors are recycled.",
                "marking_scheme": "2 Marks for full answer",
                "status": "approved"
            },
            {
                "id": 2,
                "section_name": "Part B",
                "question_number": "2(a)",
                "question_text": "Part I: Write an R function. Part II: Explain trade-offs.",
                "marks": 13,
                "co_level": "CO2",
                "bloom_level": "L3 - Apply",
                "question_type": "programming + descriptive",
                "model_answer": "TOP SECRET FACULTY SOLUTION CODE AND ALGORITHM",
                "marking_scheme": "Part I: 8M, Part II: 5M",
                "status": "approved"
            }
        ]
    }

    # 1. Student Export ("question_paper")
    pdf_student = generate_question_paper_pdf(paper_dict, export_type="question_paper")
    assert Path(pdf_student).exists()
    assert Path(pdf_student).stat().st_size > 1000

    # Read back with fitz to inspect text content
    doc_student = fitz.open(str(pdf_student))
    student_text = "".join(page.get_text() for page in doc_student)
    doc_student.close()

    # MUST contain questions
    assert "What is the recycling rule in R vector arithmetic?" in student_text
    # MUST NOT contain solutions or confidential answer keys!
    assert "TOP SECRET MODEL ANSWER" not in student_text
    assert "TOP SECRET FACULTY SOLUTION" not in student_text

    # 2. Faculty Answer Key Export ("with_answer_key")
    pdf_faculty = generate_question_paper_pdf(paper_dict, export_type="with_answer_key")
    assert Path(pdf_faculty).exists()
    doc_faculty = fitz.open(str(pdf_faculty))
    faculty_text = "".join(page.get_text() for page in doc_faculty)
    doc_faculty.close()

    # MUST contain model answers and solutions
    assert "TOP SECRET MODEL ANSWER" in faculty_text
    assert "TOP SECRET FACULTY SOLUTION" in faculty_text
