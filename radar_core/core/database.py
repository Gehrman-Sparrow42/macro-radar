"""Database engine, session management, and repository operations for radar_core."""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from sqlalchemy import desc, func
from sqlmodel import Session, SQLModel, create_engine, select

from radar_core.config.settings import get_settings
from radar_core.core.models import (
    AgentStrategyMemo,
    AnalysisResult,
    MacroMemoryDigest,
    RawData,
    RawItem,
    compute_content_hash,
)

logger = logging.getLogger("radar_core.database")

_engine = None


def get_engine(db_url: str | None = None):
    """Retrieve or initialize SQLModel engine with thread-safe settings for SQLite."""
    global _engine
    if _engine is None or db_url is not None:
        target_url = db_url or get_settings().DATABASE_URL
        connect_args = {}
        if target_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        _engine = create_engine(
            target_url,
            echo=False,
            connect_args=connect_args,
        )
    return _engine


def init_db(db_url: str | None = None) -> None:
    """Initialize SQLite database tables defined in SQLModel."""
    engine = get_engine(db_url)
    SQLModel.metadata.create_all(engine)
    logger.info("Database schema initialized successfully.")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session scope."""
    engine = get_engine()
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


# ---------------------------------------------------------------------------
# Repository Operations
# ---------------------------------------------------------------------------

def save_raw_item(session: Session, item: RawItem) -> tuple[RawData, bool]:
    """
    Persist a raw ingested item if its canonical SHA-256 hash is novel.
    Returns (RawData, is_new: bool).
    Guarantees strict deduplication without throwing duplicate key exceptions.
    """
    c_hash = compute_content_hash(item.content_text)

    # Check for existing record by unique content_hash
    existing = session.exec(
        select(RawData).where(RawData.content_hash == c_hash)
    ).first()

    if existing:
        logger.debug(
            "Duplicate item skipped: [source=%s, hash=%s, title=%s]",
            item.source_name,
            c_hash[:8],
            item.title[:40],
        )
        return existing, False

    raw_record = RawData(
        source_name=item.source_name,
        url=item.url,
        title=item.title,
        content_text=item.content_text,
        content_hash=c_hash,
        is_processed=False,
    )
    session.add(raw_record)
    session.commit()
    session.refresh(raw_record)

    logger.info(
        "Ingested new item: [id=%d, source=%s, title=%s]",
        raw_record.id,
        raw_record.source_name,
        raw_record.title[:40],
    )
    return raw_record, True


def get_unprocessed_raw_data(
    session: Session,
    limit: int = 50,
    source_name: str | None = None,
) -> list[RawData]:
    """Retrieve queue of unprocessed raw documents."""
    query = select(RawData).where(RawData.is_processed == False)  # noqa: E712
    if source_name:
        query = query.where(RawData.source_name == source_name)
    query = query.order_by(RawData.fetched_at).limit(limit)
    return list(session.exec(query).all())


def mark_as_processed(session: Session, raw_data_id: int) -> None:
    """Flag a RawData entry as successfully processed by pipeline."""
    record = session.get(RawData, raw_data_id)
    if record:
        record.is_processed = True
        session.add(record)
        session.commit()


def save_analysis_result(session: Session, result: AnalysisResult) -> AnalysisResult:
    """Persist an LLM analysis result and commit."""
    session.add(result)
    session.commit()
    session.refresh(result)
    logger.info(
        "Saved analysis result: [id=%d, severity=%s, pipeline=%s]",
        result.id,
        result.severity,
        result.pipeline_type,
    )
    return result


def get_analysis_results(
    session: Session,
    pipeline_type: str | None = None,
    severity: str | list[str] | None = None,
    search_term: str | None = None,
    limit: int = 100,
) -> list[tuple[AnalysisResult, RawData]]:
    """Query analysis results joined with original raw data with optional filtering."""
    query = (
        select(AnalysisResult, RawData)
        .join(RawData, AnalysisResult.raw_data_id == RawData.id)
        .order_by(desc(AnalysisResult.created_at))
    )

    if pipeline_type:
        query = query.where(AnalysisResult.pipeline_type == pipeline_type)

    if severity:
        if isinstance(severity, list):
            if severity:
                query = query.where(AnalysisResult.severity.in_(severity))
        else:
            query = query.where(AnalysisResult.severity == severity)

    if search_term and search_term.strip():
        term = f"%{search_term.strip()}%"
        query = query.where(
            (AnalysisResult.summary_title.ilike(term))
            | (AnalysisResult.detailed_reasoning.ilike(term))
            | (RawData.title.ilike(term))
            | (RawData.source_name.ilike(term))
            | (RawData.content_text.ilike(term))
        )

    results = session.exec(query.limit(limit)).all()
    return list(results)


def get_metrics_summary(session: Session) -> dict[str, Any]:
    """Calculate aggregate counts for dashboard metric cards."""
    total_raw = session.exec(select(func.count(RawData.id))).one() or 0
    total_processed = session.exec(
        select(func.count(RawData.id)).where(RawData.is_processed == True)  # noqa: E712
    ).one() or 0
    total_analyses = session.exec(select(func.count(AnalysisResult.id))).one() or 0

    severity_counts = {}
    for sev in ["CRITICAL", "OPPORTUNITY", "WARNING", "INFO"]:
        cnt = session.exec(
            select(func.count(AnalysisResult.id)).where(AnalysisResult.severity == sev)
        ).one() or 0
        severity_counts[sev] = cnt

    sources = session.exec(
        select(RawData.source_name, func.count(RawData.id)).group_by(RawData.source_name)
    ).all()

    return {
        "total_raw": total_raw,
        "total_processed": total_processed,
        "total_pending": total_raw - total_processed,
        "total_analyses": total_analyses,
        "critical_count": severity_counts.get("CRITICAL", 0),
        "opportunity_count": severity_counts.get("OPPORTUNITY", 0),
        "warning_count": severity_counts.get("WARNING", 0),
        "info_count": severity_counts.get("INFO", 0),
        "sources": {src: cnt for src, cnt in sources},
    }


def save_memory_digest(session: Session, digest: MacroMemoryDigest) -> MacroMemoryDigest:
    """Save or update a MacroMemoryDigest record."""
    existing = session.exec(
        select(MacroMemoryDigest).where(MacroMemoryDigest.period_key == digest.period_key)
    ).first()

    if existing:
        existing.period_label = digest.period_label
        existing.start_date = digest.start_date
        existing.end_date = digest.end_date
        existing.regime_narrative = digest.regime_narrative
        existing.dominant_stance = digest.dominant_stance
        existing.stance_distribution = digest.stance_distribution
        existing.key_events = digest.key_events
        existing.bist_impact_summary = digest.bist_impact_summary
        existing.item_count = digest.item_count
        existing.updated_at = digest.updated_at
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    session.add(digest)
    session.commit()
    session.refresh(digest)
    return digest


def get_all_memory_digests(
    session: Session,
    limit: int = 12,
) -> list[MacroMemoryDigest]:
    """Retrieve historical memory digests ordered chronologically or by start_date descending."""
    stmt = select(MacroMemoryDigest).order_by(desc(MacroMemoryDigest.start_date)).limit(limit)
    return list(session.exec(stmt).all())


def save_agent_memo(session: Session, memo: AgentStrategyMemo) -> AgentStrategyMemo:
    """Save a new AgentStrategyMemo record."""
    session.add(memo)
    session.commit()
    session.refresh(memo)
    return memo


def get_latest_agent_memo(session: Session) -> AgentStrategyMemo | None:
    """Retrieve the most recent AgentStrategyMemo."""
    stmt = select(AgentStrategyMemo).order_by(desc(AgentStrategyMemo.created_at)).limit(1)
    return session.exec(stmt).first()


def get_all_agent_memos(session: Session, limit: int = 5) -> list[AgentStrategyMemo]:
    """Retrieve recent AgentStrategyMemos."""
    stmt = select(AgentStrategyMemo).order_by(desc(AgentStrategyMemo.created_at)).limit(limit)
    return list(session.exec(stmt).all())

