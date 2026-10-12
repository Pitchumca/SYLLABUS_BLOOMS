from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.syllabus import Syllabus
from app.models.book import Book
from app.models.search_result import SearchResult
from app.schemas.book import (
    BookResponse,
    BookCreate,
    BookUpdate,
    BookMergeRequest,
    BookParseRequest
)
from app.services.book_parser import detect_and_parse_books
from app.utils.security import sanitize_input_text

router = APIRouter(prefix="/books", tags=["Books & Review"])

def _do_parse_books(syllabus_id: int, custom_text: Optional[str], db: Session) -> List[Book]:
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")

    text_to_parse = custom_text or syllabus.extracted_text or ""
    if not text_to_parse.strip():
        raise HTTPException(status_code=400, detail="No syllabus text found to parse. Please upload or paste text.")

    # Remove existing auto-parsed books for this syllabus to avoid duplicate accumulation
    db.query(Book).filter(Book.syllabus_id == syllabus_id, Book.is_manually_added == False).delete()
    db.commit()

    parsed_data = detect_and_parse_books(text_to_parse)

    created_books = []
    for item in parsed_data:
        new_book = Book(
            syllabus_id=syllabus.id,
            category=item.get("category", "Textbook"),
            title=item.get("title", "Untitled Book"),
            authors=item.get("authors"),
            edition=item.get("edition"),
            publisher=item.get("publisher"),
            publication_year=item.get("publication_year"),
            isbn=item.get("isbn"),
            raw_citation=item.get("raw_citation"),
            confidence_score=item.get("confidence_score", 50.0),
            is_duplicate=item.get("is_duplicate", False),
            is_reviewed=False,
            is_manually_added=False
        )
        db.add(new_book)
        created_books.append(new_book)

    syllabus.status = "parsed"
    db.commit()

    for b in created_books:
        db.refresh(b)

    return created_books

@router.post("/parse", response_model=List[BookResponse])
def parse_books_from_syllabus(
    payload: BookParseRequest,
    db: Session = Depends(get_db)
):
    """Parse Textbook and Reference Book sections from syllabus text via JSON body."""
    return _do_parse_books(payload.syllabus_id, payload.custom_text, db)

@router.post("/parse/{syllabus_id}", response_model=List[BookResponse])
def parse_books_by_id(
    syllabus_id: int,
    payload: Optional[BookParseRequest] = None,
    db: Session = Depends(get_db)
):
    """Parse Textbook and Reference Book sections from syllabus text by path parameter."""
    custom_text = payload.custom_text if payload else None
    return _do_parse_books(syllabus_id, custom_text, db)

@router.get("/syllabus/{syllabus_id}", response_model=List[BookResponse])
@router.get("", response_model=List[BookResponse])
def get_books(
    syllabus_id: Optional[int] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List books for a specific syllabus with optional category or text search filtering."""
    if not syllabus_id:
        raise HTTPException(status_code=400, detail="syllabus_id is required.")

    query = db.query(Book).filter(Book.syllabus_id == syllabus_id)

    if category and category != "All":
        query = query.filter(Book.category == category)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (Book.title.ilike(s)) |
            (Book.authors.ilike(s)) |
            (Book.publisher.ilike(s)) |
            (Book.isbn.ilike(s))
        )

    return query.order_by(Book.id.asc()).all()

@router.post("/syllabus/{syllabus_id}", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
def add_book_manually(
    payload: BookCreate,
    syllabus_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Add a missing book manually during review."""
    target_syllabus_id = syllabus_id or payload.syllabus_id
    syllabus = db.query(Syllabus).filter(Syllabus.id == target_syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")

    new_book = Book(
        syllabus_id=target_syllabus_id,
        category=payload.category,
        title=sanitize_input_text(payload.title),
        authors=sanitize_input_text(payload.authors) if payload.authors else None,
        edition=sanitize_input_text(payload.edition) if payload.edition else None,
        publisher=sanitize_input_text(payload.publisher) if payload.publisher else None,
        publication_year=sanitize_input_text(payload.publication_year) if payload.publication_year else None,
        isbn=sanitize_input_text(payload.isbn) if payload.isbn else None,
        raw_citation="Manually added by reviewer",
        is_reviewed=True,
        is_manually_added=True,
        confidence_score=100.0
    )
    db.add(new_book)
    db.commit()
    db.refresh(new_book)
    return new_book

@router.put("/{book_id}", response_model=BookResponse)
def update_book(
    book_id: int,
    payload: BookUpdate,
    db: Session = Depends(get_db)
):
    """Update editable book details (category, title, author, edition, publisher, year, ISBN, review status)."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found.")

    if payload.category is not None:
        book.category = payload.category
    if payload.title is not None:
        book.title = sanitize_input_text(payload.title)
    if payload.authors is not None:
        book.authors = sanitize_input_text(payload.authors)
    if payload.edition is not None:
        book.edition = sanitize_input_text(payload.edition)
    if payload.publisher is not None:
        book.publisher = sanitize_input_text(payload.publisher)
    if payload.publication_year is not None:
        book.publication_year = sanitize_input_text(payload.publication_year)
    if payload.isbn is not None:
        book.isbn = sanitize_input_text(payload.isbn)
    if payload.is_reviewed is not None:
        book.is_reviewed = payload.is_reviewed

    db.commit()
    db.refresh(book)
    return book

@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, db: Session = Depends(get_db)):
    """Delete an incorrect book record."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found.")

    db.delete(book)
    db.commit()
    return None

@router.post("/merge/{target_book_id}", response_model=BookResponse)
@router.post("/merge", response_model=BookResponse)
def merge_duplicate_books(
    payload: dict,
    target_book_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Merge duplicate book records into the target book record.
    Transfers associated search results and deletes the merged source records.
    """
    actual_target_id = target_book_id or payload.get("target_book_id")
    if not actual_target_id:
        raise HTTPException(status_code=400, detail="Target book ID is required.")

    source_ids = payload.get("source_book_ids") or payload.get("secondary_book_ids") or []
    merged_info = payload.get("merged_data") or payload.get("override_data") or {}

    target = db.query(Book).filter(Book.id == actual_target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target book record not found.")

    if isinstance(merged_info, dict):
        if merged_info.get("title"):
            target.title = sanitize_input_text(merged_info["title"])
        if merged_info.get("authors"):
            target.authors = sanitize_input_text(merged_info["authors"])
        if merged_info.get("edition"):
            target.edition = sanitize_input_text(merged_info["edition"])
        if merged_info.get("publisher"):
            target.publisher = sanitize_input_text(merged_info["publisher"])
        if merged_info.get("publication_year"):
            target.publication_year = sanitize_input_text(str(merged_info["publication_year"]))
        if merged_info.get("isbn"):
            target.isbn = sanitize_input_text(merged_info["isbn"])
        if merged_info.get("category"):
            target.category = merged_info["category"]

    target.is_reviewed = True
    target.is_duplicate = False

    for s_id in source_ids:
        if s_id != target.id:
            db.query(SearchResult).filter(SearchResult.book_id == s_id).update({"book_id": target.id})
            db.query(Book).filter(Book.id == s_id).delete()

    db.commit()
    db.refresh(target)
    return target

@router.post("/confirm-all/{syllabus_id}")
def confirm_all_books(syllabus_id: int, db: Session = Depends(get_db)):
    """Mark all books in a syllabus as reviewed and confirmed."""
    db.query(Book).filter(Book.syllabus_id == syllabus_id).update({"is_reviewed": True})
    db.commit()
    return {"message": "All books confirmed as reviewed."}
