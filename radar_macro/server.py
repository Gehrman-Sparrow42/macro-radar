"""FastAPI Application Server for Radar Macro Intelligence Terminal."""

import logging
from pathlib import Path
import sys
import threading
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure path resolution
APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent

for p in [str(APP_ROOT), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from radar_core.core.database import (
    get_analysis_results,
    get_engine,
    get_metrics_summary,
    get_session,
    init_db,
)
from radar_macro.config.bist_sectors import map_macro_to_bist_tickers
from radar_macro.config.settings import get_macro_settings, setup_macro_logging
from radar_macro.config.sources import MACRO_SOURCES, get_active_macro_sources
from radar_macro.pipeline import MacroImpactPipeline
from radar_macro.portfolio import (
    compute_tactical_copilot,
    get_user_portfolio_weights,
    save_user_portfolio_weights,
)

setup_macro_logging()
logger = logging.getLogger("radar_macro.server")

settings = get_macro_settings()
get_engine(db_url=settings.DATABASE_URL)
init_db(db_url=settings.DATABASE_URL)

app = FastAPI(
    title="Radar Makro - Türkiye Yatırım İstihbarat Terminali",
    version="2.1.0",
    description="TCMB, Resmî Gazete ve küresel merkez bankalarının Türkiye yatırımlarına etkisi",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = APP_ROOT / "web"
WEB_DIR.mkdir(parents=True, exist_ok=True)

# Ingestion state tracking
ingest_lock = threading.Lock()
ingest_status: dict[str, Any] = {
    "is_running": False,
    "last_run": None,
    "last_stats": None,
    "last_error": None,
}


class IngestRequest(BaseModel):
    category: str | None = None
    jurisdiction: str | None = None
    batch_size: int = 8


class PortfolioUpdateRequest(BaseModel):
    weights: dict[str, float]
    user_key: str = "default_user"


class SettingsUpdateRequest(BaseModel):
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    openai_api_key: str | None = None
    openai_model_reasoning: str | None = None
    openai_model_heavy: str | None = None
    openai_model_fast: str | None = None


class SettingsTestRequest(BaseModel):
    provider: str
    api_key: str | None = None
    model_name: str


def _mask_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 10:
        return "****"
    return f"{key[:7]}...{key[-4:]}"


def _save_env_updates(updates: dict[str, str]) -> None:
    """Updates .env on disk and refreshes running process environment."""
    import os
    env_paths = [PROJECT_ROOT / ".env", APP_ROOT / ".env"]
    primary_env = PROJECT_ROOT / ".env"

    current_lines = []
    if primary_env.exists():
        current_lines = primary_env.read_text(encoding="utf-8").splitlines()

    new_keys = set(updates.keys())
    updated_lines = []
    seen_keys = set()

    for line in current_lines:
        trimmed = line.strip()
        if trimmed and not trimmed.startswith("#") and "=" in trimmed:
            k = trimmed.split("=", 1)[0].strip()
            if k in updates:
                updated_lines.append(f"{k}={updates[k]}")
                seen_keys.add(k)
                continue
        updated_lines.append(line)

    for k, v in updates.items():
        if k not in seen_keys:
            updated_lines.append(f"{k}={v}")

    content = "\n".join(updated_lines) + "\n"
    for p in env_paths:
        try:
            p.write_text(content, encoding="utf-8")
        except Exception as err:
            logger.debug("Writing .env to %s failed: %s", p, err)

    for k, v in updates.items():
        os.environ[k] = v

    # Clear cached settings singletons
    try:
        from radar_macro.config.settings import get_macro_settings
        get_macro_settings.cache_clear()
    except Exception:
        pass
    try:
        from radar_core.config.settings import get_settings
        get_settings.cache_clear()
    except Exception:
        pass



# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/metrics")
def get_metrics() -> dict[str, Any]:
    """Aggregated surveillance metrics and telemetry."""
    with get_session() as session:
        summary = get_metrics_summary(session)

    # Breakdown for jurisdictions & stances
    with get_session() as session:
        all_analyses = get_analysis_results(
            session=session,
            pipeline_type="macro_regulatory",
            limit=300,
        )

    jurisdictions: dict[str, int] = {}
    stances: dict[str, int] = {"ŞAHİN": 0, "GÜVERCİN": 0, "EKSEN DEĞİŞİMİ": 0, "NÖTR": 0}

    for analysis, _ in all_analyses:
        m = analysis.metrics or {}
        jur = m.get("jurisdiction", "Küresel")
        jurisdictions[jur] = jurisdictions.get(jur, 0) + 1

        stn = str(m.get("policy_stance", "NÖTR")).upper()
        if stn in ["ŞAHİN", "HAWKISH"]:
            stances["ŞAHİN"] += 1
        elif stn in ["GÜVERCİN", "DOVISH"]:
            stances["GÜVERCİN"] += 1
        elif stn in ["EKSEN DEĞİŞİMİ", "PIVOT"]:
            stances["EKSEN DEĞİŞİMİ"] += 1
        else:
            stances["NÖTR"] += 1

    summary["jurisdictions"] = jurisdictions
    summary["stances"] = stances
    summary["active_sources_count"] = len(get_active_macro_sources())
    summary["ingest_status"] = ingest_status
    return summary


@app.get("/api/bulletins")
def get_bulletins(
    search: str | None = Query(None, description="Arama terimi"),
    severity: str | None = Query(None, description="Risk derecesi: CRITICAL,WARNING,OPPORTUNITY,INFO"),
    stance: str | None = Query(None, description="Politika duruşu: ŞAHİN,GÜVERCİN,EKSEN DEĞİŞİMİ,NÖTR"),
    jurisdiction: str | None = Query(None, description="Filtre: Türkiye, Küresel veya Tümü"),
    category: str | None = Query(None, description="Kategori filtresi"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> dict[str, Any]:
    """Filtrelenmiş Türkiye odaklı makro istihbarat bültenleri."""
    sev_list = [s.strip().upper() for s in severity.split(",")] if severity else None
    stance_list = [s.strip().upper() for s in stance.split(",")] if stance else None

    with get_session() as session:
        raw_results = get_analysis_results(
            session=session,
            pipeline_type="macro_regulatory",
            severity=sev_list,
            search_term=search,
            limit=350,
        )

    filtered: list[dict[str, Any]] = []
    source_map = {s["source_name"].lower(): s for s in MACRO_SOURCES}

    for analysis, raw in raw_results:
        m = analysis.metrics or {}
        raw_stance = str(m.get("policy_stance", "NÖTR")).upper()

        if raw_stance in ["ŞAHİN", "HAWKISH"]:
            item_stance = "ŞAHİN"
        elif raw_stance in ["GÜVERCİN", "DOVISH"]:
            item_stance = "GÜVERCİN"
        elif raw_stance in ["EKSEN DEĞİŞİMİ", "PIVOT"]:
            item_stance = "EKSEN DEĞİŞİMİ"
        else:
            item_stance = "NÖTR"

        item_jur = m.get("jurisdiction")
        src_meta = source_map.get(raw.source_name.lower(), {})
        if not item_jur:
            item_jur = src_meta.get("jurisdiction", "Küresel")

        item_cat = src_meta.get("category", "Makro Düzenleme")

        # Stance Filter
        if stance_list:
            matched_stance = False
            for s in stance_list:
                if (s in ["ŞAHİN", "HAWKISH"] and item_stance == "ŞAHİN") or \
                   (s in ["GÜVERCİN", "DOVISH"] and item_stance == "GÜVERCİN") or \
                   (s in ["EKSEN DEĞİŞİMİ", "PIVOT"] and item_stance == "EKSEN DEĞİŞİMİ") or \
                   (s in ["NÖTR", "NEUTRAL"] and item_stance == "NÖTR"):
                    matched_stance = True
                    break
            if not matched_stance:
                continue

        # Jurisdiction Filter
        if jurisdiction and jurisdiction.lower() not in ["all", "tümü", ""]:
            is_tr = (item_jur.lower() in ["turkey", "türkiye"]) or m.get("is_turkish", False)
            if jurisdiction.lower() in ["turkey", "türkiye"]:
                if not is_tr:
                    continue
            elif jurisdiction.lower() in ["global", "küresel"]:
                if is_tr:
                    continue
            elif jurisdiction.lower() != item_jur.lower():
                continue

        # Category Filter
        if category and category.lower() not in ["all", "tümü", ""]:
            if category.lower() != item_cat.lower():
                continue

        created_iso = analysis.created_at.isoformat() if analysis.created_at else None

        # BIST Şirket & Sektör Duyarlılık Eşleştirmesi (Kayıtlı veya dinamik fallback)
        bist_tickers = m.get("bist_tickers")
        if not bist_tickers or not bist_tickers.get("favored"):
            is_tr = (item_jur.lower() in ["turkey", "türkiye"]) or m.get("is_turkish", False)
            bist_tickers = map_macro_to_bist_tickers(
                policy_stance=item_stance,
                is_turkish=is_tr,
                category=item_cat,
                text_content=raw.title + " " + (raw.content_text or ""),
            )

        filtered.append({
            "id": analysis.id,
            "raw_id": raw.id,
            "title": analysis.summary_title,
            "raw_title": raw.title,
            "source_name": raw.source_name,
            "url": raw.url,
            "severity": analysis.severity,
            "created_at": created_iso,
            "detailed_reasoning": analysis.detailed_reasoning,
            "action_items": analysis.action_items or [],
            "policy_stance": item_stance,
            "regulatory_urgency": m.get("regulatory_urgency", "İZLEME"),
            "jurisdiction": item_jur,
            "asset_impact": m.get("asset_impact", {}),
            "bist_tickers": bist_tickers,
            "relevance_score": m.get("relevance_score", 85),
            "simple_summary": m.get("simple_summary"),
            "technical_analysis": m.get("technical_analysis"),
            "content_text": raw.content_text,
            "content_hash": raw.content_hash,
            "category": item_cat,
        })

    # Pagination
    total = len(filtered)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = filtered[start_idx:end_idx]

    return {
        "items": paginated,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
    }


@app.get("/api/sources")
def get_sources() -> list[dict[str, Any]]:
    """Tüm yapılandırılmış makro kaynaklar."""
    return MACRO_SOURCES


@app.get("/api/portfolio")
def get_portfolio(user_key: str = "default_user") -> dict[str, Any]:
    """Portföy taktiksel varlık dağılımı ve 'Şundan Çık ➔ Şuna Geç' yönlendirmeleri."""
    weights = get_user_portfolio_weights(user_key=user_key)
    return compute_tactical_copilot(current_weights=weights)


@app.post("/api/portfolio")
def update_portfolio(payload: PortfolioUpdateRequest) -> dict[str, Any]:
    """Kullanıcının portföy ağırlıklarını günceller ve yeni taktiksel öneri üretir."""
    saved_weights = save_user_portfolio_weights(weights=payload.weights, user_key=payload.user_key)
    return compute_tactical_copilot(current_weights=saved_weights)


@app.get("/api/memory")
def get_memory_digests() -> list[dict[str, Any]]:
    """Geçmiş ayların sıkıştırılmış makro bellek özetlerini döndürür."""
    from radar_macro.memory_engine import list_memory_digests
    return list_memory_digests()


@app.post("/api/memory/compact")
def trigger_memory_compaction(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Arka planda geçmiş ayların bellek sıkıştırmasını tetikler."""
    from radar_macro.backfill import run_historical_backfill
    background_tasks.add_task(run_historical_backfill)
    return {"status": "started", "message": "Aylık makro bellek derleme döngüsü başlatıldı."}


# ---------------------------------------------------------------------------
# In-App Dynamic LLM & API Key Configuration Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/settings")
def get_runtime_settings() -> dict[str, Any]:
    """Uygulama içerisinden dinamik olarak modelleri ve API anahtar durumlarını okur."""
    s = get_macro_settings()
    return {
        "gemini_api_key_masked": _mask_key(s.GEMINI_API_KEY),
        "gemini_api_key_set": bool(s.GEMINI_API_KEY and len(s.GEMINI_API_KEY) > 5),
        "gemini_model": s.GEMINI_MODEL,
        "openai_api_key_masked": _mask_key(s.OPENAI_API_KEY),
        "openai_api_key_set": bool(s.OPENAI_API_KEY and len(s.OPENAI_API_KEY) > 5),
        "openai_model_reasoning": s.OPENAI_MODEL_REASONING,
        "openai_model_heavy": s.OPENAI_MODEL_HEAVY,
        "openai_model_fast": s.OPENAI_MODEL_FAST,
        "recommendations": {
            "gemini_news": [
                {"id": "gemini-flash-latest", "label": "Gemini Flash (Varsayılan - Hızlı & Ücretsiz Kotası Yüksek)", "badge": "Tavsiye"},
                {"id": "gemini-2.0-flash", "label": "Gemini 2.0 Flash (En Güncel Flash Modeli)", "badge": "Yeni"},
                {"id": "gemini-2.0-pro-exp", "label": "Gemini 2.0 Pro Exp (Yüksek Muhakeme)", "badge": "Deneysel"},
            ],
            "openai_reasoning": [
                {"id": "o3", "label": "OpenAI o3 (En Üst Düzey Tam Sıklet Muhakeme Amiral Gemisi)", "badge": "Yeni Nesil Amiral"},
                {"id": "o1", "label": "OpenAI o1 (Derin Muhakeme & WACC - 100K+ İçin Önerilen)", "badge": "Güvenilir Amiral"},
                {"id": "o3-mini", "label": "OpenAI o3-mini (Yüksek Hızlı STEM/Matematik CoT)", "badge": "Hızlı Düşünce"},
                {"id": "gpt-4o", "label": "OpenAI GPT-4o (Amiral Gemisi Genel Analitik)", "badge": "Klasik Amiral"},
                {"id": "gpt-5", "label": "OpenAI GPT-5 (Doğrulanmış Hesaplar)", "badge": "Gelecek Nesil"},
            ],
            "openai_fast": [
                {"id": "gpt-4o-mini", "label": "GPT-4o-mini (Düşük Maliyetli Failover)", "badge": "Yedek"},
                {"id": "gpt-4o", "label": "GPT-4o (Güçlü Yedek)", "badge": "Ağır"},
            ],
        },
    }


@app.post("/api/settings")
def update_runtime_settings(payload: SettingsUpdateRequest) -> dict[str, Any]:
    """API anahtarlarını ve model tercihlerini canlı günceller ve .env dosyasına yazar."""
    updates: dict[str, str] = {}
    current_settings = get_macro_settings()

    if payload.gemini_api_key and "..." not in payload.gemini_api_key and "****" not in payload.gemini_api_key:
        updates["GEMINI_API_KEY"] = payload.gemini_api_key.strip()
    if payload.gemini_model:
        updates["GEMINI_MODEL"] = payload.gemini_model.strip()

    if payload.openai_api_key and "..." not in payload.openai_api_key and "****" not in payload.openai_api_key:
        updates["OPENAI_API_KEY"] = payload.openai_api_key.strip()
    if payload.openai_model_reasoning:
        updates["OPENAI_MODEL_REASONING"] = payload.openai_model_reasoning.strip()
    if payload.openai_model_heavy:
        updates["OPENAI_MODEL_HEAVY"] = payload.openai_model_heavy.strip()
    if payload.openai_model_fast:
        updates["OPENAI_MODEL_FAST"] = payload.openai_model_fast.strip()

    if updates:
        _save_env_updates(updates)
        logger.info("Runtime settings dynamically updated: %s", list(updates.keys()))

    return {
        "status": "success",
        "message": "Ayarlar başarıyla kaydedildi ve çalışma zamanına anında uygulandı.",
        "updated_keys": list(updates.keys()),
        "current": get_runtime_settings(),
    }


@app.post("/api/settings/test")
def test_runtime_credentials(payload: SettingsTestRequest) -> dict[str, Any]:
    """Belirtilen API anahtarı ve modelin canlı bağlantısını test eder."""
    current_settings = get_macro_settings()
    key = payload.api_key
    if not key or "..." in key or "****" in key:
        if payload.provider.lower() == "gemini":
            key = current_settings.GEMINI_API_KEY
        else:
            key = current_settings.OPENAI_API_KEY

    from radar_core.core.llm_engine import LLMEngine
    return LLMEngine.test_connection(
        provider=payload.provider,
        api_key=key or "",
        model_name=payload.model_name,
    )



def _run_ingest_worker(category: str | None, jurisdiction: str | None, batch_size: int) -> None:
    """Arka planda veri çekme ve Türkiye odaklı analiz işçisi."""
    global ingest_status
    with ingest_lock:
        ingest_status["is_running"] = True
        ingest_status["last_error"] = None
        try:
            pipeline = MacroImpactPipeline()
            sources = pipeline.get_sources(category=category, jurisdiction=jurisdiction)
            for s in sources:
                s["limit"] = batch_size

            stats = pipeline.run(source_configs=sources, batch_size=batch_size * 2)
            # Bekleyen kuyruk öğelerini de erit
            extra_stats = pipeline.process_queue(batch_size=batch_size * 2)
            stats["processing"]["evaluated"] += extra_stats.get("evaluated", 0)
            stats["processing"]["analyzed"] += extra_stats.get("analyzed", 0)
            stats["processing"]["prefiltered_skipped"] += extra_stats.get("prefiltered_skipped", 0)

            import datetime
            ingest_status["last_run"] = datetime.datetime.now().isoformat()
            ingest_status["last_stats"] = stats
        except Exception as exc:
            logger.error("İstihbarat çekme hatası: %s", exc)
            ingest_status["last_error"] = str(exc)
        finally:
            ingest_status["is_running"] = False


@app.post("/api/ingest")
def trigger_ingest(
    req: IngestRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """İstihbarat çekme ve analiz döngüsünü tetikler."""
    if ingest_status["is_running"]:
        return {
            "status": "already_running",
            "message": "Halen arka planda devam eden aktif bir istihbarat döngüsü mevcut.",
        }

    background_tasks.add_task(
        _run_ingest_worker,
        category=req.category,
        jurisdiction=req.jurisdiction,
        batch_size=req.batch_size,
    )

    return {
        "status": "started",
        "message": "Türkiye ve küresel akışlar üzerinden istihbarat tarama döngüsü başlatıldı.",
    }


# ---------------------------------------------------------------------------
# Statik Web Arayüz Sunumu
# ---------------------------------------------------------------------------

if (WEB_DIR / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/")
    def serve_root():
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/{full_path:path}")
    def serve_static_fallback(full_path: str):
        target_file = WEB_DIR / full_path
        if target_file.is_file():
            return FileResponse(target_file)
        return FileResponse(WEB_DIR / "index.html")
