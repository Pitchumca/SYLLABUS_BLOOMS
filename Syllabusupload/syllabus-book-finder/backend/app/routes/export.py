import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.syllabus import Syllabus
from app.models.book import Book
from app.models.search_result import SearchResult
from app.models.export_history import ExportHistory
from app.schemas.export import ExportHistoryResponse
from app.services.export_service import (
    generate_excel_report,
    generate_pdf_report,
    generate_csv_report,
    generate_json_report
)

router = APIRouter(prefix="/export", tags=["Exports & Reports"])

def _get_books_export_data(syllabus_id: int, db: Session, category: Optional[str] = None) -> List[dict]:
    """Helper to query books joined with their top search result for report generation."""
    books_query = db.query(Book).filter(Book.syllabus_id == syllabus_id)
    if category and category != "All":
        books_query = books_query.filter(Book.category == category)
        
    books = books_query.order_by(Book.id.asc()).all()
    export_rows = []

    for b in books:
        top_res = db.query(SearchResult).filter(SearchResult.book_id == b.id).order_by(SearchResult.confidence_score.desc()).first()
        export_rows.append({
            "category": b.category,
            "title": b.title,
            "authors": b.authors or "",
            "edition": b.edition or "",
            "publisher": b.publisher or "",
            "publication_year": b.publication_year or "",
            "isbn": b.isbn or "",
            "source": top_res.source if top_res else "—",
            "access_type": top_res.access_type if top_res else "No verified access found",
            "access_url": top_res.access_url if top_res else "",
            "confidence_score": top_res.confidence_score if top_res else (b.confidence_score or 0.0),
            "verification_status": top_res.verification_status if top_res else "Unverified",
            "remarks": top_res.remarks if top_res else "Pending verification"
        })
    return export_rows

def _log_export_history(db: Session, syllabus_id: int, export_type: str, filename: str, count: int):
    """Log generated export to database."""
    history = ExportHistory(
        syllabus_id=syllabus_id,
        export_type=export_type,
        filename=filename,
        file_path=str(settings.EXPORT_DIR / filename),
        record_count=count
    )
    db.add(history)
    db.commit()

@router.get("/{syllabus_id}/excel")
def export_syllabus_excel(
    syllabus_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate and download styled Excel report (.xlsx)."""
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")

    books_data = _get_books_export_data(syllabus_id, db, category)
    excel_bytes = generate_excel_report(syllabus.original_filename, books_data)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Syllabus_Books_Audit_{syllabus_id}_{timestamp}.xlsx"

    # Save copy to exports directory
    with open(settings.EXPORT_DIR / filename, "wb") as f:
        f.write(excel_bytes)

    _log_export_history(db, syllabus_id, "excel", filename, len(books_data))

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/{syllabus_id}/pdf")
def export_syllabus_pdf(
    syllabus_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate and download professional ReportLab PDF report (.pdf)."""
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")

    books_data = _get_books_export_data(syllabus_id, db, category)
    pdf_bytes = generate_pdf_report(syllabus.original_filename, books_data)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Syllabus_Books_Report_{syllabus_id}_{timestamp}.pdf"

    # Save copy to exports directory
    with open(settings.EXPORT_DIR / filename, "wb") as f:
        f.write(pdf_bytes)

    _log_export_history(db, syllabus_id, "pdf", filename, len(books_data))

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/{syllabus_id}/csv")
def export_syllabus_csv(
    syllabus_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate and download CSV report (.csv) with UTF-8 BOM."""
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")

    books_data = _get_books_export_data(syllabus_id, db, category)
    csv_str = generate_csv_report(books_data)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Syllabus_Books_{syllabus_id}_{timestamp}.csv"

    # Save copy to exports
    with open(settings.EXPORT_DIR / filename, "w", encoding="utf-8") as f:
        f.write(csv_str)

    _log_export_history(db, syllabus_id, "csv", filename, len(books_data))

    return Response(
        content=csv_str.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/{syllabus_id}/json")
def export_syllabus_json(
    syllabus_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate and download structured JSON report (.json)."""
    syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found.")

    books_data = _get_books_export_data(syllabus_id, db, category)
    json_str = generate_json_report(syllabus.original_filename, books_data)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Syllabus_Books_{syllabus_id}_{timestamp}.json"

    # Save copy to exports
    with open(settings.EXPORT_DIR / filename, "w", encoding="utf-8") as f:
        f.write(json_str)

    _log_export_history(db, syllabus_id, "json", filename, len(books_data))

    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/history", response_model=List[ExportHistoryResponse])
def get_export_history(syllabus_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Retrieve history log of exported files."""
    query = db.query(ExportHistory)
    if syllabus_id:
        query = query.filter(ExportHistory.syllabus_id == syllabus_id)
    return query.order_by(ExportHistory.created_at.desc()).limit(20).all()
