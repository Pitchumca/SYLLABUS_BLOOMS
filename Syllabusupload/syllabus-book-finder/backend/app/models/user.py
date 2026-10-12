import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default="faculty", nullable=False) # "admin" | "faculty"
    department = Column(String(100), nullable=False) # e.g. "Computer Science & Engineering"
    designation = Column(String(100), nullable=False) # e.g. "Professor", "Associate Professor", "Assistant Professor", "HOD"
    employee_id = Column(String(50), nullable=True)
    phone = Column(String(30), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    auto_download_verified_oa = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    syllabuses = relationship("Syllabus", back_populates="faculty", cascade="all, delete-orphan")
    content_files = relationship("ContentFile", back_populates="faculty", cascade="all, delete-orphan")
    question_papers = relationship("QuestionPaper", back_populates="faculty", cascade="all, delete-orphan")
    student_profile = relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    enrollments = relationship("StudentEnrollment", back_populates="student", foreign_keys="[StudentEnrollment.student_id]", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    taught_courses = relationship("Course", back_populates="faculty", cascade="all, delete-orphan")
