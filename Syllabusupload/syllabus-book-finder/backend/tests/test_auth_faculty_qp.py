import uuid
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, Base, engine
from app.models.user import User
from app.models.syllabus import Syllabus
from app.services.co_extractor import extract_course_outcomes, extract_syllabus_units
from app.services.question_generator import generate_questions_from_blueprint
from app.services.word_template_service import generate_question_paper_docx, create_default_template_file

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield

def test_login_and_auth():
    # 1. Login with seeded admin
    res_admin = client.post("/api/auth/login", json={
        "email": "admin@college.edu",
        "password": "Admin@123"
    })
    assert res_admin.status_code == 200, res_admin.text
    data = res_admin.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"
    admin_token = data["access_token"]

    # 2. Check /api/auth/me with Bearer token
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "admin@college.edu"

    # 3. Login with seeded faculty
    res_fac = client.post("/api/auth/login", json={
        "email": "faculty@college.edu",
        "password": "Faculty@123"
    })
    assert res_fac.status_code == 200
    fac_data = res_fac.json()
    assert fac_data["user"]["role"] == "faculty"
    assert fac_data["user"]["department"] == "Computer Science & Engineering"

def test_faculty_management_admin_crud():
    # Login admin
    res_admin = client.post("/api/auth/login", json={
        "email": "admin@college.edu",
        "password": "Admin@123"
    })
    admin_token = res_admin.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. List faculty
    res_list = client.get("/api/faculty", headers=headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 3

    # 2. Get department stats
    res_stats = client.get("/api/faculty/stats", headers=headers)
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_faculty"] >= 3
    assert "Computer Science & Engineering" in stats["department_breakdown"]

    # 3. Add new faculty
    unique_email = f"dr.patil_{uuid.uuid4().hex[:6]}@college.edu"
    new_faculty_data = {
        "email": unique_email,
        "password": "SecretPassword123",
        "full_name": "Dr. Ramesh Patil",
        "role": "faculty",
        "department": "Mechanical Engineering",
        "designation": "Assistant Professor",
        "employee_id": "MECH-099",
        "phone": "+91 99999 88888",
        "is_active": True
    }
    res_create = client.post("/api/faculty", json=new_faculty_data, headers=headers)
    assert res_create.status_code == 201
    created_id = res_create.json()["id"]

    # 4. Filter by department
    res_mech = client.get("/api/faculty?department=Mechanical", headers=headers)
    assert res_mech.status_code == 200
    assert any(f["id"] == created_id for f in res_mech.json())

    # 5. Update faculty
    res_update = client.put(f"/api/faculty/{created_id}", json={
        "designation": "Associate Professor"
    }, headers=headers)
    assert res_update.status_code == 200
    assert res_update.json()["designation"] == "Associate Professor"

    # 6. Delete faculty
    res_del = client.delete(f"/api/faculty/{created_id}", headers=headers)
    assert res_del.status_code == 200

def test_course_outcomes_extraction():
    sample_syllabus_text = """
    COURSE OUTCOMES:
    CO1: Understand basic asymptotic notation and complexity of algorithms (L2)
    CO2: Apply divide and conquer methods to solve sorting problems (L3)
    CO3: Analyze graph traversal techniques including BFS and DFS (L4)
    CO4: Evaluate greedy versus dynamic programming strategies (L5)
    CO5: Design optimized balanced tree structures (L6)

    UNIT I: Introduction to Algorithms
    Asymptotic notations, Big O, Omega, Theta notation, recurrence relations.

    UNIT II: Divide and Conquer
    Merge sort, Quick sort, Binary search analysis.
    """
    outcomes = extract_course_outcomes(sample_syllabus_text)
    assert len(outcomes) >= 5
    codes = [o["code"] for o in outcomes]
    assert "CO1" in codes
    assert "CO2" in codes
    assert "CO3" in codes

def test_blueprint_question_generation_and_validation():
    # Login faculty
    res_fac = client.post("/api/auth/login", json={
        "email": "faculty@college.edu",
        "password": "Faculty@123"
    })
    fac_token = res_fac.json()["access_token"]
    headers = {"Authorization": f"Bearer {fac_token}"}

    # First upload sample syllabus
    res_syl = client.post("/api/upload/sample")
    assert res_syl.status_code == 201
    syllabus_id = res_syl.json()["id"]

    # Generate question paper with blueprint
    blueprint_payload = {
        "syllabus_id": syllabus_id,
        "institution_name": "Autonomous Institute of Technology",
        "course_name": "Data Structures & Algorithms",
        "course_code": "CS204",
        "exam_name": "Semester End Examination",
        "academic_year": "2025-2026",
        "semester": "IV Semester",
        "department": "Computer Science & Engineering",
        "duration": "3 Hours",
        "max_marks": 50,
        "instructions": "Answer all questions clearly.",
        "sections": [
            {
                "name": "Part A",
                "instructions": "Answer ALL questions. Each carries 2 marks.",
                "questions_count": 5,
                "marks_per_question": 2,
                "co_distribution": ["CO1", "CO2", "CO3", "CO4", "CO5"],
                "bloom_distribution": ["L1 - Remember", "L2 - Understand", "L2 - Understand", "L1 - Remember", "L2 - Understand"],
                "has_internal_choice": False
            },
            {
                "name": "Part B",
                "instructions": "Answer any TWO questions. Each carries 10 marks.",
                "questions_count": 2,
                "marks_per_question": 10,
                "co_distribution": ["CO2", "CO3"],
                "bloom_distribution": ["L3 - Apply", "L4 - Analyze"],
                "has_internal_choice": False
            }
        ]
    }

    res_gen = client.post("/api/question-paper/generate", json=blueprint_payload, headers=headers)
    assert res_gen.status_code == 201, res_gen.text
    paper = res_gen.json()
    assert paper["course_code"] == "CS204"
    assert len(paper["questions"]) == 7

    # Faculty validates question 1
    q1 = paper["questions"][0]
    res_val = client.put(
        f"/api/question-paper/{paper['id']}/question/{q1['id']}",
        json={
            "question_text": "Define Big-O notation and explain its significance in asymptotic analysis.",
            "marks": 2,
            "is_validated": True
        },
        headers=headers
    )
    assert res_val.status_code == 200
    assert res_val.json()["is_validated"] is True
    assert "Big-O notation" in res_val.json()["question_text"]

    # Bulk validate all questions
    res_val_all = client.post(f"/api/question-paper/{paper['id']}/validate-all", headers=headers)
    assert res_val_all.status_code == 200
    assert res_val_all.json()["status"] == "validated"

    # Download Word .docx
    res_docx = client.get(f"/api/question-paper/{paper['id']}/download-docx", headers=headers)
    assert res_docx.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in res_docx.headers["content-type"]
    assert len(res_docx.content) > 1000

def test_default_word_template_download():
    res = client.get("/api/question-paper/default-template/download")
    assert res.status_code == 200
    assert len(res.content) > 500
