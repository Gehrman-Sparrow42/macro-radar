"""Radar Makro: Hiyerarşik Bellek ve Sıkıştırma (Memory & Compaction) Motoru.

Geçmiş ayların bülten, tebliğ ve karar analizlerini yoğunlaştırarak token yakmadan
yeni analizlere ve portföy copilotuna zamansal süreklilik kazandırır.
"""

from datetime import datetime, timezone
import logging
from typing import Any
from sqlmodel import Session, col, desc, select

from radar_core.core.database import get_engine, get_session, save_memory_digest
from radar_core.core.llm_engine import LLMEngine
from radar_core.core.models import AnalysisResult, MacroMemoryDigest, RawData

logger = logging.getLogger("radar_macro.memory_engine")

MONTH_NAMES_TR = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
}


def generate_period_digest(
    start_date: datetime,
    end_date: datetime,
    period_key: str,
    period_label: str | None = None,
    period_type: str = "monthly",
    session: Session | None = None,
    llm_engine: LLMEngine | None = None,
) -> MacroMemoryDigest:
    """
    Belirli bir tarih aralığındaki (örn. 1 ay veya 90 gün) tüm makro analizleri
    toplar, istatistiklerini çıkarır ve LLM ile sıkıştırılmış kalıcı bellek özeti üretir.
    """
    close_session = False
    if session is None:
        session = Session(get_engine())
        close_session = True

    try:
        stmt = (
            select(AnalysisResult, RawData)
            .join(RawData, AnalysisResult.raw_data_id == RawData.id)
            .where(AnalysisResult.pipeline_type == "macro_regulatory")
            .where(AnalysisResult.created_at >= start_date)
            .where(AnalysisResult.created_at <= end_date)
            .order_by(desc(AnalysisResult.created_at))
        )
        results = session.exec(stmt).all()

        total_items = len(results)
        hawkish_count = 0
        dovish_count = 0
        pivot_count = 0
        neutral_count = 0

        favored_tickers: dict[str, int] = {}
        pressured_tickers: dict[str, int] = {}
        key_events: list[dict[str, Any]] = []

        for analysis, raw in results:
            m = analysis.metrics or {}
            stance = str(m.get("policy_stance", "NÖTR")).upper()
            if stance in ["ŞAHİN", "HAWKISH"]:
                hawkish_count += 1
            elif stance in ["GÜVERCİN", "DOVISH"]:
                dovish_count += 1
            elif stance in ["EKSEN DEĞİŞİMİ", "PIVOT"]:
                pivot_count += 1
            else:
                neutral_count += 1

            # BIST Ticker mentions
            bist = m.get("bist_tickers", {})
            for t in bist.get("favored", []):
                sym = t.get("ticker") if isinstance(t, dict) else str(t)
                if sym and len(sym) < 25:
                    favored_tickers[sym] = favored_tickers.get(sym, 0) + 1
            for t in bist.get("pressured", []):
                sym = t.get("ticker") if isinstance(t, dict) else str(t)
                if sym and len(sym) < 25:
                    pressured_tickers[sym] = pressured_tickers.get(sym, 0) + 1

            # Key critical events
            if analysis.severity in ["CRITICAL", "OPPORTUNITY"] or len(key_events) < 5:
                key_events.append({
                    "title": analysis.summary_title,
                    "severity": analysis.severity,
                    "date": analysis.created_at.strftime("%Y-%m-%d"),
                    "source": raw.source_name,
                    "stance": stance,
                })

        safe_total = total_items if total_items > 0 else 1
        hawkish_pct = round((hawkish_count / safe_total) * 100, 1)
        dovish_pct = round((dovish_count / safe_total) * 100, 1)
        pivot_pct = round((pivot_count / safe_total) * 100, 1)
        neutral_pct = round((neutral_count / safe_total) * 100, 1)

        # Dominant Stance
        if pivot_pct >= 25:
            dominant_stance = "EKSEN DEĞİŞİMİ"
        elif hawkish_pct >= 40:
            dominant_stance = "ŞAHİN"
        elif dovish_pct >= 40:
            dominant_stance = "GÜVERCİN"
        else:
            dominant_stance = "NÖTR"

        # Label fallback
        if not period_label:
            period_label = f"{period_key} Makro Bellek Özeti"

        # Sort BIST impact
        sorted_favored = sorted(favored_tickers.items(), key=lambda x: x[1], reverse=True)[:5]
        sorted_pressured = sorted(pressured_tickers.items(), key=lambda x: x[1], reverse=True)[:5]
        bist_summary = {
            "top_favored": [t[0] for t in sorted_favored],
            "top_pressured": [t[0] for t in sorted_pressured],
            "favored_counts": dict(sorted_favored),
            "pressured_counts": dict(sorted_pressured),
        }

        # Sıkıştırılmış Makro Anlatı (Regime Narrative)
        regime_narrative = (
            f"{period_label} döneminde toplam {total_items} makro istihbarat maddesi işlendi. "
            f"Döneme damgasını vuran ana eğilim %{hawkish_pct} oranında {dominant_stance} duruş oldu. "
        )

        if dominant_stance == "ŞAHİN":
            regime_narrative += (
                "TCMB pozitif reel faiz kararlılığı ve zorunlu karşılık adımlarıyla piyasa likiditesini sterilize etti. "
                "TL mevduat ve para piyasası fonları risksiz yüksek getiriyle öne çıkarken, "
                "yüksek borçlu sanayi şirketleri finansman baskısıyla geriledi."
            )
        elif dominant_stance == "GÜVERCİN":
            regime_narrative += (
                "Genişlemeci para politikası adımları ve likidite enjeksiyonu getiri eğrisini normalleştirdi. "
                "Faiz düşüşü beklentileriyle BIST lokomotif hisseleri ve gayrimenkul sektörü talep gördü."
            )
        elif dominant_stance == "EKSEN DEĞİŞİMİ":
            regime_narrative += (
                "Olağanüstü düzenleme ve küresel şoklar nedeniyle volatilite yükseldi; "
                "defansif döviz ve altın pozisyonları değer kazandı."
            )
        else:
            regime_narrative += (
                "Makro dengeler koridor içinde seyretti, varlıklar arasında belirgin bir ayrışma yaşanmadı."
            )

        # AI Synthesis (Opsiyonel Derinleştirme)
        if llm_engine is None:
            try:
                llm_engine = LLMEngine()
            except Exception:
                pass

        if llm_engine and (getattr(llm_engine, "gemini_api_key", None) or getattr(llm_engine, "openai_api_key", None)) and total_items > 0:
            try:
                event_titles = [e["title"] for e in key_events[:4]]
                prompt_compaction = (
                    f"Dönem: {period_label}\n"
                    f"İncelenen Karar Sayısı: {total_items}\n"
                    f"Duruş Dağılımı: Şahin %{hawkish_pct}, Güvercin %{dovish_pct}, Eksen Değişimi %{pivot_pct}\n"
                    f"Öne Çıkan Kararlar:\n" + "\n".join(f"- {t}" for t in event_titles) + "\n\n"
                    f"GÖREV: Bu dönemin Türk piyasaları (BIST, TL Faiz, Kur) üzerindeki kalıcı makro mirasını "
                    f"en fazla 3-4 vurucu Türkçe cümleyle özetle. JSON döndür: summary_title, detailed_reasoning."
                )
                ai_out = llm_engine.analyze_structured(prompt=prompt_compaction, task_type="news_analysis")
                if ai_out.detailed_reasoning and len(ai_out.detailed_reasoning) > 40:
                    regime_narrative = ai_out.detailed_reasoning
            except Exception as e:
                logger.debug("LLM memory compaction skipped, using rule-based narrative: %s", e)

        digest = MacroMemoryDigest(
            period_key=period_key,
            period_type=period_type,
            period_label=period_label,
            start_date=start_date,
            end_date=end_date,
            regime_narrative=regime_narrative,
            dominant_stance=dominant_stance,
            stance_distribution={
                "hawkish_pct": hawkish_pct,
                "dovish_pct": dovish_pct,
                "pivot_pct": pivot_pct,
                "neutral_pct": neutral_pct,
            },
            key_events=key_events[:5],
            bist_impact_summary=bist_summary,
            item_count=total_items,
            updated_at=datetime.now(timezone.utc),
        )

        saved = save_memory_digest(session, digest)
        logger.info("MacroMemoryDigest successfully saved for '%s' (%d items).", period_key, total_items)
        return saved
    finally:
        if close_session:
            session.close()


def get_active_memory_context(months: int = 6) -> str:
    """
    Portföy copilotuna veya yeni bülten analizlerine enjekte edilmek üzere
    son 6 ayın sıkıştırılmış makro bellek özetini üretir (~500-750 token).
    Bu sayede binlerce sayfalık eski haber yerine sadece damıtılmış bilgi modele aktarılır.
    """
    with get_session() as session:
        stmt = (
            select(MacroMemoryDigest)
            .where(MacroMemoryDigest.period_type == "monthly")
            .order_by(col(MacroMemoryDigest.start_date).desc())
            .limit(months)
        )
        digests = session.exec(stmt).all()

    if not digests:
        with get_session() as session:
            stmt = select(MacroMemoryDigest).order_by(col(MacroMemoryDigest.start_date).desc()).limit(months)
            digests = session.exec(stmt).all()

    if not digests:
        return "Geçmiş dönem makro bellek kaydı bulunmamaktadır."

    # Kronolojik olarak eskiden yeniye doğru sırala
    digests = sorted(digests, key=lambda d: d.start_date)

    lines = ["--- KURUMSAL MAKRO BELLEK & GEÇMİŞ 6 AYLIK POLİTİKA MİRASI (L2 COMPACTION) ---"]
    for d in digests:
        stats = d.stance_distribution or {}
        hwk = stats.get("hawkish_pct", 0)
        fav = ", ".join(d.bist_impact_summary.get("top_favored", [])[:3])
        prs = ", ".join(d.bist_impact_summary.get("top_pressured", [])[:3])

        bist_line = ""
        if fav or prs:
            bist_line = f" | BIST Etkisi: [Pozitif: {fav or '-'}] [Baskılı: {prs or '-'}]"

        lines.append(
            f"• [{d.period_label}] (Baskın Duruş: {d.dominant_stance}, Sıkılaşma: %{hwk:.0f}{bist_line}):\n"
            f"  {d.regime_narrative}"
        )
    lines.append("--------------------------------------------------------------------------------")
    return "\n".join(lines)


def list_memory_digests() -> list[dict[str, Any]]:
    """Tüm kayıtlı bellek özetlerini API ve UI için JSON formatında döndürür."""
    with get_session() as session:
        stmt = select(MacroMemoryDigest).order_by(col(MacroMemoryDigest.start_date).desc())
        items = session.exec(stmt).all()

    results = []
    for d in items:
        results.append({
            "id": d.id,
            "period_key": d.period_key,
            "period_type": d.period_type,
            "period_label": d.period_label,
            "start_date": d.start_date.isoformat() if d.start_date else None,
            "end_date": d.end_date.isoformat() if d.end_date else None,
            "regime_narrative": d.regime_narrative,
            "dominant_stance": d.dominant_stance,
            "stance_distribution": d.stance_distribution,
            "key_events": d.key_events,
            "bist_impact_summary": d.bist_impact_summary,
            "item_count": d.item_count,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        })
    return results
