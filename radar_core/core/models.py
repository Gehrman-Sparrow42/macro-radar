"""Data models for radar_core defining database entities, fetcher items, and LLM outputs."""

from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Literal
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, JSON


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def compute_content_hash(text: str) -> str:
    """
    Compute a deterministic SHA-256 hash for deduplication.
    Normalizes consecutive whitespace and trims ends.
    """
    canonical_text = re.sub(r"\s+", " ", text.strip())
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Transfer Objects (Fetchers & LLM)
# ---------------------------------------------------------------------------

class RawItem(BaseModel):
    """Normalized data packet produced by fetchers prior to DB ingestion."""

    source_name: str
    url: str
    title: str
    content_text: str
    raw_metadata: dict[str, Any] = PydanticField(default_factory=dict)


class StructuredAnalysisOutput(BaseModel):
    """Pydantic schema used by Google GenAI for native structured output validation."""

    severity: Literal["INFO", "WARNING", "OPPORTUNITY", "CRITICAL"] = PydanticField(
        description="Assessed severity/impact classification of the intelligence item."
    )
    summary_title: str = PydanticField(
        description="Concise, high-impact headline summarizing the finding (max 150 chars)."
    )
    detailed_reasoning: str = PydanticField(
        description="Comprehensive analytical reasoning explaining why this matters, mechanisms, and implications."
    )
    action_items: list[str] = PydanticField(
        default_factory=list,
        description="Actionable next steps, strategic recommendations, or operational tasks."
    )
    metrics: dict[str, Any] = PydanticField(
        default_factory=dict,
        description="Key numerical scores (e.g. relevance 0-100, confidence 0-1) and semantic tags."
    )


# ---------------------------------------------------------------------------
# Database Tables (SQLModel / SQLAlchemy)
# ---------------------------------------------------------------------------

class RawData(SQLModel, table=True):
    """Raw ingested documents with SHA-256 deduplication."""

    __tablename__ = "raw_data"

    id: int | None = Field(default=None, primary_key=True)
    source_name: str = Field(index=True, nullable=False)
    url: str = Field(nullable=False)
    title: str = Field(nullable=False)
    content_text: str = Field(nullable=False)
    content_hash: str = Field(
        unique=True,
        index=True,
        nullable=False,
        description="SHA-256 hash of canonical content to guarantee uniqueness"
    )
    fetched_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    is_processed: bool = Field(default=False, index=True)

    # Relationships
    analyses: list["AnalysisResult"] = Relationship(back_populates="raw_data")


class AnalysisResult(SQLModel, table=True):
    """Synthesized LLM analytical results linked to raw data."""

    __tablename__ = "analysis_result"

    id: int | None = Field(default=None, primary_key=True)
    raw_data_id: int = Field(foreign_key="raw_data.id", index=True, nullable=False)
    pipeline_type: str = Field(
        index=True,
        nullable=False,
        description="Identifier of the downstream pipeline, e.g. finance, market, dummy"
    )
    severity: str = Field(
        index=True,
        nullable=False,
        description="INFO, WARNING, OPPORTUNITY, or CRITICAL"
    )
    summary_title: str = Field(nullable=False)
    detailed_reasoning: str = Field(nullable=False)
    action_items: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False)
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    # Relationships
    raw_data: RawData | None = Relationship(back_populates="analyses")


class MacroMemoryDigest(SQLModel, table=True):
    """
    Sıkıştırılmış Hiyerarşik Makro Bellek Özeti (L2 Compaction Digest).
    Geçmiş ayların veya 90 günlük hareketli periyotların makroekonomik istihbaratını
    yoğunlaştırarak portföy modellerine ve yeni analizlere token yakmadan süreklilik sağlar.
    """

    __tablename__ = "macro_memory_digest"

    id: int | None = Field(default=None, primary_key=True)
    period_key: str = Field(
        unique=True,
        index=True,
        nullable=False,
        description="Dönem kimliği, örn: '2026-06', '2026-07', '2026-08', 'rolling_90d'"
    )
    period_type: str = Field(
        default="monthly",
        index=True,
        nullable=False,
        description="'monthly', 'quarterly' veya 'rolling'"
    )
    period_label: str = Field(
        nullable=False,
        description="Okunabilir Türkçe etiket, örn: 'Haziran 2026 Makroekonomik Bellek Özeti'"
    )
    start_date: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    end_date: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    regime_narrative: str = Field(
        nullable=False,
        description="Sıkıştırılmış makro rejim ve para politikası gidişatı"
    )
    dominant_stance: str = Field(
        default="ŞAHİN",
        index=True,
        nullable=False,
        description="'ŞAHİN', 'GÜVERCİN', 'EKSEN DEĞİŞİMİ' veya 'NÖTR'"
    )
    stance_distribution: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False)
    )
    key_events: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False)
    )
    bist_impact_summary: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False)
    )
    item_count: int = Field(default=0, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

