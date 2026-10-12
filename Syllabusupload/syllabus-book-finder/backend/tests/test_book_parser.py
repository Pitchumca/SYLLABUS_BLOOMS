import pytest
from app.services.book_parser import (
    detect_and_parse_books,
    parse_single_citation,
    extract_isbn,
    extract_edition,
    extract_publisher,
    extract_year,
    flag_duplicates
)

def test_extract_isbn():
    cit1 = "Thomas H. Cormen, 'Introduction to Algorithms', 3rd Edition, PHI, 2009, ISBN: 978-0262033848."
    assert extract_isbn(cit1) == "9780262033848"

    cit2 = "Sedgewick, Algorithms, 4th ed, ISBN 0-321-57351-0"
    assert extract_isbn(cit2) == "0321573510"

def test_extract_edition():
    assert extract_edition("3rd Edition, Pearson, 2012") == "3rd Edition"
    assert extract_edition("Fundamentals of Algorithms, 2nd ed., 2008") == "2nd ed"

def test_extract_publisher():
    assert extract_publisher("Pearson Education, 2014") in ("Pearson", "Pearson Education")
    assert extract_publisher("Published by McGraw-Hill, 2010") in ("McGraw-Hill", "McGraw Hill")
    assert extract_publisher("John Wiley & Sons, 2013") in ("John Wiley & Sons", "Wiley")

def test_extract_year():
    assert extract_year("Pearson Education, 2014, ISBN: 978-0132847377") == "2014"
    assert extract_year("MIT Press, (2009)") == "2009"

def test_parse_single_citation():
    cit = '1. Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein, "Introduction to Algorithms", 3rd Edition, PHI Learning / MIT Press, 2009, ISBN: 978-0262033848.'
    book = parse_single_citation(cit, category="Textbook")
    
    assert book["category"] == "Textbook"
    assert "Introduction to Algorithms" in book["title"]
    assert "Cormen" in book["authors"]
    assert "3rd Edition" in book["edition"]
    assert "2009" in book["publication_year"]
    assert book["isbn"] == "9780262033848"
    assert book["confidence_score"] >= 80.0

def test_parse_indian_university_citation():
    # Anna University / VTU style T1 and R1
    cit = "T1: Mark Allen Weiss, Data Structures and Algorithm Analysis in C++, 4th Edition, Pearson Education, 2014, ISBN: 978-0132847377."
    book = parse_single_citation(cit, category="Textbook")
    assert "Data Structures" in book["title"]
    assert "Weiss" in book["authors"]
    assert book["publication_year"] == "2014"

def test_detect_and_parse_books_full(sample_text_path):
    text = sample_text_path.read_text(encoding="utf-8")
    books = detect_and_parse_books(text)

    assert len(books) >= 5
    textbooks = [b for b in books if b["category"] == "Textbook"]
    reference_books = [b for b in books if b["category"] == "Reference Book"]

    assert len(textbooks) >= 3
    assert len(reference_books) >= 3

    # Check that Cormen and Goodrich are detected
    titles = [b["title"] for b in books]
    assert any("Algorithms" in t for t in titles)

def test_duplicate_detection():
    books = [
        {"title": "Introduction to Algorithms", "authors": "Cormen et al.", "isbn": "9780262033848"},
        {"title": "Introduction to Algorithms 3rd Ed", "authors": "Thomas Cormen", "isbn": "9780262033848"}
    ]
    flag_duplicates(books)
    assert books[1]["is_duplicate"] is True
