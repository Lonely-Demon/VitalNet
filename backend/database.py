# SQLAlchemy 2.x imports — Mapped + mapped_column is the modern non-deprecated style
from sqlalchemy import create_engine, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from typing import Optional
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vitalnet.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Required for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class CaseRecord(Base):
    __tablename__ = "cases"

    # SQLAlchemy 2.x modern Mapped style — type-annotated, no deprecation warnings
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    asha_id: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    patient_age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    patient_sex: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    chief_complaint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    complaint_duration: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    bp_systolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bp_diastolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spo2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    heart_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    symptoms_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array as string
    observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    known_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_medications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    triage_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # EMERGENCY|URGENT|ROUTINE
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_driver: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    briefing_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # full LLM JSON as string

    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


def get_db():
    # FastAPI dependency injection pattern — one session per request, auto-cleanup on exit
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
