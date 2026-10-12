from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class BookAuthorSchema(BaseModel):
    given_name: Optional[str] = ""
    family_name: Optional[str] = ""
    display_name: str
    role: Optional[str] = "author"

class BookExtractionSchema(BaseModel):
    id: Optional[int] = None
    resource_type: str = "TEXTBOOK" # "TEXTBOOK" or "REFERENCE_BOOK"
    authors: List[BookAuthorSchema] = []
    book_title: str
    subtitle: Optional[str] = ""
    publisher: Optional[str] = "Not available"
    edition: Optional[str] = "Not available"
    publication_year: Optional[Any] = "Not available"
    isbn_10: Optional[str] = ""
    isbn_13: Optional[str] = ""
    volume: Optional[str] = ""
    doi: Optional[str] = ""
    original_citation: Optional[str] = ""
    metadata_confidence: float = 0.95
    canonical_book_id: Optional[str] = None
    is_reviewed: Optional[bool] = False
    is_duplicate: Optional[bool] = False

class SourceRecordSchema(BaseModel):
    source_name: str
    source_url: Optional[str] = None
    landing_page_url: Optional[str] = None
    access_type: str = "Catalog Record"
    access_status: str = "METADATA_ONLY"
    candidate_match_score: float = 0.0
    candidate_match_classification: str = "Metadata Only"
    verification_http_status: Optional[int] = None
    verification_message: Optional[str] = None
    is_verified: bool = False
    is_downloadable: bool = False
    verified_download_url: Optional[str] = None

class ConsolidatedBookSchema(BaseModel):
    canonical_book_id: str
    metadata: BookExtractionSchema
    metadata_sources: List[str] = []
    file_sources: List[SourceRecordSchema] = []
    best_metadata_source: Optional[str] = "Application Database"
    best_download_source: Optional[str] = None
    match_score: float = 0.0
    match_classification: str = "Metadata Only"

class PreValidationResultSchema(BaseModel):
    url: str
    final_url: Optional[str] = None
    http_status: int
    mime_type: Optional[str] = None
    file_signature: Optional[str] = None
    file_size_bytes: Optional[int] = None
    is_valid: bool
    status_label: str # "Direct PDF Available", "Link unavailable", "Access required", etc.
    user_friendly_message: str

class CoverageMatrixRowSchema(BaseModel):
    unit: int
    syllabus_topic: str
    textbook: str
    chapter: str
    pages: str
    relevance: float
    rag_status: str # "Indexed", "Pending", "Unavailable"

# Aliases for flexibility across routers and services
BookMetadataStructuredSchema = BookExtractionSchema
CandidateSourceRecord = SourceRecordSchema
SyllabusCoverageRowSchema = CoverageMatrixRowSchema

class BookMetadataUpdateRequest(BaseModel):
    book_title: Optional[str] = None
    authors: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[str] = None
    publication_year: Optional[str] = None
    isbn_10: Optional[str] = None
    isbn_13: Optional[str] = None
    resource_type: Optional[str] = None
