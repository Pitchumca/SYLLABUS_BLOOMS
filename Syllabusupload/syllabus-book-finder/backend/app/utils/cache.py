import hashlib
import json
import datetime
from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models.cache import SearchCache

DEFAULT_TTL_HOURS = 48

def make_query_hash(query_str: str, source: str = "") -> str:
    """Generate SHA256 hash for query string and source."""
    normalized = f"{source.strip().lower()}:{query_str.strip().lower()}"
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def get_cached_search(db: Session, query_hash: str) -> Optional[Any]:
    """Retrieve valid cached search result from database."""
    cached = db.query(SearchCache).filter(SearchCache.query_hash == query_hash).first()
    if cached:
        if cached.expires_at > datetime.datetime.utcnow():
            try:
                return json.loads(cached.results_json)
            except Exception:
                return None
        else:
            # Expired, clean up
            db.delete(cached)
            db.commit()
    return None

def set_cached_search(db: Session, query_hash: str, query_params: str, data: Any, ttl_hours: int = DEFAULT_TTL_HOURS):
    """Store search response in cache table."""
    expires = datetime.datetime.utcnow() + datetime.timedelta(hours=ttl_hours)
    data_json = json.dumps(data, default=str)
    
    existing = db.query(SearchCache).filter(SearchCache.query_hash == query_hash).first()
    if existing:
        existing.query_params = query_params
        existing.results_json = data_json
        existing.expires_at = expires
    else:
        new_entry = SearchCache(
            query_hash=query_hash,
            query_params=query_params[:500],
            results_json=data_json,
            expires_at=expires
        )
        db.add(new_entry)
    db.commit()
