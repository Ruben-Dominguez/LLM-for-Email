import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")


class Settings:
    # Project
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Sistema Contable de Facturación con LLM")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
    BASE_DIR: Path = BASE_DIR

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/invoices.db")

    # LLM Settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock").lower()
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "gemini-2.5-flash")

    # Email / IMAP Settings
    EMAIL_SOURCE: str = os.getenv("EMAIL_SOURCE", "mock").lower()
    IMAP_SERVER: str = os.getenv("IMAP_SERVER", "imap.gmail.com")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USER: str = os.getenv("IMAP_USER", "")
    IMAP_PASSWORD: str = os.getenv("IMAP_PASSWORD", "")
    IMAP_FOLDER: str = os.getenv("IMAP_FOLDER", "INBOX")

    # Validation Rules
    PO_TOLERANCE_PERCENTAGE: float = float(os.getenv("PO_TOLERANCE_PERCENTAGE", "2.0"))
    MAX_INVOICE_AGE_DAYS: int = int(os.getenv("MAX_INVOICE_AGE_DAYS", "90"))

    # Storage Paths
    DATA_DIR: Path = BASE_DIR / "data"
    MOCK_INBOX_DIR: Path = BASE_DIR / "data" / "mock_inbox"
    SAMPLES_DIR: Path = BASE_DIR / "data" / "samples"
    EXPORTS_DIR: Path = BASE_DIR / "exports"


settings = Settings()
os.makedirs(settings.EXPORTS_DIR, exist_ok=True)
os.makedirs(settings.MOCK_INBOX_DIR, exist_ok=True)
os.makedirs(settings.SAMPLES_DIR, exist_ok=True)

