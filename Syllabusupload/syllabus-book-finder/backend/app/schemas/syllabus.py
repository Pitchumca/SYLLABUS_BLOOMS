from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class SyllabusBase(BaseModel):
    original_filename: str
    file_size_bytes: int
    page_count: int = 0
    extraction_method: str = "PyMuPDF"
    status: str = "uploaded"

class SyllabusCreate(SyllabusBase):
    stored_filename: str
    extracted_text: Optional[str] = None

class SyllabusUpdate(BaseModel):
    extracted_text: Optional[str] = None
    status: Optional[str] = None
    extraction_method: Optional[str] = None

class SyllabusResponse(SyllabusBase):
    id: int
    stored_filename: str
    extracted_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
