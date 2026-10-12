@echo off
echo Starting FastAPI Backend for AI-Powered Syllabus Book Finder...
cd /d "%~dp0backend"
call .venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
