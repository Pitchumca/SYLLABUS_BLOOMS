from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.syllabus import Syllabus
from app.models.book import Book
from app.models.search_result import SearchResult
from app.schemas.analytics import DashboardStats, CategoryStats, AccessTypeStats, SourceStats, ConfidenceDistribution
from app.services.match_engine import (
    ACCESS_VERIFIED_OPEN,
    ACCESS_PUBLIC_DOMAIN,
    ACCESS_BORROWING,
    ACCESS_PREVIEW,
    ACCESS_CATALOGUE,
    ACCESS_PUBLISHER,
    ACCESS_GENERAL,
    ACCESS_NONE
)

router = APIRouter(prefix="/analytics", tags=["Analytics Dashboard"])

@router.get("/{syllabus_id}", response_model=DashboardStats)
def get_syllabus_analytics(syllabus_id: int, db: Session = Depends(get_db)):
    """
    Compute comprehensive dashboard analytics and Recharts dataset for a syllabus:
    - Counts for categories, access tiers, and sources
    - Confidence score distribution histogram
    """
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")

    books = db.query(Book).filter(Book.syllabus_id == syllabus_id).all()
    total_books = len(books)
    if total_books == 0:
        return DashboardStats(
            total_books=0,
            total_textbooks=0,
            total_reference_books=0,
            verified_open_access_count=0,
            preview_or_borrowing_count=0,
            catalogue_or_publisher_count=0,
            no_verified_access_count=0,
            average_confidence_score=0.0,
            books_by_category=[],
            results_by_access_type=[],
            results_by_source=[],
            confidence_distribution=[]
        )

    # 1. Categories
    total_textbooks = sum(1 for b in books if b.category == "Textbook")
    total_ref_books = sum(1 for b in books if b.category == "Reference Book")
    
    books_by_category = [
        CategoryStats(name="Textbooks", count=total_textbooks),
        CategoryStats(name="Reference Books", count=total_ref_books)
    ]

    # 2. Access Types (evaluated per book using highest confidence result)
    access_counts = {
        ACCESS_VERIFIED_OPEN: 0,
        ACCESS_PUBLIC_DOMAIN: 0,
        ACCESS_BORROWING: 0,
        ACCESS_PREVIEW: 0,
        ACCESS_CATALOGUE: 0,
        ACCESS_PUBLISHER: 0,
        ACCESS_GENERAL: 0,
        ACCESS_NONE: 0
    }

    source_counts = {}
    confidence_scores = []
    
    # Bins: 0-20, 21-40, 41-60, 61-80, 81-100
    conf_bins = {"0-20%": 0, "21-40%": 0, "41-60%": 0, "61-80%": 0, "81-100%": 0}

    for b in books:
        top_sr = db.query(SearchResult).filter(SearchResult.book_id == b.id).order_by(SearchResult.confidence_score.desc()).first()
        if top_sr:
            acc = top_sr.access_type
            access_counts[acc] = access_counts.get(acc, 0) + 1
            src = top_sr.source
            source_counts[src] = source_counts.get(src, 0) + 1
            score = top_sr.confidence_score
        else:
            access_counts[ACCESS_NONE] += 1
            score = b.confidence_score or 0.0

        confidence_scores.append(score)
        if score <= 20:
            conf_bins["0-20%"] += 1
        elif score <= 40:
            conf_bins["21-40%"] += 1
        elif score <= 60:
            conf_bins["41-60%"] += 1
        elif score <= 80:
            conf_bins["61-80%"] += 1
        else:
            conf_bins["81-100%"] += 1

    verified_open_access = access_counts[ACCESS_VERIFIED_OPEN] + access_counts[ACCESS_PUBLIC_DOMAIN]
    preview_or_borrowing = access_counts[ACCESS_PREVIEW] + access_counts[ACCESS_BORROWING]
    catalogue_or_pub = access_counts[ACCESS_CATALOGUE] + access_counts[ACCESS_PUBLISHER]
    no_verified_access = access_counts[ACCESS_NONE] + access_counts[ACCESS_GENERAL]

    avg_conf = round(sum(confidence_scores) / max(1, len(confidence_scores)), 1)

    results_by_access_type = [
        AccessTypeStats(name="Open Access", count=access_counts[ACCESS_VERIFIED_OPEN] + access_counts[ACCESS_PUBLIC_DOMAIN], color="#16A34A"),
        AccessTypeStats(name="Borrowing", count=access_counts[ACCESS_BORROWING], color="#2563EB"),
        AccessTypeStats(name="Preview", count=access_counts[ACCESS_PREVIEW], color="#0284C7"),
        AccessTypeStats(name="Catalogue", count=access_counts[ACCESS_CATALOGUE], color="#EA580C"),
        AccessTypeStats(name="Publisher", count=access_counts[ACCESS_PUBLISHER], color="#D97706"),
        AccessTypeStats(name="No Verified Access", count=access_counts[ACCESS_NONE] + access_counts[ACCESS_GENERAL], color="#DC2626")
    ]

    results_by_source = [
        SourceStats(name=k, count=v) for k, v in source_counts.items()
    ]
    if not results_by_source:
        results_by_source = [SourceStats(name="Not Searched", count=total_books)]

    confidence_distribution = [
        ConfidenceDistribution(range=k, count=v) for k, v in conf_bins.items()
    ]

    return DashboardStats(
        total_books=total_books,
        total_textbooks=total_textbooks,
        total_reference_books=total_ref_books,
        verified_open_access_count=verified_open_access,
        preview_or_borrowing_count=preview_or_borrowing,
        catalogue_or_publisher_count=catalogue_or_pub,
        no_verified_access_count=no_verified_access,
        average_confidence_score=avg_conf,
        books_by_category=books_by_category,
        results_by_access_type=results_by_access_type,
        results_by_source=results_by_source,
        confidence_distribution=confidence_distribution
    )
