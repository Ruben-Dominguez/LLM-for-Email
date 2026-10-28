from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import settings
from src.database.connection import get_db
from src.api.schemas import HealthResponse

router = APIRouter(tags=["Health & Status"])


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """Verifica la salud del servicio y la conectividad a la base de datos SQL."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return HealthResponse(
        status="HEALTHY" if db_ok else "DEGRADED",
        database_connected=db_ok,
        llm_provider=settings.LLM_PROVIDER,
        email_source=settings.EMAIL_SOURCE,
        timestamp=datetime.now(timezone.utc),
    )

