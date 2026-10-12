from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class ExportRequest(BaseModel):
    syllabus_id: int
    format: str # excel, pdf, csv, json
    filter_category: Optional[str] = None
    filter_access_type: Optional[str] = None

class ExportHistoryResponse(BaseModel):
    id: int
    syllabus_id: Optional[int]
    export_type: str
    filename: str
    record_count: int
    created_at: datetime

    class Config:
        from_attributes = True
