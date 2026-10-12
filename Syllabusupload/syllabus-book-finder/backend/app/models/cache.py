import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base

class SearchCache(Base):
    __tablename__ = "search_cache"

    id = Column(Integer, primary_key=True, index=True)
    query_hash = Column(String(64), unique=True, index=True, nullable=False)
    query_params = Column(String(500), nullable=False)
    results_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
