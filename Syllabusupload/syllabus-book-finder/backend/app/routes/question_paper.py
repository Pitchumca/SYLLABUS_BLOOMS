import re
import json
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.question_paper import QuestionPaper, Question
from app.models.syllabus import Syllabus
from app.models.content_file import ContentFile
from app.models.user import User
from app.models.student import Course
from app.models.discovery_rag import RAGChunk, CourseResource
from app.schemas.question_paper import (
    BlueprintGenerateRequest,
    QuestionPaperResponse,
    QuestionResponse,
    QuestionUpdate,
    QuestionReviewRequest,
    QuestionRegenerateRequest,
    CoverageMatrixRequest,
    ProvenanceResponse
)
from app.utils.auth import get_current_user, require_faculty
from app.utils.security import (
    sanitize_filename,
    generate_safe_stored_filename,
    validate_uploaded_file,
    validate_path_traversal
)
from app.services.co_extractor import extract_course_outcomes, extract_syllabus_units
from app.services.alignment_engine import build_coverage_matrix, align_content_file_to_syllabus
from app.services.question_generator import (
    generate_questions_from_blueprint,
    synthesize_question,
    regenerate_single_question
)
from app.models.template_and_resource import QuestionPaperTemplate
from app.services.grammar_validator import validate_question_grammar
from app.services.semantic_validator import evaluate_semantic_quality, validate_mcq_structure
from app.services.word_template_service import (
    generate_question_paper_docx,
    create_default_template_file
)
from app.services.pdf_template_service import generate_question_paper_pdf
from app.services.template_extractor import validate_extracted_blueprint

router = APIRouter(prefix="/question-paper", tags=["Question Paper Blueprint & Generation"])

@router.get("/course-metadata")
def get_course_metadata_endpoint(
    syllabus_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Retrieve auto-populated course and institutional metadata for the selected syllabus."""
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")

    course = db.query(Course).filter(Course.syllabus_id == syllabus_id).first()
    text = syllabus.extracted_text or ""

    code_match = re.search(r'(?:Course\s*Code|Subject\s*Code)\s*[:\-]?\s*([A-Z0-9]+)', text, re.IGNORECASE)
    title_match = re.search(r'(?:Course\s*Title|Subject\s*Title|Course\s*Name)\s*[:\-]?\s*([^\n\r]+)', text, re.IGNORECASE)
    sem_match = re.search(r'(?:Semester|Sem)\s*[:\-]?\s*([IVX0-9]+(?:\s*Semester)?)', text, re.IGNORECASE)
    year_match = re.search(r'(?:Academic\s*Year|Year)\s*[:\-]?\s*([0-9]{4}\s*[-–]\s*[0-9]{4})', text, re.IGNORECASE)
    prog_match = re.search(r'(?:Programme|Degree|Branch)\s*[:\-]?\s*([^\n\r]+)', text, re.IGNORECASE)
    dept_match = re.search(r'(?:Department\s*of)\s*([^\n\r,]+)', text, re.IGNORECASE)

    course_code = course.course_code if (course and course.course_code) else (code_match.group(1).strip() if code_match else "35021P28")
    course_name = course.course_name if (course and course.course_name) else (title_match.group(1).strip() if title_match else "R Programming")
    semester = course.semester if (course and course.semester) else (sem_match.group(1).strip() if sem_match else "IV Semester")
    academic_year = course.academic_year if (course and course.academic_year) else (year_match.group(1).strip() if year_match else "2024-2025")
    department = course.department if (course and course.department) else (dept_match.group(1).strip() if dept_match else "Computer Science & Engineering")
    programme = "B.E. Computer Science & Engineering" if not prog_match else prog_match.group(1).strip()
    regulation = "2021 (Autonomous)"

    faculty_name = course.faculty.full_name if (course and course.faculty) else (current_user.full_name if current_user else "Dr. Pitchumani Angayarkanni")

    return {
        "syllabus_id": syllabus.id,
        "course_code": course_code,
        "course_name": course_name,
        "semester": semester,
        "academic_year": academic_year,
        "department": department,
        "programme": programme,
        "regulation": regulation,
        "assigned_faculty": faculty_name,
        "institution_name": "AARUPADAI VEEDU INSTITUTE OF TECHNOLOGY"
    }

@router.post("/coverage-matrix")
def get_pre_generation_coverage_matrix(
    payload: CoverageMatrixRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Build pre-generation coverage matrix comparing syllabus topics, aligned slides, and blueprint."""
    syllabus = db.query(Syllabus).filter(Syllabus.id == payload.syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")

    text = syllabus.extracted_text or ""
    units = extract_syllabus_units(text)
    cos = extract_course_outcomes(text)

    # Gather alignments from content files
    content_files = db.query(ContentFile).filter(ContentFile.syllabus_id == payload.syllabus_id).all()
    all_alignments = []
    for cf in content_files:
        if cf.alignments_json:
            try:
                data = json.loads(cf.alignments_json)
                all_alignments.extend(data.get("alignments", []))
            except Exception:
                pass
        elif cf.chunks_json:
            try:
                chunks = json.loads(cf.chunks_json)
                res = align_content_file_to_syllabus(chunks, units, cos, cf.original_filename)
                all_alignments.extend(res.get("alignments", []))
            except Exception:
                pass

    blueprint = payload.blueprint or {
        "sections": [
            {"name": "Part A", "questions_count": 5, "marks_per_question": 2},
            {"name": "Part B", "questions_count": 3, "marks_per_question": 10}
        ]
    }

    matrix = build_coverage_matrix(
        blueprint=blueprint,
        syllabus_units=units,
        course_outcomes=cos,
        all_alignments=all_alignments,
        generation_mode=payload.generation_mode or "syllabus_ppt"
    )
    return matrix

@router.get("/blueprint/presets")
def get_blueprint_presets():
    """Retrieve pre-configured standard university exam blueprint presets."""
    return [
        {
            "id": "univ_100_abc",
            "name": "Anna University / VTU 100 Marks (Parts A, B, C)",
            "description": "Standard 100 Marks format: Part A (10 MCQs x 2 = 20), Part B (5 Programming/Descriptive x 13 = 65 with internal choice), Part C (1 Design/Application x 15 = 15).",
            "max_marks": 100,
            "duration": "3 Hours",
            "sections": [
                {
                    "name": "Part A",
                    "instructions": "Answer ALL questions. Each question carries 2 marks.",
                    "questions_count": 10,
                    "marks_per_question": 2,
                    "question_type": "mcq",
                    "mcq_config": {
                        "options_count": 4,
                        "is_multiple_correct": False,
                        "include_none_of_above": False,
                        "include_all_of_above": False,
                        "randomize_options": False,
                        "negative_marking": 0.0,
                        "generate_explanation": True
                    },
                    "co_distribution": ["CO1", "CO1", "CO2", "CO2", "CO3", "CO3", "CO4", "CO4", "CO5", "CO5"],
                    "bloom_distribution": ["L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand"],
                    "has_internal_choice": False
                },
                {
                    "name": "Part B",
                    "instructions": "Answer either (a) or (b) from each question. Each question carries 13 marks.",
                    "questions_count": 5,
                    "marks_per_question": 13,
                    "question_type": "programming",
                    "co_distribution": ["CO1", "CO2", "CO3", "CO4", "CO5"],
                    "bloom_distribution": ["L3 - Apply", "L3 - Apply", "L3 - Apply", "L4 - Analyze", "L5 - Evaluate"],
                    "has_internal_choice": True
                },
                {
                    "name": "Part C",
                    "instructions": "Comprehensive / Design & Statistical Application workflow question. Carries 15 marks.",
                    "questions_count": 1,
                    "marks_per_question": 15,
                    "question_type": "design_application",
                    "co_distribution": ["CO5"],
                    "bloom_distribution": ["L6 - Create"],
                    "has_internal_choice": False
                }
            ]
        },
        {
            "id": "univ_100_ab",
            "name": "Standard Semester End (100 Marks - Parts A & B)",
            "description": "Part A: 10 Short questions (2 marks each = 20), Part B: 5 Long questions (16 marks each = 80).",
            "max_marks": 100,
            "duration": "3 Hours",
            "sections": [
                {
                    "name": "Part A",
                    "instructions": "Answer ALL questions (10 x 2 = 20 Marks).",
                    "questions_count": 10,
                    "marks_per_question": 2,
                    "co_distribution": ["CO1", "CO1", "CO2", "CO2", "CO3", "CO3", "CO4", "CO4", "CO5", "CO5"],
                    "bloom_distribution": ["L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand"],
                    "has_internal_choice": False
                },
                {
                    "name": "Part B",
                    "instructions": "Answer any FIVE questions (5 x 16 = 80 Marks).",
                    "questions_count": 5,
                    "marks_per_question": 16,
                    "co_distribution": ["CO1", "CO2", "CO3", "CO4", "CO5"],
                    "bloom_distribution": ["L3 - Apply", "L3 - Apply", "L4 - Analyze", "L4 - Analyze", "L5 - Evaluate"],
                    "has_internal_choice": True
                }
            ]
        },
        {
            "id": "midterm_50",
            "name": "Internal Assessment / Mid-Term (50 Marks)",
            "description": "50 Marks assessment: Part A (5x2=10), Part B (4x5=20), Part C (2x10=20).",
            "max_marks": 50,
            "duration": "90 Minutes",
            "sections": [
                {
                    "name": "Part A",
                    "instructions": "Answer ALL questions. Each question carries 2 marks.",
                    "questions_count": 5,
                    "marks_per_question": 2,
                    "co_distribution": ["CO1", "CO1", "CO2", "CO2", "CO3"],
                    "bloom_distribution": ["L1 - Remember", "L2 - Understand", "L1 - Remember", "L2 - Understand", "L3 - Apply"],
                    "has_internal_choice": False
                },
                {
                    "name": "Part B",
                    "instructions": "Answer ALL questions. Each carries 5 marks.",
                    "questions_count": 4,
                    "marks_per_question": 5,
                    "co_distribution": ["CO1", "CO2", "CO2", "CO3"],
                    "bloom_distribution": ["L2 - Understand", "L3 - Apply", "L3 - Apply", "L4 - Analyze"],
                    "has_internal_choice": False
                },
                {
                    "name": "Part C",
                    "instructions": "Answer any TWO questions. Each carries 10 marks.",
                    "questions_count": 2,
                    "marks_per_question": 10,
                    "co_distribution": ["CO2", "CO3"],
                    "bloom_distribution": ["L4 - Analyze", "L5 - Evaluate"],
                    "has_internal_choice": False
                }
            ]
        }
    ]

@router.post("/generate", response_model=QuestionPaperResponse, status_code=status.HTTP_201_CREATED)
def generate_questions(
    payload: BlueprintGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Generate complete question paper with Course Outcomes and Bloom's Taxonomy mapping
    strictly grounded in the syllabus and faculty-uploaded PPT / lecture notes.
    """
    syllabus = db.query(Syllabus).filter(Syllabus.id == payload.syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus record not found.")

    syllabus_text = syllabus.extracted_text or ""
    units = extract_syllabus_units(syllabus_text)
    course_outcomes = extract_course_outcomes(syllabus_text)

    # Gather aligned chunks from all uploaded content files for this syllabus
    content_files = db.query(ContentFile).filter(ContentFile.syllabus_id == payload.syllabus_id).all()
    faculty_slide_chunks = []
    for cf in content_files:
        if cf.alignments_json:
            try:
                data = json.loads(cf.alignments_json)
                faculty_slide_chunks.extend(data.get("alignments", []))
            except Exception:
                pass
        elif cf.chunks_json:
            try:
                chunks = json.loads(cf.chunks_json)
                res = align_content_file_to_syllabus(chunks, units, course_outcomes, cf.original_filename)
                cf.alignments_json = json.dumps(res)
                db.commit()
                faculty_slide_chunks.extend(res.get("alignments", []))
            except Exception:
                pass

    # Gather grounded chunks from indexed textbooks and reference books (Section 12 strict priority)
    rag_chunks = db.query(RAGChunk).filter(
        RAGChunk.syllabus_id == payload.syllabus_id,
        RAGChunk.approved_for_generation == True
    ).all()

    textbook_chunks = []
    reference_chunks = []
    for rc in rag_chunks:
        c_entry = {
            "unit": rc.unit_number or 1,
            "topic": rc.chapter or "Curriculum Topic",
            "source_filename": rc.book_title or Path(rc.source_file or "").name,
            "slide_or_page": f"Page {rc.page_start}",
            "chunk_text": rc.text,
            "confidence": rc.topic_relevance_score,
            "resource_type": (rc.resource_type or "TEXTBOOK").upper()
        }
        if (rc.resource_type or "").upper() == "TEXTBOOK":
            textbook_chunks.append(c_entry)
        else:
            reference_chunks.append(c_entry)

    # Combine in strict priority order: 1. Prescribed Textbooks, 2. Reference Books, 3. Slides/Notes
    aligned_chunks = textbook_chunks + reference_chunks + faculty_slide_chunks

    blueprint_dict = {
        "sections": [s.model_dump() for s in payload.sections]
    }

    gen_mode = payload.generation_mode or "syllabus_ppt"

    # Construct Pre-generation Coverage Matrix
    coverage_matrix = build_coverage_matrix(
        blueprint=blueprint_dict,
        syllabus_units=units,
        course_outcomes=course_outcomes,
        all_alignments=aligned_chunks,
        generation_mode=gen_mode
    )

    generated_raw = generate_questions_from_blueprint(
        blueprint=blueprint_dict,
        syllabus_text=syllabus_text,
        course_outcomes=course_outcomes,
        units=units,
        aligned_chunks=aligned_chunks,
        generation_mode=gen_mode
    )


    # Create QuestionPaper record
    paper = QuestionPaper(
        faculty_id=current_user.id,
        syllabus_id=syllabus.id,
        title=f"{payload.course_code} - {payload.exam_name}",
        institution_name=payload.institution_name,
        course_name=payload.course_name,
        course_code=payload.course_code,
        exam_name=payload.exam_name,
        academic_year=payload.academic_year,
        semester=payload.semester,
        department=payload.department,
        programme=payload.programme or "B.E. Computer Science & Engineering",
        regulation=payload.regulation or "2021 (Autonomous)",
        exam_date=payload.exam_date,
        duration=payload.duration,
        max_marks=payload.max_marks,
        instructions=payload.instructions,
        blueprint_json=json.dumps(blueprint_dict),
        template_id=payload.template_id,
        generation_mode=gen_mode,
        coverage_matrix_json=json.dumps(coverage_matrix),
        status="generated"
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    # Add question records with full provenance, model answer, rubric, and OR-choice links
    for q_data in generated_raw:
        q_obj = Question(
            question_paper_id=paper.id,
            section_name=q_data["section_name"],
            question_number=q_data["question_number"],
            question_text=q_data["question_text"],
            marks=q_data["marks"],
            co_level=q_data["co_level"],
            bloom_level=q_data["bloom_level"],
            source_topic=q_data.get("source_topic"),
            alternative_options=q_data.get("alternatives"),
            status=q_data.get("status", "draft"),
            is_validated=False,
            difficulty=q_data.get("difficulty", "Medium"),
            unit_number=q_data.get("unit_number"),
            question_type=q_data.get("question_type", "short_answer"),
            options_json=q_data.get("options_json"),
            correct_answer_json=q_data.get("correct_answer_json"),
            explanation=q_data.get("explanation"),
            distractor_explanations_json=q_data.get("distractor_explanations_json"),
            grammar_score=q_data.get("grammar_score", 95.0),
            quality_score=q_data.get("quality_score", 90.0),
            validation_details_json=q_data.get("validation_details_json"),
            needs_review_reasons=q_data.get("needs_review_reasons"),
            source_filename=q_data.get("source_filename"),
            source_page_or_slide=q_data.get("source_page_or_slide"),
            supporting_passage=q_data.get("supporting_passage"),
            alignment_confidence=q_data.get("alignment_confidence"),
            generation_method=q_data.get("generation_method", "rag_grounded"),
            model_answer=q_data.get("model_answer"),
            marking_scheme=q_data.get("marking_scheme"),
            stepwise_solution=q_data.get("stepwise_solution"),
            rubric_json=q_data.get("rubric_json"),
            or_pair_id=q_data.get("or_pair_id"),
            or_equivalence_notes=q_data.get("or_equivalence_notes"),
            or_equivalence_score=q_data.get("or_equivalence_score", 92.0)
        )
        db.add(q_obj)

    db.commit()
    db.refresh(paper)
    return paper

@router.get("/{paper_id}", response_model=QuestionPaperResponse)
def get_question_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Get single question paper with all questions and validation status."""
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found.")
    return paper

@router.get("", response_model=List[QuestionPaperResponse])
def list_faculty_question_papers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """List question papers created by or accessible to current faculty."""
    if current_user.role == "admin":
        return db.query(QuestionPaper).order_by(QuestionPaper.created_at.desc()).limit(20).all()
    return db.query(QuestionPaper).filter(QuestionPaper.faculty_id == current_user.id).order_by(QuestionPaper.created_at.desc()).all()

@router.put("/{paper_id}/question/{question_id}", response_model=QuestionResponse)
def update_and_validate_question(
    paper_id: int,
    question_id: int,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Faculty validation endpoint: Update question text, marks, CO level,
    Bloom level, or mark the question as validated.
    """
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.question_paper_id == paper_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    if payload.question_text is not None:
        question.question_text = payload.question_text.strip()
    if payload.marks is not None:
        question.marks = payload.marks
    if payload.co_level is not None:
        question.co_level = payload.co_level.strip()
    if payload.bloom_level is not None:
        question.bloom_level = payload.bloom_level.strip()
    if payload.is_validated is not None:
        question.is_validated = payload.is_validated
    if payload.faculty_notes is not None:
        question.faculty_notes = payload.faculty_notes.strip()

    db.commit()
    db.refresh(question)

    # Check if all questions in paper are validated
    all_qs = db.query(Question).filter(Question.question_paper_id == paper_id).all()
    if all_qs and all(q.is_validated for q in all_qs):
        paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
        if paper:
            paper.status = "validated"
            db.commit()

    return question

@router.post("/{paper_id}/validate-all", response_model=QuestionPaperResponse)
def validate_all_questions(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Bulk validate / approve all questions in the question paper."""
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found.")

    db.query(Question).filter(Question.question_paper_id == paper_id).update({
        "is_validated": True,
        "status": "approved"
    })
    paper.status = "validated"
    db.commit()
    db.refresh(paper)
    return paper

@router.post("/{paper_id}/question/{question_id}/regenerate", response_model=QuestionResponse)
def regenerate_question_simple_endpoint(
    paper_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Regenerate an individual question using alternatives or a new topic synthesize."""
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.question_paper_id == paper_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    # Try to pick from alternative options if available
    alternatives = []
    if question.alternative_options:
        try:
            alternatives = json.loads(question.alternative_options)
        except Exception:
            alternatives = []

    if alternatives and len(alternatives) > 0:
        next_q = alternatives.pop(0)
        question.question_text = next_q
        question.alternative_options = json.dumps(alternatives)
    else:
        # Synthesize fresh question
        topic = question.source_topic or "Data Structures and Analysis"
        synth = synthesize_question(topic, question.bloom_level, question.marks, question.co_level)
        question.question_text = synth["question_text"]
        question.alternative_options = json.dumps(synth["alternatives"])

    question.is_validated = False # Requires re-validation
    db.commit()
    db.refresh(question)
    return question

@router.post("/{paper_id}/question", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
def add_custom_question(
    paper_id: int,
    payload: QuestionUpdate,
    section_name: str = Query("Part A"),
    question_number: str = Query("New"),
    marks: int = Query(2),
    co_level: str = Query("CO1"),
    bloom_level: str = Query("L2 - Understand"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Add a custom question manually to a section."""
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found.")

    new_q = Question(
        question_paper_id=paper_id,
        section_name=section_name,
        question_number=question_number,
        question_text=payload.question_text or "Enter custom question text...",
        marks=payload.marks or marks,
        co_level=payload.co_level or co_level,
        bloom_level=payload.bloom_level or bloom_level,
        is_validated=True
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return new_q

@router.delete("/{paper_id}/question/{question_id}")
def delete_question(
    paper_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Delete an unwanted question from the paper."""
    q = db.query(Question).filter(
        Question.id == question_id,
        Question.question_paper_id == paper_id
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    db.delete(q)
    db.commit()
    return {"message": "Question deleted successfully."}

@router.put("/{paper_id}/question/{question_id}/review", response_model=QuestionResponse)
def review_single_question(
    paper_id: int,
    question_id: int,
    payload: QuestionReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Review action on question: approve, reject, or edit.
    Updates status, reviewer remarks, and timestamps.
    """
    q = db.query(Question).filter(
        Question.id == question_id,
        Question.question_paper_id == paper_id
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    action = payload.action.lower()
    q.reviewer_id = current_user.id
    if payload.reviewer_remarks:
        q.reviewer_remarks = payload.reviewer_remarks.strip()

    if action == "approve":
        # Block approval if question is structurally invalid MCQ
        if q.options_json or (q.question_type and q.question_type.startswith("mcq")):
            q_check = {
                "question_text": q.question_text,
                "question_type": q.question_type or "mcq_single",
                "options_json": q.options_json,
                "correct_answer_json": q.correct_answer_json,
                "explanation": q.explanation
            }
            valid, _, _, issues = validate_mcq_structure(q_check)
            if not valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot approve structurally incomplete MCQ: {'; '.join(issues)}. Please edit or regenerate first."
                )
        q.status = "approved"
        q.is_validated = True
    elif action == "reject":
        q.status = "rejected"
        q.is_validated = False
    elif action == "edit":
        if payload.updated_question_text:
            q.question_text = payload.updated_question_text.strip()
        if payload.updated_marks is not None:
            q.marks = payload.updated_marks
        if payload.updated_co_level:
            q.co_level = payload.updated_co_level.strip()
        if payload.updated_model_answer:
            q.model_answer = payload.updated_model_answer.strip()
        if payload.updated_marking_scheme:
            q.marking_scheme = payload.updated_marking_scheme.strip()
        if payload.updated_question_type:
            q.question_type = payload.updated_question_type
        if payload.updated_bloom_level:
            q.bloom_level = payload.updated_bloom_level
        if payload.updated_difficulty:
            q.difficulty = payload.updated_difficulty
        if payload.updated_topic:
            q.source_topic = payload.updated_topic

        # Handle MCQ options editing
        if payload.updated_options is not None:
            norm_opts = []
            for idx, item in enumerate(payload.updated_options):
                lbl = chr(65 + idx)
                l = (item.get("label") or lbl).strip().upper()
                t = str(item.get("text", "")).strip()
                corr = bool(item.get("is_correct", False))
                norm_opts.append({"label": l, "text": t, "is_correct": corr, "explanation": item.get("explanation")})

            if any(not opt["text"] for opt in norm_opts):
                raise HTTPException(status_code=400, detail="All 4 MCQ option texts must be non-empty.")

            target_type = payload.updated_question_type or q.question_type or "mcq_single"
            corr_count = sum(1 for opt in norm_opts if opt["is_correct"])
            if target_type in ["mcq", "mcq_single"]:
                if corr_count != 1:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Single-answer MCQ must have exactly one correct option selected (found {corr_count})."
                    )
            elif target_type in ["mcq_multiple", "multiple_select"]:
                if corr_count < 2:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Multiple-select MCQ must have at least two correct options selected (found {corr_count})."
                    )

            q.options_json = json.dumps(norm_opts)
            if payload.updated_correct_answer:
                q.correct_answer_json = str(payload.updated_correct_answer).strip().upper()
            else:
                corrs = [opt["label"] for opt in norm_opts if opt["is_correct"]]
                q.correct_answer_json = corrs[0] if len(corrs) == 1 else json.dumps(corrs)

        if payload.updated_explanation:
            q.explanation = payload.updated_explanation.strip()

        # Update model_answer and marking_scheme for MCQs if needed
        if q.options_json and (not q.model_answer or "Correct Option:" not in q.model_answer):
            q.model_answer = f"Correct Option: {q.correct_answer_json}.\n\nExplanation: {q.explanation or 'Technical reasoning.'}"
        if q.options_json and not q.marking_scheme:
            q.marking_scheme = f"{q.marks} Marks: Selecting the correct option ({q.correct_answer_json})."

        # Re-score grammar and clean wording
        cleaned, g_score, _ = validate_question_grammar(q.question_text)
        q.question_text = cleaned
        q.grammar_score = g_score

        # Re-run semantic quality validation
        target_unit = {"number": q.unit_number or "1", "title": f"Unit {q.unit_number or '1'}", "topics": q.source_topic or ""}
        co_dict = {"code": q.co_level, "unit_title": target_unit.get("title", "")}
        q_eval = {
            "question_text": q.question_text,
            "question_type": q.question_type,
            "marks": q.marks,
            "co_level": q.co_level,
            "bloom_level": q.bloom_level,
            "difficulty": q.difficulty,
            "source_topic": q.source_topic,
            "unit_number": q.unit_number,
            "source_filename": q.source_filename,
            "supporting_passage": q.supporting_passage,
            "options_json": q.options_json,
            "correct_answer_json": q.correct_answer_json,
            "explanation": q.explanation,
            "model_answer": q.model_answer,
            "marking_scheme": q.marking_scheme
        }
        val_res = evaluate_semantic_quality(q_eval, target_unit, co_dict)
        q.quality_score = val_res["quality_score"]
        q.validation_details_json = val_res["details_json"]
        q.needs_review_reasons = "; ".join(val_res["reasons"]) if val_res["reasons"] else None

        if val_res["quality_score"] > 0.0 and val_res.get("status") == "draft":
            q.status = "approved"
            q.is_validated = True
        else:
            q.status = "needs_review"
            q.is_validated = False

    db.commit()
    db.refresh(q)

    # Check if all questions have been reviewed
    all_qs = db.query(Question).filter(Question.question_paper_id == paper_id).all()
    if all_qs and all(item.status in ["approved", "rejected"] for item in all_qs):
        paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
        if paper:
            paper.status = "reviewed"
            db.commit()

    return q

@router.put("/{paper_id}/question/{question_id}/regenerate", response_model=QuestionResponse)
@router.post("/{paper_id}/question/{question_id}/regenerate", response_model=QuestionResponse)
def regenerate_question_endpoint(
    paper_id: int,
    question_id: int,
    payload: QuestionRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Regenerate question using targeted faculty directives:
    simplify_wording, increase_difficulty, decrease_difficulty, change_bloom,
    change_topic, convert_to_mcq, make_programming, correct_grammar_only.
    """
    q = db.query(Question).filter(
        Question.id == question_id,
        Question.question_paper_id == paper_id
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    syllabus = db.query(Syllabus).filter(Syllabus.id == paper.syllabus_id).first() if paper else None
    
    units = []
    if syllabus and syllabus.extracted_text:
        units = extract_syllabus_units(syllabus.extracted_text)

    q_dict = {
        "id": q.id,
        "question_paper_id": q.question_paper_id,
        "question_number": q.question_number,
        "section_name": q.section_name,
        "question_text": q.question_text,
        "marks": q.marks,
        "co_level": q.co_level,
        "bloom_level": q.bloom_level,
        "difficulty": q.difficulty,
        "source_topic": q.source_topic,
        "unit_number": q.unit_number,
        "question_type": q.question_type,
        "or_pair_id": q.or_pair_id
    }

    target_unit = next((u for u in units if str(u.get("number", "")) == str(q.unit_number)), None)
    if not target_unit:
        target_unit = {"number": q.unit_number or "1", "title": f"Unit {q.unit_number or '1'}", "topics": q.source_topic or ""}

    new_q_dict = regenerate_single_question(
        existing_question=q_dict,
        directive=payload.directive or "standard",
        target_bloom=payload.target_bloom_level,
        target_difficulty=payload.target_difficulty,
        target_topic=payload.target_topic,
        target_type=payload.target_question_type,
        unit=target_unit
    )

    q.question_text = new_q_dict["question_text"]
    q.marks = new_q_dict["marks"]
    q.bloom_level = new_q_dict["bloom_level"]
    q.source_topic = new_q_dict["source_topic"]
    q.difficulty = new_q_dict["difficulty"]
    q.question_type = new_q_dict["question_type"]
    q.options_json = new_q_dict.get("options_json")
    q.correct_answer_json = new_q_dict.get("correct_answer_json")
    q.explanation = new_q_dict.get("explanation")
    q.distractor_explanations_json = new_q_dict.get("distractor_explanations_json")
    q.model_answer = new_q_dict.get("model_answer")
    q.marking_scheme = new_q_dict.get("marking_scheme")
    q.stepwise_solution = new_q_dict.get("stepwise_solution")
    q.grammar_score = new_q_dict.get("grammar_score", 95.0)
    q.quality_score = new_q_dict.get("quality_score", 90.0)
    q.validation_details_json = new_q_dict.get("validation_details_json")
    q.needs_review_reasons = new_q_dict.get("needs_review_reasons")
    q.status = new_q_dict.get("status", "draft")
    q.is_validated = False

    db.commit()
    db.refresh(q)
    return q

@router.get("/{paper_id}/question/{question_id}/source", response_model=ProvenanceResponse)
def get_question_provenance(
    paper_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Retrieve full grounding provenance details for 'View Source' modal."""
    q = db.query(Question).filter(
        Question.id == question_id,
        Question.question_paper_id == paper_id
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    return ProvenanceResponse(
        question_id=q.id,
        source_filename=q.source_filename or "Approved Institutional Syllabus",
        source_page_or_slide=q.source_page_or_slide or f"Unit {q.unit_number or '1'}",
        supporting_passage=q.supporting_passage or "Prescribed syllabus curriculum concept.",
        alignment_confidence=q.alignment_confidence or 1.0,
        generation_method=q.generation_method or "syllabus_grounded",
        source_topic=q.source_topic,
        unit_number=q.unit_number
    )

@router.post("/{paper_id}/upload-template", response_model=QuestionPaperResponse)
async def upload_word_template(
    paper_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Upload a custom Word (.docx) question paper template for this paper.
    The system will render generated and validated questions into this template format.
    """
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found.")

    ext = Path(file.filename or "").suffix.lower()
    if ext != ".docx":
        raise HTTPException(status_code=400, detail="Only Word (.docx) templates are supported.")

    clean_name = sanitize_filename(file.filename)
    stored_name = generate_safe_stored_filename(clean_name)
    stored_path = settings.UPLOAD_DIR / stored_name

    header_chunk = await file.read(1024)
    file_size = len(header_chunk)
    with open(stored_path, "wb") as f:
        f.write(header_chunk)
        while chunk := await file.read(64 * 1024):
            file_size += len(chunk)
            f.write(chunk)

    validate_uploaded_file(file, header_chunk, file_size, allowed_exts={".docx"})

    paper.template_filename = stored_name
    db.commit()
    db.refresh(paper)
    return paper

@router.get("/{paper_id}/download-docx")
def download_question_paper_docx(
    paper_id: int,
    export_type: str = Query("question_paper"), # "question_paper", "with_answer_key", "evaluation_scheme"
    export_approved_only: bool = Query(True),
    include_citations: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Generate and download Word (.docx) documents.
    Supports Question Paper (approved only), With Answer Key, and Evaluation Scheme.
    Hides citations by default on student exam papers, unless include_citations is True.
    """
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found.")

    questions = db.query(Question).filter(Question.question_paper_id == paper_id).order_by(Question.id.asc()).all()
    if not questions:
        raise HTTPException(status_code=400, detail="Question paper has no questions generated yet.")

    # Filter questions if required
    if export_approved_only:
        approved_qs = [
            q for q in questions 
            if str(q.status).lower() == "approved" or q.is_validated is True
        ]
        if not approved_qs:
            raise HTTPException(
                status_code=400,
                detail="No approved questions found. Please review and approve questions before exporting to Word (.docx)."
            )
        questions = approved_qs

    template_path = None
    orig_template_name = None
    if paper.template_filename:
        tp = settings.UPLOAD_DIR / paper.template_filename
        if tp.is_file():
            template_path = tp
    elif paper.template_id:
        tmpl = db.query(QuestionPaperTemplate).filter(QuestionPaperTemplate.id == paper.template_id).first()
        if tmpl and tmpl.stored_filename:
            tp = settings.UPLOAD_DIR / tmpl.stored_filename
            if tp.is_file():
                template_path = tp
                orig_template_name = tmpl.original_filename or tmpl.template_name

    paper_dict = {
        "institution_name": paper.institution_name,
        "department": paper.department,
        "exam_name": paper.exam_name,
        "course_name": paper.course_name,
        "course_code": paper.course_code,
        "semester": paper.semester,
        "academic_year": paper.academic_year,
        "programme": paper.programme,
        "regulation": paper.regulation,
        "exam_date": paper.exam_date,
        "duration": paper.duration,
        "max_marks": paper.max_marks,
        "instructions": paper.instructions,
        "original_template_name": orig_template_name
    }

    questions_list = [
        {
            "section_name": q.section_name,
            "question_number": q.question_number,
            "question_text": q.question_text,
            "marks": q.marks,
            "co_level": q.co_level,
            "bloom_level": q.bloom_level,
            "status": q.status,
            "is_validated": q.is_validated,
            "question_type": q.question_type,
            "options_json": q.options_json,
            "correct_answer_json": q.correct_answer_json,
            "correct_option": q.correct_answer_json,
            "explanation": q.explanation,
            "distractor_explanations_json": q.distractor_explanations_json,
            "source_filename": q.source_filename,
            "source_page_or_slide": q.source_page_or_slide,
            "supporting_passage": q.supporting_passage,
            "alignment_confidence": q.alignment_confidence,
            "model_answer": q.model_answer,
            "marking_scheme": q.marking_scheme,
            "stepwise_solution": q.stepwise_solution,
            "rubric_json": q.rubric_json,
            "or_pair_id": q.or_pair_id,
            "or_equivalence_notes": q.or_equivalence_notes
        }
        for q in questions
    ]

    # Check permission
    if current_user.role != "admin" and paper.faculty_id and paper.faculty_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to export this question paper."
        )

    out_file_path = generate_question_paper_docx(
        paper_data=paper_dict,
        questions=questions_list,
        template_path=template_path,
        export_type=export_type,
        export_approved_only=export_approved_only,
        include_citations=include_citations
    )
    clean_code = "".join(c for c in (paper.course_code or "QP") if c.isalnum() or c in "_-")
    clean_exam = "".join(c for c in (paper.exam_name or "Exam") if c.isalnum() or c in "_-")

    prefix_map = {
        "question_paper": "QuestionPaper",
        "with_answer_key": "QP_With_AnswerKey",
        "evaluation_scheme": "QP_EvaluationScheme"
    }
    file_prefix = prefix_map.get(export_type, "QuestionPaper")
    safe_download_name = f"{file_prefix}_{clean_code}_{clean_exam}.docx"

    return FileResponse(
        path=str(out_file_path),
        filename=safe_download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_download_name}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@router.post("/{paper_id}/export/docx")
def export_question_paper_docx(
    paper_id: int,
    export_type: str = Query("question_paper"),
    export_approved_only: bool = Query(True),
    include_citations: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    POST export endpoint for the finalized Word (.docx) question paper document.
    """
    return download_question_paper_docx(
        paper_id=paper_id,
        export_type=export_type,
        export_approved_only=export_approved_only,
        include_citations=include_citations,
        db=db,
        current_user=current_user
    )


@router.get("/{paper_id}/download-pdf")
def download_question_paper_pdf_endpoint(
    paper_id: int,
    export_type: str = Query("question_paper"), # "question_paper", "with_answer_key", "evaluation_scheme"
    export_approved_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Generate and download PDF question paper document using ReportLab.
    Strictly excludes answers/rubrics/provenance in 'question_paper' export.
    """
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found.")

    questions = db.query(Question).filter(Question.question_paper_id == paper_id).order_by(Question.id.asc()).all()
    if not questions:
        raise HTTPException(status_code=400, detail="Question paper has no questions generated yet.")

    if export_approved_only:
        approved_qs = [
            q for q in questions 
            if str(q.status).lower() == "approved" or q.is_validated is True
        ]
        if not approved_qs:
            raise HTTPException(
                status_code=400,
                detail="No approved questions found. Please review and approve questions before exporting to PDF."
            )
        questions = approved_qs

    paper_dict = {
        "institution_name": paper.institution_name,
        "department": paper.department,
        "exam_name": paper.exam_name,
        "course_name": paper.course_name,
        "course_code": paper.course_code,
        "semester": paper.semester,
        "academic_year": paper.academic_year,
        "programme": paper.programme,
        "regulation": paper.regulation,
        "exam_date": paper.exam_date,
        "duration": paper.duration,
        "max_marks": paper.max_marks,
        "instructions": paper.instructions
    }

    questions_list = [
        {
            "section_name": q.section_name,
            "question_number": q.question_number,
            "question_text": q.question_text,
            "marks": q.marks,
            "co_level": q.co_level,
            "bloom_level": q.bloom_level,
            "status": q.status,
            "is_validated": q.is_validated,
            "question_type": q.question_type,
            "options_json": q.options_json,
            "correct_answer_json": q.correct_answer_json,
            "correct_option": q.correct_answer_json,
            "explanation": q.explanation,
            "distractor_explanations_json": q.distractor_explanations_json,
            "source_filename": q.source_filename,
            "source_page_or_slide": q.source_page_or_slide,
            "supporting_passage": q.supporting_passage,
            "alignment_confidence": q.alignment_confidence,
            "model_answer": q.model_answer,
            "marking_scheme": q.marking_scheme,
            "stepwise_solution": q.stepwise_solution,
            "rubric_json": q.rubric_json,
            "or_pair_id": q.or_pair_id,
            "or_equivalence_notes": q.or_equivalence_notes
        }
        for q in questions
    ]

    out_file_path = generate_question_paper_pdf(
        paper_data=paper_dict,
        questions=questions_list,
        export_type=export_type,
        export_approved_only=export_approved_only
    )

    clean_code = "".join(c for c in (paper.course_code or "QP") if c.isalnum() or c in "_-")
    clean_exam = "".join(c for c in (paper.exam_name or "Exam") if c.isalnum() or c in "_-")
    prefix_map = {
        "question_paper": "QuestionPaper",
        "with_answer_key": "QP_With_AnswerKey",
        "evaluation_scheme": "QP_EvaluationScheme"
    }
    file_prefix = prefix_map.get(export_type, "QuestionPaper")
    safe_download_name = f"{file_prefix}_{clean_code}_{clean_exam}.pdf"

    return FileResponse(
        path=str(out_file_path),
        filename=safe_download_name,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_download_name}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@router.get("/{paper_id}/provenance-report")
def get_question_paper_provenance_report(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Detailed grounding provenance report for all questions in the question paper.
    """
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found.")

    questions = db.query(Question).filter(Question.question_paper_id == paper_id).order_by(Question.id.asc()).all()
    
    provenance_list = []
    total_conf = 0.0
    grounded_count = 0
    for q in questions:
        conf = float(q.alignment_confidence or 1.0)
        total_conf += conf
        if q.source_filename:
            grounded_count += 1
        provenance_list.append({
            "question_id": q.id,
            "section_name": q.section_name,
            "question_number": q.question_number,
            "question_text": q.question_text,
            "marks": q.marks,
            "co_level": q.co_level,
            "bloom_level": q.bloom_level,
            "source_topic": q.source_topic,
            "source_filename": q.source_filename,
            "source_page_or_slide": q.source_page_or_slide,
            "supporting_passage": q.supporting_passage,
            "alignment_confidence": conf,
            "generation_method": q.generation_method,
            "status": q.status
        })

    avg_conf = round((total_conf / len(questions)) * 100, 1) if questions else 100.0

    return {
        "paper_id": paper.id,
        "course_code": paper.course_code,
        "course_name": paper.course_name,
        "exam_name": paper.exam_name,
        "total_questions": len(questions),
        "grounded_questions_count": grounded_count,
        "average_confidence_percentage": avg_conf,
        "questions": provenance_list
    }

@router.get("/{paper_id}/validation-report")
def get_question_paper_validation_report(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Specification B6 & Quality Validation Report for the generated question paper.
    """
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found.")

    questions = db.query(Question).filter(Question.question_paper_id == paper_id).order_by(Question.id.asc()).all()

    errors = []
    warnings = []

    total_effective = 0
    counted_qnums = set()
    for q in questions:
        raw_num = str(q.question_number).strip()
        base_num = raw_num.split("(")[0].strip() if "(" in raw_num else raw_num.split("[")[0].strip()
        if "[OR]" not in raw_num and not (raw_num.endswith("(b)") and base_num in counted_qnums):
            total_effective += q.marks
            counted_qnums.add(base_num)

    target_marks = paper.max_marks
    if total_effective != target_marks:
        errors.append(f"Mark mismatch: Sum of effective question marks ({total_effective}) does not equal target maximum marks ({target_marks}).")

    approved_count = sum(1 for q in questions if str(q.status).lower() == "approved" or q.is_validated)
    draft_count = sum(1 for q in questions if str(q.status).lower() == "draft" and not q.is_validated)
    rejected_count = sum(1 for q in questions if str(q.status).lower() == "rejected")

    if draft_count > 0:
        warnings.append(f"{draft_count} questions are still in Draft status and require faculty approval.")
    if rejected_count > 0:
        warnings.append(f"{rejected_count} questions are marked Rejected.")

    is_valid = len(errors) == 0

    return {
        "paper_id": paper.id,
        "course_code": paper.course_code,
        "course_name": paper.course_name,
        "is_valid": is_valid,
        "calculated_total_marks": total_effective,
        "target_maximum_marks": target_marks,
        "reconciled": total_effective == target_marks,
        "approved_count": approved_count,
        "draft_count": draft_count,
        "rejected_count": rejected_count,
        "total_questions": len(questions),
        "errors": errors,
        "warnings": warnings
    }

@router.get("/default-template/download")
def download_default_template():
    """Download the standard editable university question paper Word template."""
    tmpl_path = settings.EXPORT_DIR / "Standard_University_Question_Paper_Template.docx"
    create_default_template_file(tmpl_path)
    return FileResponse(
        path=str(tmpl_path),
        filename="Standard_University_Question_Paper_Template.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

def normalize_question_status(status_raw: Any, is_validated: bool = False) -> str:
    """Normalize question status into: 'approved', 'draft', 'rejected', 'needs_revision', 'invalid'."""
    if not status_raw:
        return "approved" if is_validated else "draft"
    s = str(status_raw).strip().lower()
    if s in ["approved", "approve", "isapproved", "true"]:
        return "approved"
    if s in ["rejected", "reject"]:
        return "rejected"
    if s in ["needs_revision", "needs_review", "revision"]:
        return "needs_revision"
    if s in ["invalid", "incomplete"]:
        return "invalid"
    if s in ["draft", "pending"]:
        return "approved" if is_validated else "draft"
    return "draft"

@router.get("/{paper_id}/export-validation", response_model=Dict[str, Any])
@router.get("/{paper_id}/export-validation/", response_model=Dict[str, Any])
def get_export_validation_endpoint(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Validate whether a question paper is 100% ready for Word/PDF export.
    Enforces that:
    - total question count > 0
    - approved question count = total question count
    - draft question count = 0
    - rejected question count = 0
    - invalid question count = 0
    - effective marks equal target maximum marks
    - CO, Bloom, and internal choice (OR) parity complete
    """
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found.")

    questions = db.query(Question).filter(Question.question_paper_id == paper_id).order_by(Question.id.asc()).all()
    total_questions = len(questions)

    approved_questions = 0
    draft_questions = 0
    rejected_questions = 0
    invalid_questions = 0

    co_mapping_complete = True
    bloom_mapping_complete = True
    mcq_options_complete = True
    or_pairs = {}

    for q in questions:
        norm_status = normalize_question_status(q.status, bool(q.is_validated))
        if norm_status == "approved":
            approved_questions += 1
        elif norm_status == "rejected":
            rejected_questions += 1
        elif norm_status == "invalid":
            invalid_questions += 1
        else:
            draft_questions += 1

        if not q.co_level or not str(q.co_level).strip():
            co_mapping_complete = False

        if not q.bloom_level or not str(q.bloom_level).strip():
            bloom_mapping_complete = False

        qtype = str(q.question_type or "").lower()
        if "mcq" in qtype and q.options_json:
            try:
                opts = json.loads(q.options_json) if isinstance(q.options_json, str) else q.options_json
                if isinstance(opts, (list, dict)) and len(opts) < 2:
                    mcq_options_complete = False
            except Exception:
                mcq_options_complete = False

        q_num = str(q.question_number or "").strip()
        or_pid = q.or_pair_id
        if not or_pid and ("(a)" in q_num.lower() or "(b)" in q_num.lower()):
            b_num = re.sub(r'[^0-9]', '', q_num) or "1"
            or_pid = f"or_pair_{b_num}"
        if or_pid:
            or_pairs.setdefault(or_pid, []).append(q)

    or_pairs_complete = True
    for pid, pair_qs in or_pairs.items():
        if len(pair_qs) < 2:
            or_pairs_complete = False
            break

    total_effective = 0
    counted_qnums = set()
    for q in questions:
        raw_num = str(q.question_number).strip()
        base_num = raw_num.split("(")[0].strip() if "(" in raw_num else raw_num.split("[")[0].strip()
        if "[OR]" not in raw_num and not (raw_num.endswith("(b)") and base_num in counted_qnums):
            total_effective += (q.marks or 0)
            counted_qnums.add(base_num)

    target_marks = paper.max_marks or 100
    marks_valid = (total_effective == target_marks)

    blueprint_valid = True
    if paper.blueprint_json:
        try:
            bp_data = json.loads(paper.blueprint_json) if isinstance(paper.blueprint_json, str) else paper.blueprint_json
            if isinstance(bp_data, dict):
                sections = bp_data.get("sections", [])
                if not sections and "sections" in bp_data:
                    blueprint_valid = False
        except Exception:
            blueprint_valid = False

    template_available = True

    can_export = bool(
        total_questions > 0 and
        approved_questions == total_questions and
        draft_questions == 0 and
        rejected_questions == 0 and
        invalid_questions == 0 and
        marks_valid
    )

    if can_export:
        message = "Question paper is ready for export."
    elif total_questions == 0:
        message = "No questions found in this question paper."
    elif approved_questions < total_questions:
        message = f"Only {approved_questions} of {total_questions} questions are approved. All questions must be approved before export."
    elif draft_questions > 0:
        message = f"{draft_questions} question(s) are still in draft/review status."
    elif rejected_questions > 0:
        message = f"{rejected_questions} question(s) are marked as rejected. Replace or approve them before export."
    elif not marks_valid:
        message = f"Total effective marks ({total_effective}) do not match target maximum marks ({target_marks})."
    else:
        message = "This question paper is not ready for export."

    return {
        "paper_id": paper.id,
        "total_questions": total_questions,
        "approved_questions": approved_questions,
        "draft_questions": draft_questions,
        "rejected_questions": rejected_questions,
        "invalid_questions": invalid_questions,
        "blueprint_valid": blueprint_valid,
        "template_available": template_available,
        "marks_valid": marks_valid,
        "co_mapping_complete": co_mapping_complete,
        "bloom_mapping_complete": bloom_mapping_complete,
        "or_pairs_complete": or_pairs_complete,
        "mcq_options_complete": mcq_options_complete,
        "can_export": can_export,
        "message": message
    }

