import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, Base, engine
from app.models.user import User
from app.models.syllabus import Syllabus
from app.models.content_file import ContentFile
from app.services.co_extractor import extract_syllabus_units, extract_course_outcomes
from app.services.alignment_engine import (
    parse_syllabus_topics,
    align_chunk_to_syllabus,
    build_coverage_matrix
)
from app.services.question_generator import generate_questions_from_blueprint
from app.services.word_template_service import generate_question_paper_docx

client = TestClient(app)

@pytest.fixture(scope="module")
def faculty_token():
    # Login as seeded faculty
    res = client.post("/api/auth/login", json={
        "email": "faculty@college.edu",
        "password": "Faculty@123"
    })
    assert res.status_code == 200, res.text
    return res.json()["access_token"]

def test_syllabus_topic_parsing():
    sample_text = """
    UNIT I - DATA STRUCTURES AND ARRAYS
    Introduction to Data Structures – Abstract Data Types (ADT) – Arrays and Dynamic Arrays – Memory Representation of Arrays
    UNIT II - LINKED LISTS AND APPLICATIONS
    Singly Linked List – Doubly Linked List – Circular Linked List – Applications of Linked Lists
    """
    units = extract_syllabus_units(sample_text)
    assert len(units) >= 2
    topics = []
    for u in units:
        unit_topics = parse_syllabus_topics(u["topics"])
        u_num = 2 if "II" in str(u["number"]) else 1
        for t in unit_topics:
            topics.append({"unit_number": u_num, "topic": t})
    assert len(topics) >= 6
    unit_nums = {t["unit_number"] for t in topics}
    assert 1 in unit_nums
    assert 2 in unit_nums
    topic_names = [t["topic"] for t in topics]
    assert any("linked list" in name.lower() for name in topic_names)

def test_alignment_scoring_thresholds():
    sample_units = [
        {"number": "1", "title": "Data Structures", "topics": "Introduction to Data Structures • Arrays and Dynamic Arrays • Memory Representation of Arrays"},
        {"number": "2", "title": "Linked Lists", "topics": "Singly Linked List • Doubly Linked List • Circular Linked List • Applications of Linked Lists"}
    ]
    sample_cos = [
        {"code": "CO1", "description": "Understand data structures and dynamic arrays", "bloom_level": "L2 - Understand"},
        {"code": "CO2", "description": "Apply linked lists", "bloom_level": "L3 - Apply"}
    ]

    # Strong chunk (>= 80%)
    chunk_strong = {
        "title": "Dynamic Arrays",
        "content": "In this slide we study dynamic arrays, array memory representation and basic data structures implementation with complexity.",
        "slide_or_page_number": 4
    }
    match_strong = align_chunk_to_syllabus(chunk_strong, sample_units, sample_cos, "unit1_arrays.pptx")
    assert match_strong["classification"] in ("Strong alignment", "Review recommended")
    assert match_strong["confidence_score"] >= 0.6

    # Completely unrelated chunk (< 60%)
    chunk_unrelated = {
        "title": "Plant Biology",
        "content": "Photosynthesis is the process used by plants to convert light energy into chemical energy.",
        "slide_or_page_number": 1
    }
    match_unrelated = align_chunk_to_syllabus(chunk_unrelated, sample_units, sample_cos, "biology_notes.pdf")
    assert match_unrelated["classification"] == "Unmatched"
    assert match_unrelated["confidence_score"] < 0.6

def test_grounded_question_generation_integrity():
    syllabus_text = """
    UNIT I: R BASICS
    Introducing to R – Vectors – Matrices – Lists – Data Frames – Reading Data
    UNIT II: CONTROL STRUCTURES
    Conditionals – Loops – Functions – Scoping Rules
    """

    chunks = [
        {
            "chunk_id": "c1",
            "slide_or_page_number": 3,
            "title": "Vectors and Matrices",
            "content": "Vectors are basic data structures in R created using c() function. Matrices are 2D arrays with dim() attribute.",
            "is_image_only": False,
            "source_filename": "Unit1_Slides.pptx"
        }
    ]

    blueprint = {
        "sections": [
            {
                "name": "Part A",
                "questions_count": 2,
                "marks_per_question": 2,
                "has_internal_choice": False,
                "co_distribution": ["CO1"],
                "instructions": "Answer all questions"
            },
            {
                "name": "Part B",
                "questions_count": 1,
                "marks_per_question": 10,
                "has_internal_choice": True,
                "co_distribution": ["CO1"],
                "instructions": "Answer either (a) or (b)"
            }
        ]
    }

    units = [
        {"number": "1", "title": "R Basics", "topics": "Introducing to R, Vectors, Matrices, Lists, Data Frames"},
        {"number": "2", "title": "Control Structures", "topics": "Conditionals, Loops, Functions"}
    ]

    cos = [
        {"code": "CO1", "description": "Understand R fundamentals", "bloom_level": "L2 - Understand"}
    ]

    questions = generate_questions_from_blueprint(
        blueprint=blueprint,
        syllabus_text=syllabus_text,
        course_outcomes=cos,
        units=units,
        aligned_chunks=chunks,
        generation_mode="syllabus_ppt"
    )

    # 2 in Part A + 2 for internal choice in Part B (1a and 1b) = 4 questions
    assert len(questions) == 4

    # Every question must start as 'draft'
    for q in questions:
        assert q["status"] == "draft"
        assert not q["is_validated"]
        assert q["marks"] in (2, 10)
        assert q["co_level"] == "CO1"
        assert q["model_answer"] is not None and len(q["model_answer"]) > 0
        assert q["marking_scheme"] is not None and len(q["marking_scheme"]) > 0
        assert q["rubric_json"] is not None

    # Check OR pair equivalence for Part B
    part_b_qs = [q for q in questions if q["section_name"] == "Part B"]
    assert len(part_b_qs) == 2
    q_a, q_b = part_b_qs[0], part_b_qs[1]
    assert q_a["or_pair_id"] == q_b["or_pair_id"]
    assert q_a["marks"] == q_b["marks"]
    assert q_a["unit_number"] == q_b["unit_number"]

def test_faculty_review_lifecycle_and_export(faculty_token):
    headers = {"Authorization": f"Bearer {faculty_token}"}

    # Upload sample syllabus first to ensure one exists with ID
    syl_res = client.post("/api/upload/sample")
    assert syl_res.status_code == 201
    s_id = syl_res.json()["id"]

    # 1. Course Metadata Endpoint
    meta_res = client.get(f"/api/question-paper/course-metadata?syllabus_id={s_id}", headers=headers)
    assert meta_res.status_code == 200
    meta_data = meta_res.json()
    assert "institution_name" in meta_data
    assert "course_code" in meta_data
    assert "programme" in meta_data

    # 2. Coverage Matrix Endpoint
    cov_res = client.post("/api/question-paper/coverage-matrix", json={
        "syllabus_id": s_id,
        "generation_mode": "syllabus_ppt"
    }, headers=headers)
    assert cov_res.status_code == 200
    cov_data = cov_res.json()
    assert "coverage_rows" in cov_data
    assert "warnings" in cov_data
    assert cov_data["is_ready_for_generation"] is True

    # 3. Generate a real test paper
    gen_res = client.post("/api/question-paper/generate", json={
        "syllabus_id": s_id,
        "institution_name": "AVIT University",
        "course_name": "Data Structures & Algorithms",
        "course_code": "CS204",
        "programme": "B.E. Computer Science",
        "semester": "IV Semester",
        "academic_year": "2024-2025",
        "department": "Computer Science & Engineering",
        "regulation": "2021",
        "duration": "3 Hours",
        "max_marks": 20,
        "instructions": "Answer all Part A questions.",
        "generation_mode": "syllabus_ppt",
        "sections": [
            {
                "name": "Part A",
                "questions_count": 2,
                "marks_per_question": 2,
                "has_internal_choice": False,
                "co_distribution": ["CO1", "CO2"],
                "bloom_distribution": ["L1 - Remember", "L2 - Understand"],
                "instructions": "Answer all questions"
            }
        ]
    }, headers=headers)
    assert gen_res.status_code == 201, gen_res.text
    paper = gen_res.json()
    paper_id = paper["id"]
    assert len(paper["questions"]) >= 2
    q1 = paper["questions"][0]
    q2 = paper["questions"][1]
    assert q1["status"] == "draft"

    # 4. Review: Approve Q1, Reject Q2
    rev_q1 = client.put(f"/api/question-paper/{paper_id}/question/{q1['id']}/review", json={
        "action": "approve",
        "reviewer_remarks": "Approved by faculty reviewer"
    }, headers=headers)
    assert rev_q1.status_code == 200
    assert rev_q1.json()["status"] == "approved"
    assert rev_q1.json()["is_validated"] is True

    rev_q2 = client.put(f"/api/question-paper/{paper_id}/question/{q2['id']}/review", json={
        "action": "reject",
        "reviewer_remarks": "Needs higher bloom level"
    }, headers=headers)
    assert rev_q2.status_code == 200
    assert rev_q2.json()["status"] == "rejected"
    assert rev_q2.json()["is_validated"] is False

    # 5. Provenance lookup
    prov_res = client.get(f"/api/question-paper/{paper_id}/question/{q1['id']}/source", headers=headers)
    assert prov_res.status_code == 200
    prov_data = prov_res.json()
    assert "source_filename" in prov_data
    assert "alignment_confidence" in prov_data

    # 6. Word Export - Question Paper Mode (only approved questions)
    doc_res = client.get(f"/api/question-paper/{paper_id}/download-docx?export_type=question_paper&export_approved_only=true", headers=headers)
    assert doc_res.status_code == 200
    assert doc_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert len(doc_res.content) > 1000

    # 7. Word Export - With Answer Key Mode
    ans_res = client.get(f"/api/question-paper/{paper_id}/download-docx?export_type=with_answer_key&export_approved_only=false", headers=headers)
    assert ans_res.status_code == 200
    assert len(ans_res.content) > 1000

    # 8. Word Export - Evaluation Scheme Mode
    eval_res = client.get(f"/api/question-paper/{paper_id}/download-docx?export_type=evaluation_scheme&export_approved_only=false", headers=headers)
    assert eval_res.status_code == 200
    assert len(eval_res.content) > 1000
