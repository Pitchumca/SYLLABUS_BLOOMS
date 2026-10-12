import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base

class CourseResource(Base):
    """
    Associates course, syllabus and academic resources (Textbooks and Reference Books).
    """
    __tablename__ = "course_resources"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id", ondelete="CASCADE"), nullable=True)
    resource_type = Column(String(50), nullable=False, default="TEXTBOOK") # TEXTBOOK, REFERENCE_BOOK
    
    book_metadata_id = Column(Integer, ForeignKey("book_metadata.id", ondelete="CASCADE"), nullable=True)
    book_file_id = Column(Integer, ForeignKey("book_files.id", ondelete="SET NULL"), nullable=True)
    
    status = Column(String(50), default="active", nullable=False) # active, archived, recommended
    units_covered = Column(String(255), nullable=True) # e.g. "1,2,3,4,5"
    relevance_score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    # Relationships
    course = relationship("Course", foreign_keys=[course_id])
    syllabus = relationship("Syllabus", foreign_keys=[syllabus_id])
    metadata_record = relationship("BookMetadata", foreign_keys=[book_metadata_id], back_populates="course_resources")
    file_record = relationship("BookFile", foreign_keys=[book_file_id])


class BookMetadata(Base):
    """
    Normalized bibliographic metadata extracted from syllabus with structured separation.
    """
    __tablename__ = "book_metadata"

    id = Column(Integer, primary_key=True, index=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id", ondelete="CASCADE"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    legacy_book_id = Column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True)

    resource_type = Column(String(50), nullable=False, default="TEXTBOOK") # "TEXTBOOK", "REFERENCE_BOOK"
    book_title = Column(String(500), nullable=False)
    subtitle = Column(String(500), nullable=True)
    publisher = Column(String(255), nullable=True)
    edition = Column(String(100), nullable=True)
    publication_year = Column(Integer, nullable=True)
    isbn_10 = Column(String(20), nullable=True, index=True)
    isbn_13 = Column(String(20), nullable=True, index=True)
    volume = Column(String(50), nullable=True)
    doi = Column(String(100), nullable=True, index=True)
    original_citation = Column(Text, nullable=True)
    metadata_confidence = Column(Float, default=0.95)

    canonical_book_id = Column(String(100), nullable=True, index=True)
    is_reviewed = Column(Boolean, default=False)
    is_duplicate = Column(Boolean, default=False)
    best_metadata_source = Column(String(100), nullable=True)
    best_download_source = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    # Relationships
    syllabus = relationship("Syllabus", foreign_keys=[syllabus_id])
    course = relationship("Course", foreign_keys=[course_id])
    legacy_book = relationship("Book", foreign_keys=[legacy_book_id])
    authors = relationship("BookAuthor", back_populates="book_metadata", cascade="all, delete-orphan", order_by="BookAuthor.order_index")
    sources = relationship("BookSource", back_populates="book_metadata", cascade="all, delete-orphan")
    files = relationship("BookFile", back_populates="book_metadata", cascade="all, delete-orphan")
    course_resources = relationship("CourseResource", back_populates="metadata_record")
    rag_documents = relationship("RAGDocument", back_populates="book_metadata")
    syllabus_mappings = relationship("SyllabusBookMapping", back_populates="book_metadata")


class BookAuthor(Base):
    """
    Separated bibliographic author or editor entities.
    """
    __tablename__ = "book_authors"

    id = Column(Integer, primary_key=True, index=True)
    book_metadata_id = Column(Integer, ForeignKey("book_metadata.id", ondelete="CASCADE"), nullable=False)
    
    given_name = Column(String(150), nullable=True)
    family_name = Column(String(150), nullable=True)
    display_name = Column(String(300), nullable=False)
    role = Column(String(50), default="author", nullable=False) # author, editor, translator
    order_index = Column(Integer, default=0, nullable=False)

    book_metadata = relationship("BookMetadata", back_populates="authors")


class BookSource(Base):
    """
    Candidate source record discovered across search providers.
    """
    __tablename__ = "book_sources"

    id = Column(Integer, primary_key=True, index=True)
    book_metadata_id = Column(Integer, ForeignKey("book_metadata.id", ondelete="CASCADE"), nullable=False)
    
    source_name = Column(String(100), nullable=False) # 'Internet Archive', 'Open Library', 'Google Books', etc.
    source_url = Column(Text, nullable=True)
    landing_page_url = Column(Text, nullable=True)
    
    access_type = Column(String(100), default="Catalog Record", nullable=False)
    access_status = Column(String(50), default="METADATA_ONLY", nullable=False) # PUBLIC_PDF_VERIFIED, BORROW_REQUIRED, etc.
    
    candidate_match_score = Column(Float, default=0.0) # Percentage 0-100
    candidate_match_classification = Column(String(50), default="Metadata Only") # Exact Match, Probable Match, Different Edition, Related Book, Metadata Only, Rejected Match
    
    raw_metadata_json = Column(Text, nullable=True)
    is_best_metadata_source = Column(Boolean, default=False)
    is_best_download_source = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    book_metadata = relationship("BookMetadata", back_populates="sources")
    verification_logs = relationship("ResourceVerificationLog", back_populates="book_source")


class BookFile(Base):
    """
    Locally downloaded and verified eBook file stored in course directories.
    """
    __tablename__ = "book_files"

    id = Column(Integer, primary_key=True, index=True)
    book_metadata_id = Column(Integer, ForeignKey("book_metadata.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id", ondelete="SET NULL"), nullable=True)
    
    file_format = Column(String(20), default="pdf", nullable=False) # pdf, epub
    file_size_bytes = Column(Integer, default=0, nullable=False)
    sha256_checksum = Column(String(64), index=True, nullable=False)
    local_path = Column(String(500), nullable=False)
    source_url = Column(Text, nullable=True)
    
    is_verified = Column(Boolean, default=True, nullable=False)
    verification_status = Column(String(100), default="Verified")
    verification_http_status = Column(Integer, default=200)
    verification_message = Column(Text, nullable=True)
    verified_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    download_job_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    book_metadata = relationship("BookMetadata", back_populates="files")
    course = relationship("Course", foreign_keys=[course_id])
    syllabus = relationship("Syllabus", foreign_keys=[syllabus_id])
    extraction_jobs = relationship("ExtractionJob", back_populates="book_file")
    rag_documents = relationship("RAGDocument", back_populates="book_file")


class DownloadJobModel(Base):
    """
    Database entity for persistent download jobs with multi-step status.
    """
    __tablename__ = "download_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_uuid = Column(String(100), unique=True, index=True, nullable=False)
    book_metadata_id = Column(Integer, ForeignKey("book_metadata.id", ondelete="CASCADE"), nullable=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)

    status = Column(String(100), default="Searching", nullable=False)
    progress_pct = Column(Integer, default=5, nullable=False)
    message = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    
    is_cancelled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))


class ExtractionJob(Base):
    """
    Tracks text extraction, Table of Contents parsing, and selective OCR.
    """
    __tablename__ = "extraction_jobs"

    id = Column(Integer, primary_key=True, index=True)
    book_file_id = Column(Integer, ForeignKey("book_files.id", ondelete="CASCADE"), nullable=False)
    book_metadata_id = Column(Integer, ForeignKey("book_metadata.id", ondelete="CASCADE"), nullable=False)
    
    status = Column(String(50), default="pending", nullable=False) # pending, extracting, completed, failed
    total_pages = Column(Integer, default=0)
    ocr_applied_pages = Column(Integer, default=0)
    toc_extracted_json = Column(Text, nullable=True)
    headings_extracted_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    book_file = relationship("BookFile", back_populates="extraction_jobs")


class RAGDocument(Base):
    """
    RAG indexed document reference connected to course and vector index.
    """
    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, index=True)
    book_file_id = Column(Integer, ForeignKey("book_files.id", ondelete="CASCADE"), nullable=True)
    book_metadata_id = Column(Integer, ForeignKey("book_metadata.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id", ondelete="CASCADE"), nullable=True)
    
    resource_type = Column(String(50), default="TEXTBOOK", nullable=False)
    title = Column(String(500), nullable=False)
    total_chunks = Column(Integer, default=0, nullable=False)
    checksum = Column(String(64), nullable=False)
    index_path = Column(String(500), nullable=True)
    status = Column(String(50), default="indexed", nullable=False) # indexed, failed, out_of_date
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    book_file = relationship("BookFile", back_populates="rag_documents")
    book_metadata = relationship("BookMetadata", back_populates="rag_documents")
    chunks = relationship("RAGChunk", back_populates="rag_document", cascade="all, delete-orphan")


class RAGChunk(Base):
    """
    Semantic chunk indexed for RAG with strict provenance attributes.
    """
    __tablename__ = "rag_chunks"

    id = Column(Integer, primary_key=True, index=True)
    rag_document_id = Column(Integer, ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=True)
    book_metadata_id = Column(Integer, ForeignKey("book_metadata.id", ondelete="CASCADE"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id", ondelete="CASCADE"), nullable=True)
    
    course_code = Column(String(50), nullable=True)
    course_name = Column(String(255), nullable=True)
    resource_type = Column(String(50), default="TEXTBOOK", nullable=False)
    
    book_id = Column(String(100), nullable=True)
    book_title = Column(String(500), nullable=False)
    authors_json = Column(Text, nullable=True)
    publisher = Column(String(255), nullable=True)
    edition = Column(String(100), nullable=True)
    publication_year = Column(String(50), nullable=True)
    isbn = Column(String(50), nullable=True)
    
    chapter = Column(String(255), nullable=True)
    section = Column(String(255), nullable=True)
    page_start = Column(Integer, default=0, nullable=False)
    page_end = Column(Integer, default=0, nullable=False)
    unit_number = Column(Integer, default=1, nullable=False)
    syllabus_topics_json = Column(Text, nullable=True) # JSON array of topics
    course_outcomes_json = Column(Text, nullable=True) # JSON array of COs
    
    text = Column(Text, nullable=False)
    source_file = Column(String(500), nullable=True)
    source_url = Column(Text, nullable=True)
    checksum = Column(String(64), nullable=True)
    
    embedding_reference = Column(String(255), nullable=True)
    embedding_vector_json = Column(Text, nullable=True)
    topic_relevance_score = Column(Float, default=0.85)
    bloom_level = Column(String(50), default="L2")
    approved_for_generation = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    rag_document = relationship("RAGDocument", back_populates="chunks")


class SyllabusBookMapping(Base):
    """
    Syllabus Topic to Textbook / Reference Book alignment coverage matrix.
    """
    __tablename__ = "syllabus_book_mappings"

    id = Column(Integer, primary_key=True, index=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    
    unit_number = Column(Integer, nullable=False)
    syllabus_topic = Column(String(500), nullable=False)
    book_metadata_id = Column(Integer, ForeignKey("book_metadata.id", ondelete="CASCADE"), nullable=False)
    
    chapter = Column(String(255), nullable=True)
    pages = Column(String(100), nullable=True)
    relevance_score = Column(Float, default=0.0)
    rag_status = Column(String(50), default="Indexed", nullable=False) # Indexed, Pending, Unavailable
    co_level = Column(String(50), default="CO1")
    bloom_level = Column(String(50), default="L2")

    book_metadata = relationship("BookMetadata", back_populates="syllabus_mappings")


class ResourceVerificationLog(Base):
    """
    Detailed audit log of candidate URL pre-validation.
    """
    __tablename__ = "resource_verification_logs"

    id = Column(Integer, primary_key=True, index=True)
    book_source_id = Column(Integer, ForeignKey("book_sources.id", ondelete="SET NULL"), nullable=True)
    book_file_id = Column(Integer, ForeignKey("book_files.id", ondelete="SET NULL"), nullable=True)
    
    source_url = Column(Text, nullable=False)
    final_url = Column(Text, nullable=True)
    http_status_code = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    is_valid_signature = Column(Boolean, default=False)
    file_signature = Column(String(50), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    
    # Outcomes: VERIFIED, LINK_UNAVAILABLE, ACCESS_REQUIRED, ACCESS_RESTRICTED, RATE_LIMITED, REPOSITORY_UNAVAILABLE, TIMEOUT, INVALID_FILE_RESPONSE
    verification_outcome = Column(String(50), nullable=False)
    error_detail = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    book_source = relationship("BookSource", back_populates="verification_logs")
    user = relationship("User")
