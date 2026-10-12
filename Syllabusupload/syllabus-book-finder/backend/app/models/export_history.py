import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class ExportHistory(Base):
    __tablename__ = "export_history"

    id = Column(Integer, primary_key=True, index=True)
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id", ondelete="CASCADE"), nullable=True)
    export_type = Column(String(20), nullable=False) # excel, pdf, csv, json
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    record_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    syllabus = relationship("Syllabus", back_populates="exports")
