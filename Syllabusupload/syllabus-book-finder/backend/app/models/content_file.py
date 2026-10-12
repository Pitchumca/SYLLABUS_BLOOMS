import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class ContentFile(Base):
    __tablename__ = "content_files"

    id = Column(Integer, primary_key=True, index=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id"), nullable=True)
    faculty_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False) # "pptx", "ppt", "pdf", "docx", "txt"
    file_size_bytes = Column(Integer, nullable=False)
    extracted_text = Column(Text, nullable=True)
    slide_or_page_count = Column(Integer, default=0)
    
    # Grounded extraction & alignment fields
    extraction_status = Column(String(50), default="extracted", nullable=False) # "uploaded", "processing", "extracted", "partially_extracted", "failed"
    extraction_warnings = Column(Text, nullable=True) # JSON array of warnings
    chunks_json = Column(Text, nullable=True) # JSON array of slide/page chunks
    alignments_json = Column(Text, nullable=True) # JSON array of alignments to syllabus units & topics
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    syllabus = relationship("Syllabus", back_populates="content_files")
    faculty = relationship("User", back_populates="content_files")
