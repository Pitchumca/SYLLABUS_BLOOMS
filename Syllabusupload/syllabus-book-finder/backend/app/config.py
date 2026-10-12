import os
from pathlib import Path
from typing import List, Union
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Syllabus Textbook and Reference Book Finder"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Server configuration
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite:///./syllabus_books.db"
    
    # Storage directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    EXPORT_DIR: Path = BASE_DIR / "exports"
    STORAGE_DIR: Path = BASE_DIR / "storage"
    
    # Limits
    MAX_UPLOAD_SIZE_MB: int = 25
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024
    
    # Third-party APIs (Optional API Key)
    GOOGLE_BOOKS_API_KEY: str = ""
    
    # Allowed origins (supports string or list)
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    # Tesseract configuration
    TESSERACT_CMD: str = ""
    
    @property
    def cors_origins(self) -> List[str]:
        if isinstance(self.ALLOWED_ORIGINS, list):
            return self.ALLOWED_ORIGINS
        if isinstance(self.ALLOWED_ORIGINS, str):
            return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        return ["*"]

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
