from typing import Dict, List, Any
from pydantic import BaseModel

class CategoryStats(BaseModel):
    name: str
    count: int

class AccessTypeStats(BaseModel):
    name: str
    count: int
    color: str

class SourceStats(BaseModel):
    name: str
    count: int

class ConfidenceDistribution(BaseModel):
    range: str
    count: int

class DashboardStats(BaseModel):
    total_books: int
    total_textbooks: int
    total_reference_books: int
    verified_open_access_count: int
    preview_or_borrowing_count: int
    catalogue_or_publisher_count: int
    no_verified_access_count: int
    average_confidence_score: float
    books_by_category: List[CategoryStats]
    results_by_access_type: List[AccessTypeStats]
    results_by_source: List[SourceStats]
    confidence_distribution: List[ConfidenceDistribution]
