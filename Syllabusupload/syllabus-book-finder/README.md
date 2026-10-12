# AI-Powered Syllabus Textbook and Reference Book Finder

A modern, full-stack, responsive academic web application built for faculty members and institutional curriculum committees. It allows users to upload syllabus PDFs, automatically extract textbook and reference book citations using rule-based NLP and PyMuPDF (with optional Tesseract OCR), review and edit records with duplicate-merging controls, search across authorized lawful repositories (Google Books, Open Library, Crossref, Internet Archive, DOAB), visualize accessibility analytics, and export formatted reports in Excel, PDF, CSV, and JSON.

---

## Technology Stack

- **Frontend**: React.js with Vite, Tailwind CSS, Lucide-React icons
- **Charts & Data Visualization**: Recharts
- **Frontend Testing**: Vitest & React Testing Library
- **Backend**: Python FastAPI with Pydantic v2
- **Database & ORM**: SQLite with SQLAlchemy
- **PDF Extraction**: PyMuPDF (`fitz`) with `pdfplumber` fallback
- **OCR Engine**: Tesseract OCR (`pytesseract` and `pdf2image`) as optional fallback
- **Data & Similarity Processing**: Pandas and RapidFuzz
- **Report Generation**:
  - **Excel**: OpenPyXL with styled headers (`#1E3A8A`), auto-filters, frozen panes, text-wrapping, and auto-adjusted column widths
  - **PDF**: ReportLab with academic layout, KPI metric tables, colored access badges, and running page footers
  - **CSV & JSON**: RFC 4180 CSV with UTF-8 BOM and structured JSON
- **Backend Testing**: Pytest and Pytest-Asyncio

---

## Core Features

1. **Academic Dashboard UI**:
   - Clean, accessible desktop-, tablet-, and mobile-responsive layout.
   - Pages: Home, Syllabus Upload, Extracted-Book Review, Book-Search Results, Analytics Dashboard, Export Page, About & Usage Policy.
2. **Robust PDF Ingestion & OCR**:
   - Drag-and-drop or file picker with 25 MB file size limit and magic-byte validation.
   - Fast primary text extraction via PyMuPDF.
   - Fallback text extraction via `pdfplumber`.
   - OCR fallback trigger using Tesseract OCR for scanned or image-based PDFs.
   - In-browser editable syllabus text area.
3. **Rule-Based NLP & Section Detection (Zero Paid LLM)**:
   - Identifies headings such as *Text Books*, *Textbooks*, *Prescribed Books*, *Reference Books*, *References*, *Suggested Reading*, *Additional Reading*.
   - Specialized parsing for Indian university syllabus formats (VTU, Anna University, Mumbai University, JNTU, AICTE, T1/R1 patterns).
   - Handles multi-line citations, numbered lists, bullet points, and extracts Title, Author(s), Edition, Publisher, Year, and ISBN.
4. **Faculty Review & Duplicate Merge**:
   - In-place editable table to modify any citation field.
   - Instant toggle between *Textbook* and *Reference Book*.
   - Add missing books manually.
   - Duplicate detection badge with side-by-side comparison and record merging.
5. **Lawful Book-Access Search & Prioritization**:
   - Strictly queries authorized, legal repositories: Google Books API, Open Library Search API, Crossref REST API, Internet Archive Search API, and DOAB.
   - Search prioritization hierarchy:
     1. ISBN
     2. Exact title and author
     3. Exact title
     4. Title keywords and author
     5. Publisher and publication year
   - Match confidence score (0–100%) calculated via RapidFuzz similarity algorithms.
   - Caches repeated searches and implements retries with exponential backoff.
6. **8-Tier Color-Coded Access Classification**:
   - 🟢 **Verified open-access full text**
   - 🟢 **Public-domain full text**
   - 🔵 **Borrowing available** (Controlled Digital Lending via Open Library / IA)
   - 🔵 **Preview available** (Google Books preview & sample chapters)
   - 🟠 **Catalogue record** (WorldCat, Crossref, Open Library library holding)
   - 🟠 **Publisher or purchase page** (Official publisher portal)
   - ⚪ **General discovery link** (Google Scholar / general index)
   - 🔴 **No verified access found**
7. **Interactive Analytics**:
   - Summary metric cards (Total books, Textbooks, Reference books, Open Access, Borrowing/Preview, Average confidence).
   - Recharts visual charts: Books by Category (Donut chart), Results by Access Type (Bar chart), Results by Source Repository, and Match Confidence Distribution.
8. **Institutional Export Options**:
   - One-click downloads for Excel (.xlsx), PDF (.pdf), CSV (.csv), and JSON (.json).
   - Audit trail tracking past export history.

---

## Project Structure

```text
syllabus-book-finder/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app, middleware, CORS, lifespan
│   │   ├── config.py                   # Pydantic Settings and paths
│   │   ├── database.py                 # SQLite database engine and session
│   │   ├── models/                     # SQLAlchemy models (Syllabus, Book, SearchResult, etc.)
│   │   ├── schemas/                    # Pydantic validation schemas
│   │   ├── routes/                     # API routes (upload, books, search, analytics, export)
│   │   ├── services/
│   │   │   ├── pdf_extractor.py        # PyMuPDF & pdfplumber extraction
│   │   │   ├── ocr_service.py          # Tesseract OCR fallback
│   │   │   ├── book_parser.py          # Rule-based NLP citation parser
│   │   │   ├── search_service.py       # Lawful search engine (Google Books, Open Library, etc.)
│   │   │   ├── match_engine.py         # RapidFuzz similarity & access classification
│   │   │   └── export_service.py       # OpenPyXL & ReportLab generators
│   │   └── utils/                      # Security validation and cache helpers
│   ├── tests/                          # Pytest test suite
│   ├── sample_data/                    # Sample syllabus PDF and text files
│   ├── uploads/                        # PDF storage directory
│   ├── exports/                        # Generated audit reports
│   ├── requirements.txt                # Python backend dependencies
│   └── .env.example                    # Backend environment template
├── frontend/
│   ├── src/
│   │   ├── components/                 # Reusable UI components (Navbar, BookCard, BookTable, etc.)
│   │   ├── pages/                      # Page views (Home, Upload, Review, Results, Analytics, Export, About)
│   │   ├── services/                   # API client
│   │   ├── hooks/                      # Custom hooks (useDebounce)
│   │   ├── context/                    # AppContext global state
│   │   └── App.jsx                     # Application root
│   ├── package.json                    # Frontend dependencies
│   ├── tailwind.config.js              # Tailwind CSS theme
│   └── .env.example                    # Frontend environment template
├── README.md                           # Documentation
├── docker-compose.yml                  # Docker containerization
└── .gitignore
```

---

## Local Execution Instructions

### Prerequisites
- Python 3.10+ (Tested on Python 3.14)
- Node.js 18+ and npm
- (Optional) Tesseract OCR if local OCR for scanned PDFs is desired

### 1. Backend Setup

```bash
cd backend
python -m venv .venv

# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The backend will be running at: `http://127.0.0.1:8000`  
Swagger API interactive documentation: `http://127.0.0.1:8000/docs`

### 2. Frontend Setup

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend will be running at: `http://localhost:5173`

---

## Running with Docker

You can run the complete full-stack application using Docker Compose:

```bash
docker-compose up --build
```

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

---

## Automated Testing

### Backend Tests (Pytest)

Run all 20 unit and integration tests covering PDF extraction, Indian university citation parsing, ISBN normalization, duplicate detection, RapidFuzz match engine, and Excel/PDF generation:

```bash
cd backend
.\.venv\Scripts\pytest -v tests
```

### Frontend Tests (Vitest)

```bash
cd frontend
npm run test
```

---

## Sample Syllabus Included

A pre-compiled sample computer science syllabus is provided in `backend/sample_data/`:
- `sample_syllabus_cs.pdf`: Ready to upload on the Upload page.
- `sample_syllabus_text.txt`: Text version containing 7 course citations (Algorithms by Cormen, Weiss, Horowitz, Goodrich, Sedgewick, Levitin, and Aho).
- Quick Launcher: The **Try Sample Syllabus** button on the Home page immediately parses and navigates to the Review page.

---

## Lawful Access and Copyright Compliance

This software complies strictly with intellectual property regulations and educational fair use principles:
- **No Pirated Content**: Does not interface with pirate book collections, shadow libraries, or paywall bypass scripts.
- **No Unauthorized Downloads**: The backend only queries metadata and official landing URLs. It does not download or re-distribute copyrighted full texts.
- **Open Access Integrity**: Links are classified as *Verified Open Access* only when authoritative metadata confirms a Creative Commons license or public domain release.
