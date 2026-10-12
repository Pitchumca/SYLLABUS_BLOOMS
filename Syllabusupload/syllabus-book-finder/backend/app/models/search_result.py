import json
import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class SearchResult(Base):
    __tablename__ = "search_results"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    
    source = Column(String(100), nullable=False) # Google Books, Open Library, Crossref, Internet Archive, DOAB, etc.
    title = Column(String(500), nullable=True)
    subtitle = Column(String(500), nullable=True)
    authors = Column(String(500), nullable=True)
    authors_json = Column(Text, nullable=True) # JSON list of authors
    publisher = Column(String(255), nullable=True)
    edition = Column(String(100), nullable=True)
    publication_year = Column(String(50), nullable=True)
    isbn = Column(String(50), nullable=True)
    isbn_10 = Column(String(20), nullable=True)
    isbn_13 = Column(String(20), nullable=True)

    # Identifiers & URLs
    internet_archive_identifier = Column(String(255), nullable=True)
    internet_archive_item_url = Column(Text, nullable=True)
    verified_download_url = Column(Text, nullable=True)
    access_url = Column(Text, nullable=True)

    # Access classification states:
    # PUBLIC_PDF_VERIFIED, PUBLIC_EPUB_VERIFIED, BORROW_REQUIRED, PREVIEW_ONLY, METADATA_ONLY, LINK_UNAVAILABLE, VERIFICATION_FAILED
    access_status = Column(String(50), nullable=False, default="METADATA_ONLY")
    access_type = Column(String(100), nullable=False, default="No verified access found")
    rights_or_license = Column(String(255), nullable=True)

    # Server-side verification telemetry
    verification_http_status = Column(Integer, nullable=True)
    verification_message = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    local_file_path = Column(String(500), nullable=True)
    checksum_sha256 = Column(String(64), nullable=True)
    
    # Match confidence percentage (0.0 to 100.0)
    confidence_score = Column(Float, default=0.0)
    
    # Verification status e.g. "Verified API match", "Partial match", "Unverified", "No access"
    verification_status = Column(String(100), default="Unverified")
    
    remarks = Column(Text, nullable=True)
    raw_response_json = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    book = relationship("Book", back_populates="search_results")

    @property
    def authors_list(self) -> List[str]:
        if self.authors_json:
            try:
                return json.loads(self.authors_json)
            except Exception:
                pass
        if self.authors:
            return [a.strip() for a in self.authors.split(";") if a.strip()]
        return []

