import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id", ondelete="CASCADE"), nullable=False)
    
    # Categorization: 'Textbook' or 'Reference Book'
    category = Column(String(50), nullable=False, default="Textbook")
    
    # Bibliographic fields
    title = Column(String(500), nullable=False)
    subtitle = Column(String(500), nullable=True)
    authors = Column(String(500), nullable=True)
    authors_json = Column(Text, nullable=True)
    edition = Column(String(100), nullable=True)
    publisher = Column(String(255), nullable=True)
    publication_year = Column(String(50), nullable=True)
    isbn = Column(String(50), nullable=True)
    isbn_10 = Column(String(20), nullable=True)
    isbn_13 = Column(String(20), nullable=True)
    raw_citation = Column(Text, nullable=True)
    
    # Review & management flags
    is_reviewed = Column(Boolean, default=False)
    is_manually_added = Column(Boolean, default=False)
    is_duplicate = Column(Boolean, default=False)
    confidence_score = Column(Float, default=0.0) # parser confidence or match confidence
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    syllabus = relationship("Syllabus", back_populates="books")
    search_results = relationship("SearchResult", back_populates="book", cascade="all, delete-orphan")
