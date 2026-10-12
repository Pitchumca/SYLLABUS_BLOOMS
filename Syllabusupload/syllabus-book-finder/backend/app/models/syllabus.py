import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Syllabus(Base):
    __tablename__ = "syllabuses"

    id = Column(Integer, primary_key=True, index=True)
    faculty_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    page_count = Column(Integer, default=0)
    extracted_text = Column(Text, nullable=True)
    extraction_method = Column(String(50), default="PyMuPDF") # PyMuPDF, pdfplumber, Tesseract OCR, Manual
    status = Column(String(50), default="uploaded") # uploaded, parsed, searched, completed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    faculty = relationship("User", back_populates="syllabuses")
    books = relationship("Book", back_populates="syllabus", cascade="all, delete-orphan")
    exports = relationship("ExportHistory", back_populates="syllabus", cascade="all, delete-orphan")
    content_files = relationship("ContentFile", back_populates="syllabus", cascade="all, delete-orphan")
    question_papers = relationship("QuestionPaper", back_populates="syllabus", cascade="all, delete-orphan")
    courses = relationship("Course", back_populates="syllabus")
