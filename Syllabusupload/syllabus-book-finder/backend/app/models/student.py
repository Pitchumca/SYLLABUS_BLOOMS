import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String(100), unique=True, index=True, nullable=False) # e.g. "21CS42"
    course_name = Column(String(255), nullable=False) # e.g. "Advanced Data Structures & Algorithms"
    department = Column(String(100), nullable=False) # e.g. "Computer Science & Engineering"
    semester = Column(String(50), nullable=False, default="IV Semester")
    academic_year = Column(String(50), nullable=False, default="2025-2026")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Foreign keys
    faculty_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    faculty = relationship("User", back_populates="taught_courses")
    syllabus = relationship("Syllabus", back_populates="courses")
    enrollments = relationship("StudentEnrollment", back_populates="course", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="course", cascade="all, delete-orphan")
    mastery_records = relationship("MasteryRecord", back_populates="course", cascade="all, delete-orphan")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    register_number = Column(String(50), unique=True, index=True, nullable=False) # e.g. "REG2023CS001"
    programme = Column(String(100), nullable=False, default="B.E. Computer Science & Engineering")
    semester = Column(String(50), nullable=False, default="IV Semester")
    section = Column(String(10), nullable=False, default="A") # "A", "B", "C"
    batch_year = Column(String(50), nullable=False, default="2023-2027")
    academic_standing = Column(String(50), nullable=False, default="Good") # "Good", "Needs Support", "Honors"

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="student_profile")


class StudentEnrollment(Base):
    __tablename__ = "student_enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_student_course_enrollment"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    semester = Column(String(50), nullable=False, default="IV Semester")
    section = Column(String(10), nullable=False, default="A")
    academic_year = Column(String(50), nullable=False, default="2025-2026")
    status = Column(String(50), nullable=False, default="enrolled") # "enrolled", "completed", "dropped"
    enrolled_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    student = relationship("User", back_populates="enrollments", foreign_keys=[student_id])
    course = relationship("Course", back_populates="enrollments")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=False, default="system") # "assessment_assigned", "remedial_plan", "reassessment_unlocked", "evaluation_complete", "system"
    link_tab = Column(String(100), nullable=True, default="student-dashboard")
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="notifications")


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    faculty_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    title = Column(String(255), nullable=False)
    assessment_type = Column(String(50), nullable=False, default="diagnostic") # "diagnostic", "adaptive", "reassessment", "formative"
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False, default=30)
    total_questions = Column(Integer, nullable=False, default=10)
    passing_percentage = Column(Float, nullable=False, default=60.0)
    instructions = Column(Text, nullable=True)
    is_published = Column(Boolean, default=True, nullable=False)
    visibility_settings = Column(Text, nullable=True) # JSON: {"show_score_immediate": true, "show_solutions": true}

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    course = relationship("Course", back_populates="assessments")
    faculty = relationship("User")
    assignments = relationship("AssessmentAssignment", back_populates="assessment", cascade="all, delete-orphan")
    attempts = relationship("StudentAttempt", back_populates="assessment", cascade="all, delete-orphan")


class AssessmentAssignment(Base):
    __tablename__ = "assessment_assignments"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    section = Column(String(20), nullable=True) # e.g. "A" (nullable for course-wide)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=True) # nullable for section-wide
    due_date = Column(DateTime, nullable=True)
    status = Column(String(50), default="active", nullable=False) # "active", "completed", "expired"
    assigned_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    assessment = relationship("Assessment", back_populates="assignments")
    course = relationship("Course")
    student = relationship("User")


class StudentAttempt(Base):
    __tablename__ = "student_attempts"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    attempt_number = Column(Integer, default=1, nullable=False)
    
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    submit_time = Column(DateTime, nullable=True)
    time_spent_seconds = Column(Integer, default=0, nullable=False)
    total_score = Column(Float, default=0.0, nullable=False)
    max_possible_score = Column(Float, default=0.0, nullable=False)
    percentage = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="in_progress", nullable=False) # "in_progress", "submitted", "evaluated"
    is_adaptive = Column(Boolean, default=False, nullable=False)
    current_difficulty = Column(String(50), default="intermediate", nullable=False) # "beginner", "intermediate", "advanced"

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    assessment = relationship("Assessment", back_populates="attempts")
    student = relationship("User")
    responses = relationship("StudentResponse", back_populates="attempt", cascade="all, delete-orphan")
    adaptive_logs = relationship("AdaptiveQuestionLog", back_populates="attempt", cascade="all, delete-orphan")


class StudentResponse(Base):
    __tablename__ = "student_responses"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("student_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    
    student_answer_json = Column(Text, nullable=True) # JSON representation of student answer
    is_correct = Column(Boolean, nullable=True) # Null for subjective questions pending review
    score_awarded = Column(Float, default=0.0, nullable=False)
    max_score = Column(Float, default=2.0, nullable=False)
    evaluation_status = Column(String(50), default="auto_graded", nullable=False) # "auto_graded", "pending_review", "faculty_reviewed"
    faculty_feedback = Column(Text, nullable=True)
    time_spent_seconds = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    attempt = relationship("StudentAttempt", back_populates="responses")
    question = relationship("Question")


class AdaptiveQuestionLog(Base):
    __tablename__ = "adaptive_question_logs"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("student_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    sequence_number = Column(Integer, nullable=False)
    difficulty_before = Column(String(50), nullable=False)
    question_difficulty = Column(String(50), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    difficulty_after = Column(String(50), nullable=False)
    adaptation_reason = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    attempt = relationship("StudentAttempt", back_populates="adaptive_logs")
    question = relationship("Question")


class MasteryRecord(Base):
    __tablename__ = "mastery_records"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", "mastery_level_type", "target_identifier", name="uq_student_mastery_identifier"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    
    mastery_level_type = Column(String(50), nullable=False) # "course", "unit", "topic", "co", "bloom"
    target_identifier = Column(String(255), nullable=False) # e.g. "CO1", "Unit 1", "L3 - Apply", "Binary Search Trees"
    numerical_score = Column(Float, default=0.0, nullable=False) # 0.0 - 100.0
    mastery_category = Column(String(50), default="Needs Support", nullable=False) # "Needs Support", "Developing", "Proficient", "Advanced", "Mastered"
    total_attempts = Column(Integer, default=1, nullable=False)
    last_assessed_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    student = relationship("User")
    course = relationship("Course", back_populates="mastery_records")


class RemedialLearningPlan(Base):
    __tablename__ = "remedial_learning_plans"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    attempt_id = Column(Integer, ForeignKey("student_attempts.id"), nullable=True)

    weak_unit = Column(String(100), nullable=True)
    weak_topic = Column(String(255), nullable=False)
    weak_co = Column(String(50), nullable=True)
    weak_bloom = Column(String(50), nullable=True)
    status = Column(String(50), default="assigned", nullable=False) # "assigned", "in_progress", "completed"
    threshold_percentage = Column(Float, default=60.0, nullable=False)
    deadline = Column(DateTime, nullable=True)
    faculty_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    faculty_notes = Column(Text, nullable=True)
    reassessment_unlocked = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    student = relationship("User", foreign_keys=[student_id])
    course = relationship("Course")
    faculty = relationship("User", foreign_keys=[faculty_id])
    resources = relationship("LearningPlanResource", back_populates="plan", cascade="all, delete-orphan")


class LearningPlanResource(Base):
    __tablename__ = "learning_plan_resources"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("remedial_learning_plans.id", ondelete="CASCADE"), nullable=False)
    resource_type = Column(String(50), nullable=False) # "textbook_chapter", "reference_book", "lecture_slide", "verified_link", "practice_question"
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    url_or_path = Column(String(500), nullable=True)
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    plan = relationship("RemedialLearningPlan", back_populates="resources")


class Reassessment(Base):
    __tablename__ = "reassessments"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("remedial_learning_plans.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_attempt_id = Column(Integer, ForeignKey("student_attempts.id"), nullable=False)
    reassessment_attempt_id = Column(Integer, ForeignKey("student_attempts.id"), nullable=False)
    original_score = Column(Float, nullable=False)
    reassessment_score = Column(Float, nullable=False)
    score_improvement = Column(Float, nullable=False)
    is_mastered = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    plan = relationship("RemedialLearningPlan")
    student = relationship("User")
