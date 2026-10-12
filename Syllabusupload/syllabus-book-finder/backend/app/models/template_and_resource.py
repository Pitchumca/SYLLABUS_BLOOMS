import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

# =============================================================================
# MODULE B & E: QUESTION PAPER TEMPLATE & EXTRACTED BLUEPRINT ENTITIES
# =============================================================================

class QuestionPaperTemplate(Base):
    __tablename__ = "question_paper_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False) # e.g. "AVIT Semester Examination Template"
    institution = Column(String(255), nullable=False, default="Aarupadai Veedu Institute of Technology")
    department = Column(String(255), nullable=True, default="Computer Science & Engineering")
    programme = Column(String(255), nullable=True, default="B.E. Computer Science and Engineering")
    regulation = Column(String(100), nullable=True, default="2021 (Autonomous)")
    exam_name = Column(String(255), nullable=True, default="Semester End Examination")
    exam_type = Column(String(100), nullable=True, default="Semester End") # "Internal Assessment", "Mid-Term", "Semester End"
    max_marks = Column(Integer, nullable=False, default=100)
    duration_minutes = Column(Integer, nullable=False, default=180)
    academic_year = Column(String(50), nullable=True, default="2024-2025")
    course_code = Column(String(100), nullable=True)
    course_title = Column(String(255), nullable=True)
    version = Column(Integer, default=1, nullable=False)

    # Ownership & Approval
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approval_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_department_default = Column(Boolean, default=False, nullable=False)
    is_course_default = Column(Boolean, default=False, nullable=False)

    # Template File Details
    original_filename = Column(String(255), nullable=True)
    stored_filename = Column(String(255), nullable=True)
    file_format = Column(String(50), nullable=True) # "docx", "pdf", "scanned_pdf", "image", "xlsx"
    instructions = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    versions = relationship("TemplateVersion", back_populates="template", cascade="all, delete-orphan")
    blueprints = relationship("ExtractedBlueprint", back_populates="template", cascade="all, delete-orphan")


class TemplateVersion(Base):
    __tablename__ = "template_versions"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("question_paper_templates.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    blueprint_json = Column(Text, nullable=False)
    stored_filename = Column(String(255), nullable=True)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    change_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    template = relationship("QuestionPaperTemplate", back_populates="versions")
    changed_by = relationship("User", foreign_keys=[changed_by_id])


class ExtractedBlueprint(Base):
    __tablename__ = "extracted_blueprints"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("question_paper_templates.id", ondelete="CASCADE"), nullable=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id"), nullable=True)
    
    raw_extracted_text = Column(Text, nullable=True)
    canonical_blueprint_json = Column(Text, nullable=False) # Canonical JSON conforming to Section B4
    confidence_scores_json = Column(Text, nullable=True) # Per-field extraction confidence scores
    extraction_status = Column(String(50), default="extracted", nullable=False) # "extracted", "needs_verification", "faculty_corrected", "confirmed", "locked"
    
    validation_errors_json = Column(Text, nullable=True) # JSON list of blocking validation errors
    validation_warnings_json = Column(Text, nullable=True) # JSON list of non-blocking warnings
    
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    template = relationship("QuestionPaperTemplate", back_populates="blueprints")
    syllabus = relationship("Syllabus")
    verified_by = relationship("User", foreign_keys=[verified_by_id])
    sections = relationship("BlueprintSectionModel", back_populates="blueprint", cascade="all, delete-orphan")


class BlueprintSectionModel(Base):
    __tablename__ = "blueprint_sections"

    id = Column(Integer, primary_key=True, index=True)
    blueprint_id = Column(Integer, ForeignKey("extracted_blueprints.id", ondelete="CASCADE"), nullable=False)
    section_name = Column(String(100), nullable=False) # e.g. "Part A", "Part B", "Part C"
    answer_rule = Column(String(255), nullable=True) # e.g. "Answer all questions", "Answer either (a) or (b)"
    start_question_number = Column(Integer, default=1)
    question_count = Column(Integer, default=5, nullable=False)
    marks_per_question = Column(Integer, default=2, nullable=False)
    section_total = Column(Integer, default=10, nullable=False)
    or_choice = Column(Boolean, default=False, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)

    blueprint = relationship("ExtractedBlueprint", back_populates="sections")
    slots = relationship("BlueprintQuestionSlotModel", back_populates="section", cascade="all, delete-orphan")


class BlueprintQuestionSlotModel(Base):
    __tablename__ = "blueprint_question_slots"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("blueprint_sections.id", ondelete="CASCADE"), nullable=False)
    question_number = Column(String(50), nullable=False) # e.g. "1", "11(a)", "11(b)"
    or_pair_id = Column(String(50), nullable=True) # links 11(a) and 11(b)
    unit_number = Column(Integer, default=1)
    co_level = Column(String(50), default="CO1")
    bloom_level = Column(String(50), default="L2")
    marks = Column(Integer, default=2, nullable=False)
    
    # Question Types
    allowed_types_json = Column(Text, nullable=True) # JSON list e.g. ["coding", "descriptive"]
    required_types_json = Column(Text, nullable=True) # JSON list of must-have types
    preferred_type = Column(String(50), nullable=True)
    combine_types = Column(Boolean, default=False, nullable=False) # True if multiple types should form one coherent question
    
    confidence_score = Column(Float, default=1.0)
    needs_review = Column(Boolean, default=False)
    remarks = Column(Text, nullable=True)

    section = relationship("BlueprintSectionModel", back_populates="slots")
    slot_types = relationship("SlotQuestionTypeModel", back_populates="slot", cascade="all, delete-orphan")


class SlotQuestionTypeModel(Base):
    __tablename__ = "slot_question_types"

    id = Column(Integer, primary_key=True, index=True)
    slot_id = Column(Integer, ForeignKey("blueprint_question_slots.id", ondelete="CASCADE"), nullable=False)
    question_type_name = Column(String(100), nullable=False) # e.g. "coding", "descriptive", "mcq_single"
    is_required = Column(Boolean, default=True)
    weightage_marks = Column(Integer, nullable=True)

    slot = relationship("BlueprintQuestionSlotModel", back_populates="slot_types")


# =============================================================================
# MODULE A & E: LAWFUL PDF ACQUISITION, DOCUMENT CHUNKS & AUDIT TRAIL
# =============================================================================

class ResourceRecord(Base):
    __tablename__ = "resource_records"

    id = Column(Integer, primary_key=True, index=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id"), nullable=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True)
    
    resource_type = Column(String(100), default="Open Educational Resource", nullable=False)
    title = Column(String(500), nullable=False)
    authors = Column(String(500), nullable=True)
    publisher = Column(String(255), nullable=True)
    edition = Column(String(100), nullable=True)
    year = Column(String(50), nullable=True)
    isbn = Column(String(50), nullable=True)
    doi = Column(String(100), nullable=True)
    
    # Lawful Access Details
    source_repository = Column(String(100), nullable=False) # e.g. "Internet Archive", "DOAB", "OpenStax", "OER Commons"
    source_url = Column(Text, nullable=False)
    landing_page_url = Column(Text, nullable=True)
    
    # 10-Tier Lawful Access Classification:
    # 1. 'Open-access PDF'
    # 2. 'Public-domain PDF'
    # 3. 'Institutionally licensed'
    # 4. 'Faculty uploaded'
    # 5. 'Preview only'
    # 6. 'Catalogue record'
    # 7. 'Borrowing link'
    # 8. 'Purchase link'
    # 9. 'Restricted access'
    # 10. 'Unknown rights status'
    access_type = Column(String(100), nullable=False, default="Unknown rights status")
    licence = Column(String(100), nullable=True) # e.g. "CC-BY", "CC-BY-SA", "Public Domain", "Open Access"
    rights_statement = Column(Text, nullable=True)
    rights_verified = Column(Boolean, default=False, nullable=False)
    rights_verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rights_verified_at = Column(DateTime, nullable=True)
    faculty_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    course = Column(String(255), nullable=True)
    
    # Status lifecycle:
    # "discovered" -> "rights_verification" -> "authorized" -> "downloading" ->
    # "stored" -> "extracting" -> "indexed" -> "syllabus_aligned" -> "faculty_approved"
    status = Column(String(50), default="discovered", nullable=False)
    
    stored_document_id = Column(Integer, ForeignKey("stored_documents.id", ondelete="SET NULL", use_alter=True), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    syllabus = relationship("Syllabus")
    book = relationship("Book")
    rights_verified_by = relationship("User", foreign_keys=[rights_verified_by_id])
    faculty_owner = relationship("User", foreign_keys=[faculty_owner_id])
    stored_document = relationship("StoredDocument", foreign_keys=[stored_document_id], post_update=True)
    verification_logs = relationship("RightsVerificationLog", back_populates="resource_record", cascade="all, delete-orphan")


class StoredDocument(Base):
    __tablename__ = "stored_documents"

    id = Column(Integer, primary_key=True, index=True)
    resource_record_id = Column(Integer, ForeignKey("resource_records.id", ondelete="CASCADE"), nullable=True)
    
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False) # Relative or absolute filesystem path
    mime_type = Column(String(100), default="application/pdf", nullable=False)
    file_size = Column(Integer, nullable=False)
    sha256_checksum = Column(String(64), nullable=False, index=True)
    downloaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    acquisition_method = Column(String(50), default="lawful_download") # "lawful_download", "faculty_upload"
    
    extraction_status = Column(String(50), default="pending", nullable=False) # "pending", "extracting", "completed", "failed"
    ocr_required = Column(Boolean, default=False, nullable=False)
    page_count = Column(Integer, default=0)
    language = Column(String(20), default="en")
    version = Column(Integer, default=1)
    active = Column(Boolean, default=True)
    retention_status = Column(String(50), default="retained") # "retained", "archived", "purged"

    resource_record = relationship("ResourceRecord", foreign_keys=[resource_record_id])
    chunks = relationship("DocumentChunkModel", back_populates="stored_document", cascade="all, delete-orphan")
    audit_logs = relationship("DownloadAuditLog", back_populates="stored_document", cascade="all, delete-orphan")


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    stored_document_id = Column(Integer, ForeignKey("stored_documents.id", ondelete="CASCADE"), nullable=False)
    
    page_number = Column(Integer, nullable=False)
    chapter = Column(String(255), nullable=True)
    heading = Column(String(255), nullable=True)
    text = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    embedding_reference = Column(String(255), nullable=True) # Vector ID or placeholder hash
    
    # Curriculum Alignment
    course = Column(String(255), nullable=True)
    unit_number = Column(Integer, nullable=True)
    topic = Column(String(255), nullable=True)
    co_level = Column(String(50), nullable=True)
    alignment_score = Column(Float, default=0.0)
    approved_for_generation = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    stored_document = relationship("StoredDocument", back_populates="chunks")


class RightsVerificationLog(Base):
    __tablename__ = "rights_verification_logs"

    id = Column(Integer, primary_key=True, index=True)
    resource_record_id = Column(Integer, ForeignKey("resource_records.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    action = Column(String(50), nullable=False) # "verify_passed", "verify_failed", "faculty_override", "rights_audited"
    rights_status = Column(String(100), nullable=False)
    licence_found = Column(String(100), nullable=True)
    evidence_notes = Column(Text, nullable=True)
    faculty_override_justification = Column(Text, nullable=True)
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    resource_record = relationship("ResourceRecord", back_populates="verification_logs")
    user = relationship("User")


class DownloadAuditLog(Base):
    __tablename__ = "download_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    stored_document_id = Column(Integer, ForeignKey("stored_documents.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    source_url = Column(Text, nullable=False)
    final_url = Column(Text, nullable=True)
    http_status_code = Column(Integer, nullable=True)
    sha256_checksum = Column(String(64), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    rights_status = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False) # "success", "blocked_unauthorized", "failed_verification", "duplicate_skipped"
    failure_reason = Column(Text, nullable=True)
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    stored_document = relationship("StoredDocument", back_populates="audit_logs")
    user = relationship("User")
