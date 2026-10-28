from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.settings import settings
from src.database.models import Base

# Configure engine (SQLite requires check_same_thread=False for FastAPI concurrency)
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG and not settings.DATABASE_URL.startswith("sqlite"),
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Crea todas las tablas si no existen."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Inyector de dependencias para sesiones de base de datos en FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

