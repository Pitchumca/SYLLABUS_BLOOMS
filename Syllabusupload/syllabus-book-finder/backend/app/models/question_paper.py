import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class QuestionPaper(Base):
    __tablename__ = "question_papers"

    id = Column(Integer, primary_key=True, index=True)
    faculty_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id"), nullable=True)
    
    # Exam & Course Metadata
    title = Column(String(255), nullable=False, default="Question Paper")
    institution_name = Column(String(255), nullable=False, default="Department Examination")
    course_name = Column(String(255), nullable=False, default="")
    course_code = Column(String(100), nullable=False, default="")
    exam_name = Column(String(255), nullable=False, default="Semester End Examination")
    academic_year = Column(String(50), nullable=False, default="2025-2026")
    semester = Column(String(50), nullable=False, default="IV")
    department = Column(String(100), nullable=False, default="")
    programme = Column(String(100), nullable=True, default="B.E. Computer Science & Engineering")
    regulation = Column(String(50), nullable=True, default="2021 (Autonomous)")
    exam_date = Column(String(50), nullable=True)
    duration = Column(String(50), nullable=False, default="3 Hours")
    max_marks = Column(Integer, nullable=False, default=100)
    instructions = Column(Text, nullable=True)

    # Blueprint JSON configuration & template info
    template_id = Column(Integer, ForeignKey("question_paper_templates.id"), nullable=True)
    blueprint_json = Column(Text, nullable=True) # JSON representation of sections, target COs, marks, bloom levels
    template_filename = Column(String(255), nullable=True) # Custom uploaded Word .docx filename
    generation_mode = Column(String(50), default="syllabus_ppt", nullable=False) # "syllabus_only", "syllabus_ppt", "syllabus_books", "all_sources"
    coverage_matrix_json = Column(Text, nullable=True)
    status = Column(String(50), default="draft") # "draft", "generated", "validated", "exported"

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    faculty = relationship("User", back_populates="question_papers")
    syllabus = relationship("Syllabus", back_populates="question_papers")
    questions = relationship("Question", back_populates="question_paper", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    question_paper_id = Column(Integer, ForeignKey("question_papers.id"), nullable=False)
    
    section_name = Column(String(100), nullable=False) # e.g. "Part A", "Part B", "Part C"
    question_number = Column(String(50), nullable=False) # e.g. "1", "2(a)", "2(b)"
    question_text = Column(Text, nullable=False)
    marks = Column(Integer, nullable=False, default=2)
    co_level = Column(String(50), nullable=False, default="CO1") # e.g. "CO1", "CO2", "CO3", "CO4", "CO5"
    bloom_level = Column(String(100), nullable=False, default="L2 - Understand") # e.g. "L1 - Remember", "L2 - Understand", etc.
    
    # Faculty validation & review lifecycle
    status = Column(String(50), default="draft", nullable=False) # "draft", "approved", "rejected"
    is_validated = Column(Boolean, default=False, nullable=False)
    faculty_notes = Column(Text, nullable=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer_remarks = Column(Text, nullable=True)
    source_topic = Column(String(255), nullable=True)
    alternative_options = Column(Text, nullable=True) # JSON list of alternative candidate questions

    # Assessment & Adaptive learning fields
    question_type = Column(String(50), default="short_answer", nullable=True) # "mcq", "multiple_select", "true_false", "fill_blank", "short_answer", "descriptive", "numerical", "programming", "case_study", "design"
    options_json = Column(Text, nullable=True) # JSON list of options
    correct_answer_json = Column(Text, nullable=True) # JSON of correct answer
    explanation = Column(Text, nullable=True)
    difficulty = Column(String(50), default="intermediate", nullable=True) # "beginner", "intermediate", "advanced" (or "Easy", "Medium", "Hard")
    unit_number = Column(String(20), nullable=True) # e.g. "1", "2", "3"
    course_id = Column(Integer, nullable=True)

    # Source Provenance & Grounding
    source_filename = Column(String(255), nullable=True)
    source_page_or_slide = Column(String(50), nullable=True) # e.g. "Slide 4" or "Page 12"
    supporting_passage = Column(Text, nullable=True) # Extracted excerpt supporting the question
    alignment_confidence = Column(Float, default=0.85, nullable=True) # Confidence percentage/score
    generation_method = Column(String(50), default="grounded_rag", nullable=True) # "grounded_rag", "syllabus_only", "manual"

    # Answer Key & Rubric (Requirement 14)
    model_answer = Column(Text, nullable=True)
    marking_scheme = Column(Text, nullable=True)
    stepwise_solution = Column(Text, nullable=True)
    rubric_json = Column(Text, nullable=True)

    # OR-choice Pair Equivalence (Requirement 12)
    or_pair_id = Column(String(50), nullable=True) # Links 11(a) and 11(b) together
    or_equivalence_notes = Column(Text, nullable=True)
    or_equivalence_score = Column(Float, default=92.0, nullable=True)

    # Academic Quality, Grammar & Semantic Quality Scores
    grammar_score = Column(Float, default=95.0, nullable=True)
    quality_score = Column(Float, default=90.0, nullable=True)
    validation_details_json = Column(Text, nullable=True) # JSON with 11 quality sub-scores
    distractor_explanations_json = Column(Text, nullable=True) # JSON explaining why wrong options are incorrect
    needs_review_reasons = Column(Text, nullable=True) # Explanation if question fell below quality threshold

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    question_paper = relationship("QuestionPaper", back_populates="questions")
