@echo off
echo Starting FastAPI Backend...
cd /d "%~dp0syllabus-book-finder\backend"
call .venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
