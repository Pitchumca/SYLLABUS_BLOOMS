from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# SQLite needs connect_args check_same_thread: False for multithreaded FastAPI requests
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

from sqlalchemy import text

def run_migrations():
    """Ensure newly added columns are present in existing SQLite tables."""
    with engine.connect() as conn:
        # Check if faculty_id exists in syllabuses
        try:
            res = conn.execute(text("PRAGMA table_info(syllabuses);")).fetchall()
            cols = [r[1] for r in res]
            if "faculty_id" not in cols and len(cols) > 0:
                conn.execute(text("ALTER TABLE syllabuses ADD COLUMN faculty_id INTEGER;"))
                conn.commit()
        except Exception:
            pass

        # Check if extended columns exist in questions
        try:
            res = conn.execute(text("PRAGMA table_info(questions);")).fetchall()
            cols = [r[1] for r in res]
            if len(cols) > 0:
                for col, col_type in [
                    ("question_type", "VARCHAR(50) DEFAULT 'short_answer'"),
                    ("options_json", "TEXT"),
                    ("correct_answer_json", "TEXT"),
                    ("explanation", "TEXT"),
                    ("difficulty", "VARCHAR(50) DEFAULT 'intermediate'"),
                    ("unit_number", "VARCHAR(20)"),
                    ("course_id", "INTEGER"),
                    ("status", "VARCHAR(50) DEFAULT 'draft'"),
                    ("source_filename", "VARCHAR(255)"),
                    ("source_page_or_slide", "VARCHAR(50)"),
                    ("supporting_passage", "TEXT"),
                    ("alignment_confidence", "FLOAT DEFAULT 0.85"),
                    ("generation_method", "VARCHAR(50) DEFAULT 'grounded_rag'"),
                    ("reviewer_id", "INTEGER"),
                    ("reviewer_remarks", "TEXT"),
                    ("model_answer", "TEXT"),
                    ("marking_scheme", "TEXT"),
                    ("stepwise_solution", "TEXT"),
                    ("rubric_json", "TEXT"),
                    ("or_pair_id", "VARCHAR(50)"),
                    ("or_equivalence_notes", "TEXT"),
                    ("or_equivalence_score", "FLOAT DEFAULT 92.0"),
                    ("grammar_score", "FLOAT DEFAULT 95.0"),
                    ("quality_score", "FLOAT DEFAULT 90.0"),
                    ("validation_details_json", "TEXT"),
                    ("distractor_explanations_json", "TEXT"),
                    ("needs_review_reasons", "TEXT")
                ]:
                    if col not in cols:
                        conn.execute(text(f"ALTER TABLE questions ADD COLUMN {col} {col_type};"))
                conn.commit()
        except Exception:
            pass

        # Check if extended columns exist in content_files
        try:
            res = conn.execute(text("PRAGMA table_info(content_files);")).fetchall()
            cols = [r[1] for r in res]
            if len(cols) > 0:
                for col, col_type in [
                    ("extraction_status", "VARCHAR(50) DEFAULT 'extracted'"),
                    ("extraction_warnings", "TEXT"),
                    ("chunks_json", "TEXT"),
                    ("alignments_json", "TEXT")
                ]:
                    if col not in cols:
                        conn.execute(text(f"ALTER TABLE content_files ADD COLUMN {col} {col_type};"))
                conn.commit()
        except Exception:
            pass

        # Check if extended columns exist in question_papers
        try:
            res = conn.execute(text("PRAGMA table_info(question_papers);")).fetchall()
            cols = [r[1] for r in res]
            if len(cols) > 0:
                for col, col_type in [
                    ("programme", "VARCHAR(100) DEFAULT 'B.E. Computer Science & Engineering'"),
                    ("regulation", "VARCHAR(50) DEFAULT '2021 (Autonomous)'"),
                    ("generation_mode", "VARCHAR(50) DEFAULT 'syllabus_ppt'"),
                    ("coverage_matrix_json", "TEXT"),
                    ("template_id", "INTEGER")
                ]:
                    if col not in cols:
                        conn.execute(text(f"ALTER TABLE question_papers ADD COLUMN {col} {col_type};"))
                conn.commit()
        except Exception:
            pass

        # Check if stored_document_id exists in resource_records
        try:
            res = conn.execute(text("PRAGMA table_info(resource_records);")).fetchall()
            cols = [r[1] for r in res]
            if len(cols) > 0 and "stored_document_id" not in cols:
                conn.execute(text("ALTER TABLE resource_records ADD COLUMN stored_document_id INTEGER;"))
                conn.commit()
        except Exception:
            pass

        # Check if extended columns exist in search_results
        try:
            res = conn.execute(text("PRAGMA table_info(search_results);")).fetchall()
            cols = [r[1] for r in res]
            if len(cols) > 0:
                for col, col_type in [
                    ("subtitle", "VARCHAR(500)"),
                    ("authors_json", "TEXT"),
                    ("edition", "VARCHAR(100)"),
                    ("isbn_10", "VARCHAR(20)"),
                    ("isbn_13", "VARCHAR(20)"),
                    ("internet_archive_identifier", "VARCHAR(255)"),
                    ("internet_archive_item_url", "TEXT"),
                    ("verified_download_url", "TEXT"),
                    ("access_status", "VARCHAR(50) DEFAULT 'METADATA_ONLY'"),
                    ("rights_or_license", "VARCHAR(255)"),
                    ("verification_http_status", "INTEGER"),
                    ("verification_message", "TEXT"),
                    ("verified_at", "DATETIME"),
                    ("local_file_path", "VARCHAR(500)"),
                    ("checksum_sha256", "VARCHAR(64)")
                ]:
                    if col not in cols:
                        conn.execute(text(f"ALTER TABLE search_results ADD COLUMN {col} {col_type};"))
                conn.commit()
        except Exception:
            pass

        # Check if extended columns exist in books
        try:
            res = conn.execute(text("PRAGMA table_info(books);")).fetchall()
            cols = [r[1] for r in res]
            if len(cols) > 0:
                for col, col_type in [
                    ("subtitle", "VARCHAR(500)"),
                    ("authors_json", "TEXT"),
                    ("isbn_10", "VARCHAR(20)"),
                    ("isbn_13", "VARCHAR(20)")
                ]:
                    if col not in cols:
                        conn.execute(text(f"ALTER TABLE books ADD COLUMN {col} {col_type};"))
                conn.commit()
        except Exception:
            pass

        # Check if auto_download_verified_oa exists in users
        try:
            res = conn.execute(text("PRAGMA table_info(users);")).fetchall()
            cols = [r[1] for r in res]
            if len(cols) > 0 and "auto_download_verified_oa" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN auto_download_verified_oa BOOLEAN DEFAULT 0;"))
                conn.commit()
        except Exception:
            pass

        # Check if rag_chunks has notnull constraint on rag_document_id
        try:
            res = conn.execute(text("PRAGMA table_info(rag_chunks);")).fetchall()
            for r in res:
                if r[1] == "rag_document_id" and r[3] == 1:
                    conn.execute(text("ALTER TABLE rag_chunks RENAME TO rag_chunks_old;"))
                    conn.commit()
                    Base.metadata.tables["rag_chunks"].create(conn)
                    conn.execute(text("INSERT INTO rag_chunks SELECT * FROM rag_chunks_old;"))
                    conn.execute(text("DROP TABLE rag_chunks_old;"))
                    conn.commit()
                    break
        except Exception:
            pass

    # Ensure all newly defined tables are created
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
