from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class SearchResultBase(BaseModel):
    source: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    authors: Optional[str] = None
    authors_list: Optional[List[str]] = None
    publisher: Optional[str] = None
    edition: Optional[str] = None
    publication_year: Optional[str] = None
    isbn: Optional[str] = None
    isbn_10: Optional[str] = None
    isbn_13: Optional[str] = None
    internet_archive_identifier: Optional[str] = None
    internet_archive_item_url: Optional[str] = None
    verified_download_url: Optional[str] = None
    access_status: str = "METADATA_ONLY"
    access_type: str = "No verified access found"
    rights_or_license: Optional[str] = None
    verification_http_status: Optional[int] = None
    verification_message: Optional[str] = None
    verified_at: Optional[datetime] = None
    local_file_path: Optional[str] = None
    checksum_sha256: Optional[str] = None
    access_url: Optional[str] = None
    confidence_score: float = 0.0
    verification_status: str = "Unverified"
    remarks: Optional[str] = None

class SearchResultCreate(SearchResultBase):
    book_id: int
    raw_response_json: Optional[str] = None

class SearchResultResponse(SearchResultBase):
    id: int
    book_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

