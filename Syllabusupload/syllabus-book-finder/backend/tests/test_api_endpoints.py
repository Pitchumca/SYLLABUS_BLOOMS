import io
import pytest
from unittest.mock import patch, AsyncMock
from app.models.syllabus import Syllabus
from app.models.book import Book

def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"

def test_upload_pdf_endpoint(client, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": ("syllabus.pdf", f, "application/pdf")}
        )
    assert res.status_code == 201
    data = res.json()
    assert data["original_filename"] == "syllabus.pdf"
    assert data["page_count"] >= 1
    assert len(data["extracted_text"]) > 100
    syllabus_id = data["id"]

    # Test parse books
    parse_res = client.post("/api/books/parse", json={"syllabus_id": syllabus_id})
    assert parse_res.status_code == 200
    books = parse_res.json()
    assert len(books) >= 4
    
    # Test book update
    book_id = books[0]["id"]
    up_res = client.put(f"/api/books/{book_id}", json={"edition": "4th Edition", "is_reviewed": True})
    assert up_res.status_code == 200
    assert up_res.json()["edition"] == "4th Edition"
    assert up_res.json()["is_reviewed"] is True

    # Test add manual book
    add_res = client.post(
        "/api/books",
        json={
            "syllabus_id": syllabus_id,
            "category": "Reference Book",
            "title": "Clean Code",
            "authors": "Robert C. Martin",
            "publisher": "Prentice Hall",
            "publication_year": "2008"
        }
    )
    assert add_res.status_code == 201
    assert add_res.json()["title"] == "Clean Code"

    # Test analytics endpoint
    analytics_res = client.get(f"/api/analytics/{syllabus_id}")
    assert analytics_res.status_code == 200
    stats = analytics_res.json()
    assert stats["total_books"] >= 5
    assert stats["total_textbooks"] >= 1

def test_invalid_file_upload(client):
    # Upload plain text as PDF
    fake_data = b"This is not a PDF file"
    res = client.post(
        "/api/upload",
        files={"file": ("test.pdf", fake_data, "application/pdf")}
    )
    assert res.status_code == 400
    assert "header" in res.json()["detail"].lower()

def test_book_extraction_and_search_endpoints(client, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": ("r_prog_syllabus.pdf", f, "application/pdf")}
        )
    assert res.status_code == 201
    syllabus_id = res.json()["id"]

    r_prog_text = (
        "TEXT BOOKS:\n"
        "3. The Art of R Programming: A Tour of Statistical Software Design, Norman Matloff, No Starch Press, 2011\n"
        "4. R for Everyone: Advanced Analytics and Graphics, Jared P. Lander, Addison-Wesley Data & Analytics Series, 2013.\n"
        "REFERENCES:\n"
        "3. Beginning R - The Statistical Programming Language, Mark Gardener, Wiley, 2013.\n"
        "4. Introductory R: A Beginner's Guide to Data Visualisation, Statistical Analysis and Programming in R, Robert Knell, Amazon Digital South Asia Services Inc, 2013\n"
        "COURSE DESIGNERS\n"
        "S.No Name of the Faculty Designation Department Email\n"
        "1 Dr.R.Jaichandran Professor CSE\n"
    )

    # 1. Test POST /api/books/parse/{syllabus_id} with custom text
    parse_res = client.post(f"/api/books/parse/{syllabus_id}", json={"syllabus_id": syllabus_id, "custom_text": r_prog_text})
    assert parse_res.status_code == 200
    books = parse_res.json()
    assert len(books) == 4

    # Verify Title and Author are correctly assigned, not swapped
    assert "The Art of R Programming" in books[0]["title"]
    assert books[0]["authors"] == "Norman Matloff"
    assert books[0]["publisher"] == "No Starch Press"

    assert "R for Everyone" in books[1]["title"]
    assert books[1]["authors"] == "Jared P. Lander"

    assert "Beginning R" in books[2]["title"]
    assert books[2]["authors"] == "Mark Gardener"

    assert "Introductory R" in books[3]["title"]
    assert books[3]["authors"] == "Robert Knell"

    # 2. Test GET /api/books/syllabus/{syllabus_id}
    get_res = client.get(f"/api/books/syllabus/{syllabus_id}")
    assert get_res.status_code == 200
    assert len(get_res.json()) == 4

    # 3. Test POST /api/books/syllabus/{syllabus_id} manual add
    manual_res = client.post(
        f"/api/books/syllabus/{syllabus_id}",
        json={
            "syllabus_id": syllabus_id,
            "category": "Reference Book",
            "title": "Hands-On Programming with R",
            "authors": "Garrett Grolemund",
            "publisher": "O'Reilly",
            "publication_year": "2014"
        }
    )
    assert manual_res.status_code == 201
    manual_book = manual_res.json()
    assert manual_book["title"] == "Hands-On Programming with R"

    # 4. Test POST /api/books/confirm-all/{syllabus_id}
    confirm_res = client.post(f"/api/books/confirm-all/{syllabus_id}")
    assert confirm_res.status_code == 200

    # 5. Test GET /api/search/syllabus/{syllabus_id}
    search_get_res = client.get(f"/api/search/syllabus/{syllabus_id}")
    assert search_get_res.status_code == 200
    results = search_get_res.json()
    assert len(results) == 5

    # 6. Test POST /api/books/merge/{target_book_id}
    merge_res = client.post(
        f"/api/books/merge/{books[0]['id']}",
        json={
            "secondary_book_ids": [manual_book["id"]],
            "override_data": {
                "title": "The Art of R Programming (Updated)"
            }
        }
    )
    assert merge_res.status_code == 200
    assert merge_res.json()["title"] == "The Art of R Programming (Updated)"
