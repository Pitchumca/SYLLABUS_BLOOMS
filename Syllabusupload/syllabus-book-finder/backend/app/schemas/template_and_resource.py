from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
import datetime

# =============================================================================
# CANONICAL BLUEPRINT SCHEMA (Adheres strictly to Specification B4)
# =============================================================================

class CanonicalQuestionSlot(BaseModel):
    question_number: str # e.g. "1", "11(a)", "11(b)"
    or_pair_id: Optional[str] = None # e.g. "or_pair_11"
    question_types: List[str] = ["short_answer"] # e.g. ["mcq_single"], ["coding", "descriptive"]
    unit: int = 1
    co: str = "CO1"
    bloom_level: str = "L2"
    marks: int = 2
    preferred_type: Optional[str] = None
    combine_types: Optional[bool] = False
    confidence_score: Optional[float] = 1.0
    needs_review: Optional[bool] = False
    remarks: Optional[str] = None

class CanonicalSection(BaseModel):
    section_name: str # "Part A", "Part B", "Part C"
    answer_rule: str = "Answer all questions" # "Answer either (a) or (b)"
    start_question_number: Optional[int] = 1
    question_count: int = 5
    marks_per_question: int = 2
    section_total: int = 10
    or_choice: bool = False
    questions: List[CanonicalQuestionSlot] = []

class CanonicalBlueprintSchema(BaseModel):
    template_name: str = "AVIT Semester Examination Template"
    institution: str = "Aarupadai Veedu Institute of Technology"
    programme: Optional[str] = "B.E. Computer Science and Engineering"
    department: Optional[str] = "Computer Science & Engineering"
    course_code: str = "35021P28"
    course_title: str = "R Programming"
    exam_name: str = "Internal Assessment"
    exam_type: Optional[str] = "Internal Assessment" # "Internal Assessment", "Semester End"
    duration_minutes: int = 90
    maximum_marks: int = 50
    instructions: List[str] = []
    sections: List[CanonicalSection] = []

# =============================================================================
# CONFIDENCE & VALIDATION SCHEMAS (Specifications B5 & B6)
# =============================================================================

class FieldConfidenceScores(BaseModel):
    institution: float = 1.0
    course_information: float = 1.0
    section_names: float = 1.0
    question_numbering: float = 1.0
    marks: float = 1.0
    course_outcomes: float = 1.0
    bloom_levels: float = 1.0
    or_choices: float = 1.0
    total_marks: float = 1.0
    instructions: float = 1.0
    overall: float = 1.0

class BlueprintValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    calculated_total_marks: int
    target_maximum_marks: int
    reconciled: bool

# =============================================================================
# TEMPLATE UPLOAD & LIBRARY SCHEMAS
# =============================================================================

class TemplateExtractionResponse(BaseModel):
    blueprint: CanonicalBlueprintSchema
    confidence_scores: FieldConfidenceScores
    validation: BlueprintValidationResult
    extraction_status: str = "extracted" # "extracted", "needs_verification", "faculty_corrected", "confirmed"
    file_format: str # "docx", "pdf", "scanned_pdf", "image", "xlsx"
    original_filename: str
    stored_filename: str
    raw_preview_text: Optional[str] = None

class TemplateSaveRequest(BaseModel):
    template_name: str
    institution: str = "Aarupadai Veedu Institute of Technology"
    department: Optional[str] = "Computer Science & Engineering"
    programme: Optional[str] = "B.E. Computer Science and Engineering"
    regulation: Optional[str] = "2021 (Autonomous)"
    exam_name: Optional[str] = "Semester End Examination"
    exam_type: Optional[str] = "Semester End"
    maximum_marks: int = 100
    duration_minutes: int = 180
    academic_year: Optional[str] = "2024-2025"
    course_code: Optional[str] = None
    course_title: Optional[str] = None
    blueprint: CanonicalBlueprintSchema
    original_filename: Optional[str] = None
    stored_filename: Optional[str] = None
    file_format: Optional[str] = "docx"
    is_department_default: Optional[bool] = False
    is_course_default: Optional[bool] = False

class TemplateUpdateRequest(BaseModel):
    template_name: Optional[str] = None
    institution: Optional[str] = None
    department: Optional[str] = None
    programme: Optional[str] = None
    regulation: Optional[str] = None
    exam_name: Optional[str] = None
    exam_type: Optional[str] = None
    maximum_marks: Optional[int] = None
    duration_minutes: Optional[int] = None
    academic_year: Optional[str] = None
    blueprint: Optional[CanonicalBlueprintSchema] = None
    change_summary: Optional[str] = "Updated blueprint parameters"
    is_active: Optional[bool] = None
    is_department_default: Optional[bool] = None
    is_course_default: Optional[bool] = None

class TemplateListItem(BaseModel):
    id: int
    name: str
    institution: str
    department: Optional[str] = None
    programme: Optional[str] = None
    regulation: Optional[str] = None
    exam_name: Optional[str] = None
    exam_type: Optional[str] = None
    max_marks: int
    duration_minutes: int
    academic_year: Optional[str] = None
    course_code: Optional[str] = None
    course_title: Optional[str] = None
    version: int
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    is_active: bool
    is_department_default: bool
    is_course_default: bool
    file_format: Optional[str] = None
    original_filename: Optional[str] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TemplateDetailResponse(TemplateListItem):
    blueprint: CanonicalBlueprintSchema
    validation: Optional[BlueprintValidationResult] = None
    extraction_status: Optional[str] = "confirmed"

# =============================================================================
# MODULE A: LAWFUL PDF ACQUISITION & DOCUMENT CHUNKING SCHEMAS
# =============================================================================

class DocumentChunkSchema(BaseModel):
    id: int
    stored_document_id: int
    page_number: int
    chapter: Optional[str] = None
    heading: Optional[str] = None
    text: str
    token_count: int = 0
    unit_number: Optional[int] = None
    topic: Optional[str] = None
    co_level: Optional[str] = None
    alignment_score: float = 0.0
    approved_for_generation: bool = False

    model_config = ConfigDict(from_attributes=True)

class StoredDocumentSchema(BaseModel):
    id: int
    resource_record_id: int
    original_filename: str
    mime_type: str
    file_size: int
    sha256_checksum: str
    downloaded_at: Optional[datetime.datetime] = None
    acquisition_method: str
    extraction_status: str
    ocr_required: bool
    page_count: int
    language: str
    version: int
    active: bool
    chunks_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

class ResourceRecordResponse(BaseModel):
    id: int
    syllabus_id: Optional[int] = None
    book_id: Optional[int] = None
    resource_type: str
    title: str
    authors: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[str] = None
    year: Optional[str] = None
    isbn: Optional[str] = None
    doi: Optional[str] = None
    source_repository: str
    source_url: str
    landing_page_url: Optional[str] = None
    access_type: str
    licence: Optional[str] = None
    rights_statement: Optional[str] = None
    rights_verified: bool
    rights_verified_by_id: Optional[int] = None
    rights_verified_at: Optional[datetime.datetime] = None
    status: str
    stored_document: Optional[StoredDocumentSchema] = None
    alignment_percentage: Optional[float] = 0.0
    approved_units: Optional[List[int]] = []
    created_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

class LawfulAcquireRequest(BaseModel):
    source_url: str
    title: str
    authors: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[str] = None
    year: Optional[str] = None
    isbn: Optional[str] = None
    doi: Optional[str] = None
    licence: Optional[str] = None
    rights_statement: Optional[str] = None
    source_repository: str
    syllabus_id: Optional[int] = None
    book_id: Optional[int] = None
    faculty_override: Optional[bool] = False
    override_justification: Optional[str] = None

class RightsVerificationCheckResponse(BaseModel):
    is_eligible: bool
    access_type: str # One of the 10 tiers
    licence: Optional[str] = None
    source_repository: str
    domain: str
    reasons: List[str] = []
    can_download_and_index: bool
    warning: Optional[str] = None
