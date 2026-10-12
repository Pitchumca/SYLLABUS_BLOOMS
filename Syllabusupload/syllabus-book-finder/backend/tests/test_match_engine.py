import pytest
from app.services.match_engine import (
    calculate_match_confidence,
    classify_access_tier,
    get_access_color,
    ACCESS_VERIFIED_OPEN,
    ACCESS_BORROWING,
    ACCESS_PREVIEW,
    ACCESS_NONE
)

def test_exact_isbn_match():
    query = {"title": "Introduction to Algorithms", "isbn": "9780262033848"}
    candidate = {"title": "Intro Algorithms", "isbn": "978-0262033848"}
    
    score, summary = calculate_match_confidence(query, candidate)
    assert score == 100.0
    assert "ISBN match" in summary

def test_title_and_author_similarity():
    query = {"title": "Data Structures and Algorithm Analysis in C++", "authors": "Mark Allen Weiss", "publication_year": "2014"}
    candidate = {"title": "Data Structures and Algorithm Analysis in C++", "authors": "Weiss, Mark Allen", "publication_year": "2014"}

    score, summary = calculate_match_confidence(query, candidate)
    assert score >= 80.0

def test_access_tier_classification():
    # Open access
    acc_type, status, _ = classify_access_tier(
        "Google Books",
        {"viewability": "ALL_PAGES", "is_open_access": True},
        confidence=90.0
    )
    assert acc_type == ACCESS_VERIFIED_OPEN
    assert get_access_color(acc_type) == "green"

    # Preview
    acc_type2, _, _ = classify_access_tier(
        "Google Books",
        {"viewability": "PARTIAL", "has_preview": True},
        confidence=85.0
    )
    assert acc_type2 == ACCESS_PREVIEW
    assert get_access_color(acc_type2) == "blue"

    # Low confidence
    acc_type3, _, _ = classify_access_tier(
        "Any",
        {"viewability": "ALL_PAGES"},
        confidence=20.0
    )
    assert acc_type3 == ACCESS_NONE
    assert get_access_color(acc_type3) == "red"

def test_author_mismatch_penalty():
    # Same title "Algorithms", but completely different authors (Cormen vs Sedgewick)
    query = {"title": "Algorithms", "authors": "Thomas H. Cormen"}
    candidate_mismatch = {"title": "Algorithms", "authors": "Robert Sedgewick and Kevin Wayne"}
    candidate_match = {"title": "Algorithms", "authors": "Cormen, Leiserson, Rivest, Stein"}

    score_mismatch, _ = calculate_match_confidence(query, candidate_mismatch)
    score_match, _ = calculate_match_confidence(query, candidate_match)

    # The exact matching author must have a significantly higher score
    assert score_match > score_mismatch
    assert score_match >= 85.0

def test_internet_archive_direct_pdf_classification():
    acc_type, status, remarks = classify_access_tier(
        "Internet Archive",
        {"has_pdf": True, "access_url": "https://archive.org/download/item/item.pdf"},
        confidence=90.0
    )
    assert acc_type == ACCESS_VERIFIED_OPEN
    assert "Direct PDF" in status
