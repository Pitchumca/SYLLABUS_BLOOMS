import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_student_login():
    """Verify that student can authenticate and receive a valid JWT token."""
    res = client.post("/api/auth/login", json={
        "email": "student1@college.edu",
        "password": "Student@123"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "student"
    assert data["user"]["email"] == "student1@college.edu"

def test_student_profile_access():
    """Verify authenticated student can access their profile."""
    # 1. Login
    login_res = client.post("/api/auth/login", json={
        "email": "student1@college.edu",
        "password": "Student@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get profile
    res = client.get("/api/student/profile", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["register_number"] == "21CS001"
    assert data["programme"] == "B.E. Computer Science & Engineering"
    assert data["semester"] == "IV Semester"

def test_student_enrolled_courses():
    """Verify student receives only their enrolled courses."""
    login_res = client.post("/api/auth/login", json={
        "email": "student1@college.edu",
        "password": "Student@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/student/courses", headers=headers)
    assert res.status_code == 200
    courses = res.json()
    assert len(courses) >= 2
    codes = [c["course_code"] for c in courses]
    assert "21CS42" in codes

def test_student_course_learning_details():
    """Verify detailed course learning page returns syllabus units, topics, and outcomes."""
    login_res = client.post("/api/auth/login", json={
        "email": "student1@college.edu",
        "password": "Student@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    courses = client.get("/api/student/courses", headers=headers).json()
    target_course_id = courses[0]["id"]

    res = client.get(f"/api/student/courses/{target_course_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["course_code"] in ["21CS42", "CS204"]
    assert "units" in data
    assert len(data["units"]) > 0
    assert "overall_unit_completion" in data
    assert "materials" in data
    assert "course_outcomes" in data

def test_student_dashboard():
    """Verify complete student dashboard response with all cards."""
    login_res = client.post("/api/auth/login", json={
        "email": "student1@college.edu",
        "password": "Student@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/student/dashboard", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "student_profile" in data
    assert "enrolled_courses" in data
    assert "pending_assessments" in data
    assert "current_mastery_percentage" in data
    assert "weak_topics" in data
    assert "recommended_learning_activities" in data
    assert "upcoming_deadlines" in data
    assert "progress_trend" in data
    assert "notifications" in data

def test_student_unauthorized_to_admin_and_faculty():
    """Verify student is denied access to admin and faculty endpoints with 403 Forbidden."""
    login_res = client.post("/api/auth/login", json={
        "email": "student1@college.edu",
        "password": "Student@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to list faculty (Admin only)
    res_admin = client.get("/api/faculty", headers=headers)
    assert res_admin.status_code == 403

    # Attempt to access question papers endpoint (Faculty only)
    res_faculty = client.get("/api/question-paper", headers=headers)
    assert res_faculty.status_code == 403

def test_faculty_denied_student_dashboard():
    """Verify faculty cannot access student-only dashboard with 403 Forbidden."""
    login_res = client.post("/api/auth/login", json={
        "email": "faculty@college.edu",
        "password": "Faculty@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/student/dashboard", headers=headers)
    assert res.status_code == 403
