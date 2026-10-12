import docx
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_download_docx_unauthenticated():
    """Ensure unauthenticated download request is strictly rejected with 401."""
    res = client.get("/api/question-paper/11/download-docx")
    assert res.status_code == 401
    assert "detail" in res.json()
    assert "not provided" in res.json()["detail"].lower() or "credentials" in res.json()["detail"].lower()

def test_download_docx_authenticated_faculty():
    """Ensure authenticated faculty receives valid 200 DOCX binary with Content-Disposition."""
    login_res = client.post("/api/auth/login", json={
        "email": "faculty@college.edu",
        "password": "Faculty@123"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/question-paper/11/download-docx", headers=headers)
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in res.headers["content-type"]
    assert "content-disposition" in res.headers
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert ".docx" in res.headers["content-disposition"]

    # Verify DOCX content validity with python-docx
    doc_bytes = io.BytesIO(res.content)
    doc = docx.Document(doc_bytes)
    assert len(doc.tables) >= 5 # Metadata, Part A, Part B, Part C, CO Summary, Bloom Summary
    assert len(res.content) > 10000

def test_export_docx_post_endpoint():
    """Ensure POST export endpoint also returns valid DOCX binary."""
    login_res = client.post("/api/auth/login", json={
        "email": "faculty@college.edu",
        "password": "Faculty@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/question-paper/11/export/docx", headers=headers)
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in res.headers["content-type"]
    assert len(res.content) > 10000

def test_download_docx_student_forbidden():
    """Ensure student role is forbidden (403) from exporting faculty question paper."""
    login_res = client.post("/api/auth/login", json={
        "email": "student1@college.edu",
        "password": "Student@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/question-paper/11/download-docx", headers=headers)
    assert res.status_code == 403


def test_export_validation_paper_47():
    """Verify Paper #47 export validation endpoint returns 100% ready and can_export=True."""
    login_res = client.post("/api/auth/login", json={
        "email": "faculty@college.edu",
        "password": "Faculty@123"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/question-paper/47/export-validation/", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["paper_id"] == 47
    assert data["total_questions"] == 13
    assert data["approved_questions"] == 13
    assert data["draft_questions"] == 0
    assert data["rejected_questions"] == 0
    assert data["invalid_questions"] == 0
    assert data["can_export"] is True
    assert data["marks_valid"] is True
    assert data["co_mapping_complete"] is True
    assert data["bloom_mapping_complete"] is True
    assert data["or_pairs_complete"] is True


def test_export_all_3_formats_paper_47():
    """Verify all 3 export formats (question_paper, with_answer_key, evaluation_scheme) download successfully."""
    login_res = client.post("/api/auth/login", json={
        "email": "faculty@college.edu",
        "password": "Faculty@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    formats = ["question_paper", "with_answer_key", "evaluation_scheme"]
    for fmt in formats:
        res = client.get(f"/api/question-paper/47/download-docx?export_type={fmt}&export_approved_only=true", headers=headers)
        assert res.status_code == 200, f"Format {fmt} failed with {res.status_code}: {res.text}"
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in res.headers["content-type"]
        assert "content-disposition" in res.headers
        assert ".docx" in res.headers["content-disposition"]
        assert len(res.content) > 5000

