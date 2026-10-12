from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, model_validator
import datetime

class McqOptionSchema(BaseModel):
    label: str
    text: str
    is_correct: bool
    explanation: Optional[str] = None

class QuestionBase(BaseModel):
    section_name: str
    question_number: str
    question_text: str
    marks: int
    co_level: str
    bloom_level: str
    is_validated: bool = False
    faculty_notes: Optional[str] = None
    source_topic: Optional[str] = None
    alternative_options: Optional[str] = None
    status: str = "draft"
    difficulty: Optional[str] = "Medium"
    unit_number: Optional[str] = None
    source_filename: Optional[str] = None
    source_page_or_slide: Optional[str] = None
    supporting_passage: Optional[str] = None
    alignment_confidence: Optional[float] = None
    generation_method: Optional[str] = "rag_grounded"
    model_answer: Optional[str] = None
    marking_scheme: Optional[str] = None
    stepwise_solution: Optional[str] = None
    rubric_json: Optional[str] = None
    # Assessment, adaptive & question-type fields
    question_type: Optional[str] = "short_answer"
    options_json: Optional[str] = None
    correct_answer_json: Optional[str] = None
    explanation: Optional[str] = None

    # OR-choice Pair Equivalence
    or_pair_id: Optional[str] = None
    or_equivalence_notes: Optional[str] = None
    or_equivalence_score: Optional[float] = 92.0

    # Validation and Quality Scores
    grammar_score: Optional[float] = 95.0
    quality_score: Optional[float] = 90.0
    validation_details_json: Optional[str] = None
    distractor_explanations_json: Optional[str] = None
    needs_review_reasons: Optional[str] = None

    reviewer_id: Optional[int] = None
    reviewer_remarks: Optional[str] = None

class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    marks: Optional[int] = None
    co_level: Optional[str] = None
    bloom_level: Optional[str] = None
    is_validated: Optional[bool] = None
    faculty_notes: Optional[str] = None
    status: Optional[str] = None
    reviewer_remarks: Optional[str] = None
    model_answer: Optional[str] = None
    marking_scheme: Optional[str] = None
    question_type: Optional[str] = None
    options_json: Optional[str] = None
    correct_answer_json: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None

class QuestionReviewRequest(BaseModel):
    action: str # "approve", "reject", "edit"
    reviewer_remarks: Optional[str] = None
    updated_question_text: Optional[str] = None
    updated_marks: Optional[int] = None
    updated_model_answer: Optional[str] = None
    updated_marking_scheme: Optional[str] = None
    updated_question_type: Optional[str] = None
    updated_bloom_level: Optional[str] = None
    updated_difficulty: Optional[str] = None
    updated_topic: Optional[str] = None
    updated_co_level: Optional[str] = None
    # For MCQ editing
    updated_options: Optional[List[Dict[str, Any]]] = None
    updated_correct_answer: Optional[Any] = None
    updated_explanation: Optional[str] = None

class QuestionRegenerateRequest(BaseModel):
    directive: Optional[str] = "standard" # "simplify_wording", "increase_difficulty", "decrease_difficulty", "change_bloom", "change_topic", "change_source", "convert_to_mcq", "convert_to_descriptive", "make_programming", "correct_grammar_only"
    target_bloom_level: Optional[str] = None
    target_difficulty: Optional[str] = None
    target_topic: Optional[str] = None
    target_question_type: Optional[str] = None
    target_slide_or_page: Optional[str] = None
    faculty_prompt: Optional[str] = None

class QuestionResponse(QuestionBase):
    id: int
    question_paper_id: int
    options: Optional[List[McqOptionSchema]] = None
    correct_answer: Optional[Any] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_canonical_mcq(cls, data: Any) -> Any:
        import json, re

        def get_v(field, default=None):
            if isinstance(data, dict):
                return data.get(field, default)
            return getattr(data, field, default)

        opts_json = get_v("options_json")
        correct_ans = get_v("correct_answer_json")
        distractors_json = get_v("distractor_explanations_json")

        distractors = {}
        if distractors_json:
            try:
                distractors = json.loads(distractors_json) if isinstance(distractors_json, str) else distractors_json
            except Exception:
                distractors = {}

        parsed_opts = None
        if opts_json:
            try:
                raw_opts = json.loads(opts_json) if isinstance(opts_json, str) else opts_json
                if isinstance(raw_opts, list):
                    parsed_opts = []
                    for idx, item in enumerate(raw_opts):
                        lbl = chr(65 + idx)
                        if isinstance(item, dict):
                            l = (item.get("label") or lbl).strip().upper()
                            t = str(item.get("text", "")).strip()
                            corr = item.get("is_correct")
                            if corr is None:
                                corr = (l == str(correct_ans).strip().upper())
                            else:
                                corr = (corr is True or corr == 1 or corr == "1" or str(corr).lower() == "true")
                            exp = item.get("explanation") or distractors.get(l)
                            parsed_opts.append({"label": l, "text": t, "is_correct": corr, "explanation": exp})
                        else:
                            opt_str = str(item).strip()
                            t = re.sub(r'^[A-E][\)\.]\s*', '', opt_str).strip()
                            corr = (lbl == str(correct_ans).strip().upper())
                            exp = distractors.get(lbl)
                            parsed_opts.append({"label": lbl, "text": t, "is_correct": corr, "explanation": exp})
            except Exception:
                parsed_opts = None

        if isinstance(data, dict):
            res = dict(data)
            if parsed_opts is not None:
                res["options"] = parsed_opts
            if correct_ans is not None and "correct_answer" not in res:
                res["correct_answer"] = correct_ans
            return res
        else:
            cols = [
                "id", "question_paper_id", "section_name", "question_number", "question_text",
                "marks", "co_level", "bloom_level", "is_validated", "faculty_notes", "source_topic",
                "alternative_options", "status", "difficulty", "unit_number", "source_filename",
                "source_page_or_slide", "supporting_passage", "alignment_confidence",
                "generation_method", "model_answer", "marking_scheme", "stepwise_solution",
                "rubric_json", "question_type", "options_json", "correct_answer_json",
                "explanation", "or_pair_id", "or_equivalence_notes", "or_equivalence_score",
                "grammar_score", "quality_score", "validation_details_json",
                "distractor_explanations_json", "needs_review_reasons", "reviewer_id",
                "reviewer_remarks", "created_at", "updated_at"
            ]
            d = {}
            for col in cols:
                d[col] = getattr(data, col, None)
            d["options"] = parsed_opts
            d["correct_answer"] = correct_ans
            return d

class BlueprintSection(BaseModel):
    name: str
    instructions: str
    questions_count: int
    marks_per_question: int
    co_distribution: List[str]
    bloom_distribution: List[str]
    has_internal_choice: Optional[bool] = False
    question_type: Optional[str] = "short_answer"
    mcq_config: Optional[Dict[str, Any]] = None
    unit_distribution: Optional[List[str]] = None
    difficulty_distribution: Optional[List[str]] = None
    questions: Optional[List[Dict[str, Any]]] = None

class BlueprintGenerateRequest(BaseModel):
    syllabus_id: int
    template_id: Optional[int] = None
    institution_name: str = "AARUPADAI VEEDU INSTITUTE OF TECHNOLOGY"
    course_name: str
    course_code: str
    exam_name: str = "Semester End Examination"
    academic_year: str = "2024-2025"
    semester: str = "IV Semester"
    department: str = "Computer Science & Engineering"
    programme: Optional[str] = "B.E. Computer Science & Engineering"
    regulation: Optional[str] = "2021 (Autonomous)"
    exam_date: Optional[str] = None
    duration: str = "3 Hours"
    max_marks: int = 100
    instructions: Optional[str] = "1. Answer ALL questions in Part A.\n2. Answer either (a) or (b) from each question in Part B."
    sections: List[BlueprintSection]
    generation_mode: Optional[str] = "syllabus_ppt"

class QuestionPaperResponse(BaseModel):
    id: int
    faculty_id: Optional[int] = None
    syllabus_id: Optional[int] = None
    template_id: Optional[int] = None
    title: str
    institution_name: str
    course_name: str
    course_code: str
    exam_name: str
    academic_year: str
    semester: str
    department: str
    programme: Optional[str] = None
    regulation: Optional[str] = None
    exam_date: Optional[str] = None
    duration: str
    max_marks: int
    instructions: Optional[str] = None
    generation_mode: Optional[str] = "syllabus_ppt"
    coverage_matrix_json: Optional[str] = None
    status: str
    template_filename: Optional[str] = None
    questions: List[QuestionResponse] = []
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CourseOutcomeModel(BaseModel):
    code: str
    description: str
    bloom_level: str
    unit_title: Optional[str] = None

class ContentFileResponse(BaseModel):
    id: int
    syllabus_id: Optional[int] = None
    faculty_id: Optional[int] = None
    original_filename: str
    stored_filename: str
    file_type: str
    file_size_bytes: int
    slide_or_page_count: int
    extraction_status: Optional[str] = "extracted"
    extraction_warnings: Optional[str] = None
    created_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CoverageMatrixRequest(BaseModel):
    syllabus_id: int
    generation_mode: Optional[str] = "syllabus_ppt"
    blueprint: Optional[Dict[str, Any]] = None

class ProvenanceResponse(BaseModel):
    question_id: int
    source_filename: Optional[str] = None
    source_page_or_slide: Optional[str] = None
    supporting_passage: Optional[str] = None
    alignment_confidence: Optional[float] = None
    generation_method: Optional[str] = None
    source_topic: Optional[str] = None
    unit_number: Optional[str] = None
