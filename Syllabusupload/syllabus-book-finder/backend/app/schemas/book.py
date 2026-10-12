from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from app.schemas.search_result import SearchResultResponse

class BookBase(BaseModel):
    category: str = "Textbook" # Textbook or Reference Book
    title: str
    authors: Optional[str] = None
    edition: Optional[str] = None
    publisher: Optional[str] = None
    publication_year: Optional[str] = None
    isbn: Optional[str] = None
    raw_citation: Optional[str] = None

class BookCreate(BookBase):
    syllabus_id: int
    is_reviewed: bool = False
    is_manually_added: bool = False
    confidence_score: float = 0.0

class BookUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    edition: Optional[str] = None
    publisher: Optional[str] = None
    publication_year: Optional[str] = None
    isbn: Optional[str] = None
    is_reviewed: Optional[bool] = None

class BookMergeRequest(BaseModel):
    target_book_id: int
    source_book_ids: List[int]
    merged_data: BookUpdate

class BookResponse(BookBase):
    id: int
    syllabus_id: int
    is_reviewed: bool
    is_manually_added: bool
    is_duplicate: bool
    confidence_score: float
    created_at: datetime
    updated_at: datetime
    search_results: List[SearchResultResponse] = []

    class Config:
        from_attributes = True

class BookParseRequest(BaseModel):
    syllabus_id: int
    custom_text: Optional[str] = None
