"""Portfolio & Tactical Asset Allocation Copilot.
Makroekonomik istihbarat akışına göre 'Şundan çık, şuna geç' varlık dağılımı ve BIST hisse yönlendirmesi üretir.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any

from sqlmodel import Column, DateTime, Field, SQLModel, Text

from radar_core.core.database import get_analysis_results, get_session, get_engine
from radar_macro.config.bist_sectors import BIST_COMPANIES
from radar_macro.config.settings import get_macro_settings

logger = logging.getLogger("radar_macro.portfolio")

# ---------------------------------------------------------------------------
# Default Weights & Asset Classes
# ---------------------------------------------------------------------------
DEFAULT_PORTFOLIO_WEIGHTS: dict[str, float] = {
    "bist": 35.0,        # Borsa İstanbul Hisse Senetleri
    "mevduat": 30.0,     # TL Mevduat & Para Piyasası Fonu (PPF)
    "doviz": 15.0,       # Dolar / Euro Nakit & KKM
    "dibs": 10.0,        # TL Devlet Tahvili (DİBS) & Hazine Eurobond
    "altin": 10.0,       # Gram Altın / Fiziki Altın
}

ASSET_LABELS: dict[str, str] = {
    "bist": "BIST Hisse Senetleri",
    "mevduat": "TL Mevduat & PPF",
    "doviz": "Döviz (USD/EUR)",
    "dibs": "DİBS & Eurobond",
    "altin": "Gram Altın",
}

# ---------------------------------------------------------------------------
# Database Model for Saved User Portfolio
# ---------------------------------------------------------------------------
class PortfolioSettings(SQLModel, table=True):
    __tablename__ = "portfolio_settings"

    id: int | None = Field(default=None, primary_key=True)
    user_key: str = Field(default="default_user", index=True, sa_column_kwargs={"unique": True})
    weights_json: str = Field(sa_column=Column(Text, nullable=False))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


def _ensure_tables_exist() -> None:
    try:
        engine = get_engine(get_macro_settings().DATABASE_URL)
        SQLModel.metadata.create_all(engine)
    except Exception as exc:
        logger.debug("Table check: %s", exc)


def get_user_portfolio_weights(user_key: str = "default_user") -> dict[str, float]:
    """Kullanıcının kayıtlı portföy ağırlıklarını getirir."""
    _ensure_tables_exist()
    with get_session() as session:
        row = session.query(PortfolioSettings).filter_by(user_key=user_key).first()
        if row and row.weights_json:
            try:
                saved = json.loads(row.weights_json)
                weights = {}
                for k in DEFAULT_PORTFOLIO_WEIGHTS:
                    weights[k] = float(saved.get(k, DEFAULT_PORTFOLIO_WEIGHTS[k]))
                return weights
            except Exception as exc:
                logger.warning("Error parsing saved weights: %s", exc)
    return dict(DEFAULT_PORTFOLIO_WEIGHTS)


def save_user_portfolio_weights(weights: dict[str, float], user_key: str = "default_user") -> dict[str, float]:
    """Kullanıcının portföy ağırlıklarını kaydeder ve normalize eder."""
    # Toplamın 100 olmasını sağla
    clean_weights = {}
    total = sum(float(weights.get(k, 0.0)) for k in DEFAULT_PORTFOLIO_WEIGHTS)
    if total <= 0:
        clean_weights = dict(DEFAULT_PORTFOLIO_WEIGHTS)
    else:
        for k in DEFAULT_PORTFOLIO_WEIGHTS:
            val = float(weights.get(k, 0.0))
            clean_weights[k] = round((val / total) * 100.0, 1)

    with get_session() as session:
        row = session.query(PortfolioSettings).filter_by(user_key=user_key).first()
        if not row:
            row = PortfolioSettings(
                user_key=user_key,
                weights_json=json.dumps(clean_weights),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(row)
        else:
            row.weights_json = json.dumps(clean_weights)
            row.updated_at = datetime.now(timezone.utc)
        session.commit()

    return clean_weights


# ---------------------------------------------------------------------------
# Tactical Allocation & Rebalancing Algorithm
# ---------------------------------------------------------------------------
def compute_tactical_copilot(
    current_weights: dict[str, float] | None = None,
    limit: int = 40,
) -> dict[str, Any]:
    """
    Son makroekonomik gelişmeleri (TCMB, Resmî Gazete, Fed, vb.) analiz ederek
    kullanıcının mevcut portföyüne özel 'Şundan Çık ➔ Şuna Geç' yönlendirmesi üretir.
    """
    if not current_weights:
        current_weights = get_user_portfolio_weights()

    # 1. Son analiz sonuçlarını çek ve makro rejimi belirle
    with get_session() as session:
        recent_analyses = get_analysis_results(
            session=session,
            pipeline_type="macro_regulatory",
            limit=limit,
        )

    hawkish_count = 0
    dovish_count = 0
    pivot_count = 0
    neutral_count = 0
    turkish_news_count = 0

    bist_favored_mentions: dict[str, int] = {}
    bist_pressured_mentions: dict[str, int] = {}

    for analysis, raw in recent_analyses:
        m = analysis.metrics or {}
        stn = str(m.get("policy_stance", "NÖTR")).upper()
        if stn in ["ŞAHİN", "HAWKISH"]:
            hawkish_count += 1
        elif stn in ["GÜVERCİN", "DOVISH"]:
            dovish_count += 1
        elif stn in ["EKSEN DEĞİŞİMİ", "PIVOT"]:
            pivot_count += 1
        else:
            neutral_count += 1

        if m.get("is_turkish", False) or "turkey" in str(m.get("jurisdiction", "")).lower():
            turkish_news_count += 1

    total_signals = hawkish_count + dovish_count + pivot_count + neutral_count
    if total_signals == 0:
        total_signals = 1

    hawkish_pct = (hawkish_count / total_signals) * 100
    dovish_pct = (dovish_count / total_signals) * 100
    pivot_pct = (pivot_count / total_signals) * 100

    # 2. Makro Rejim Teşhisi
    if pivot_pct >= 20:
        regime = "Yüksek Volatilite & Küresel Eksen Değişimi"
        regime_code = "PIVOT_HIGH_VOLATILITY"
        target_weights = {
            "bist": 20.0,
            "mevduat": 35.0,
            "doviz": 20.0,
            "dibs": 10.0,
            "altin": 15.0,
        }
    elif hawkish_pct >= 40:
        regime = "Sıkı Para Politikası & Cazip TL Reel Getirisi (TCMB Şahin)"
        regime_code = "TIGHT_MONEY_HIGH_TL_YIELD"
        target_weights = {
            "bist": 25.0,
            "mevduat": 45.0,
            "doviz": 10.0,
            "dibs": 10.0,
            "altin": 10.0,
        }
    elif dovish_pct >= 40:
        regime = "Parasal Genişleme & Risk İştahı (BIST Rallisi Destekli)"
        regime_code = "EASING_RISK_ON"
        target_weights = {
            "bist": 50.0,
            "mevduat": 20.0,
            "doviz": 10.0,
            "dibs": 10.0,
            "altin": 10.0,
        }
    else:
        regime = "Dengeli Makro Denge & Seçici Sektörel Fırsatlar"
        regime_code = "BALANCED_MACRO"
        target_weights = {
            "bist": 35.0,
            "mevduat": 30.0,
            "doviz": 15.0,
            "dibs": 10.0,
            "altin": 10.0,
        }

    # 3. 'Şundan Çık, Şuna Geç' Delta Hesaplaması
    diffs: dict[str, float] = {}
    for k in DEFAULT_PORTFOLIO_WEIGHTS:
        curr = current_weights.get(k, DEFAULT_PORTFOLIO_WEIGHTS[k])
        tgt = target_weights[k]
        diffs[k] = round(tgt - curr, 1)

    # Azaltılacaklar (Negatif fark) ve Artırılacaklar (Pozitif fark)
    reduce_list = [(k, abs(diffs[k])) for k in diffs if diffs[k] <= -2.0]
    reduce_list.sort(key=lambda x: x[1], reverse=True)

    increase_list = [(k, diffs[k]) for k in diffs if diffs[k] >= 2.0]
    increase_list.sort(key=lambda x: x[1], reverse=True)

    # 4. Somut Taktiksel Hamleler Listesi ("Şundan Çık ➔ Şuna Geç")
    tactical_actions: list[dict[str, Any]] = []

    if reduce_list and increase_list:
        from_asset, from_amt = reduce_list[0]
        to_asset, to_amt = increase_list[0]
        alloc_move = min(from_amt, to_amt)

        tactical_actions.append({
            "action_type": "REALLOCATE",
            "from_class": from_asset,
            "from_label": ASSET_LABELS[from_asset],
            "to_class": to_asset,
            "to_label": ASSET_LABELS[to_asset],
            "transfer_pct": alloc_move,
            "headline": f"🔴 {ASSET_LABELS[from_asset]} %{alloc_move:.0f} Azaltın ➔ 🟢 {ASSET_LABELS[to_asset]} %{alloc_move:.0f} Artırın",
            "instruction": (
                f"Mevcut {ASSET_LABELS[from_asset]} pozisyonunuzdan yaklaşık %{alloc_move:.0f} kâr satışı/çıkış yaparak "
                f"açığa çıkan nakdi %{alloc_move:.0f} oranında {ASSET_LABELS[to_asset]} tarafına aktarınız."
            ),
        })

    # İkinci ikili hamle (varsa)
    if len(reduce_list) > 1 or len(increase_list) > 1:
        sec_from = reduce_list[1] if len(reduce_list) > 1 else reduce_list[0]
        sec_to = increase_list[1] if len(increase_list) > 1 else increase_list[0]
        sec_amt = min(sec_from[1], sec_to[1])
        if sec_amt >= 2.0 and (sec_from[0] != reduce_list[0][0] or sec_to[0] != increase_list[0][0]):
            tactical_actions.append({
                "action_type": "REALLOCATE",
                "from_class": sec_from[0],
                "from_label": ASSET_LABELS[sec_from[0]],
                "to_class": sec_to[0],
                "to_label": ASSET_LABELS[sec_to[0]],
                "transfer_pct": sec_amt,
                "headline": f"🔴 {ASSET_LABELS[sec_from[0]]} %{sec_amt:.0f} Azaltın ➔ 🟢 {ASSET_LABELS[sec_to[0]]} %{sec_amt:.0f} Artırın",
                "instruction": (
                    f"{ASSET_LABELS[sec_from[0]]} ağırlığınızı %{sec_amt:.0f} hafifleterek "
                    f"{ASSET_LABELS[sec_to[0]]} varlıklarına ekleme yapınız."
                ),
            })

    if not tactical_actions:
        tactical_actions.append({
            "action_type": "HOLD",
            "headline": "✅ Mevcut Portföy Dağılımınız Makro Rejimle Uyumlu",
            "instruction": "Mevcut varlık oranlarınız güncel faiz ve piyasa şartlarıyla dengeli durumdadır; şu an için radikal bir çıkış veya geçiş yapmanıza gerek yoktur.",
        })

    # 5. Çift Katmanlı Gerekçelendirme Metinleri (Sade + Teknik)
    if regime_code == "TIGHT_MONEY_HIGH_TL_YIELD":
        simple_rationale = (
            "Merkez Bankası ve ekonomi yönetimi faizleri yüksek tutmaya devam ediyor. "
            "Bu ortamda Türk Lirası mevduat ve para piyasası fonları (PPF) neredeyse hiç risk almadan yıllık %45-50 civarında bileşik getiri sağlamaktadır. "
            "Buna karşılık borsadaki pek çok şirket yüksek borç faizleri ve krediye erişim zorluğu nedeniyle zorlanabilir. "
            "Bu yüzden borsadaki genel hisse ağırlığınızı biraz düşürüp paranızı risksiz yüksek TL getirisinde değerlendirmek şu an en akılcı adımdır."
        )
        technical_rationale = (
            f"Son 30 günde taranan {total_signals} makro başlığın %{hawkish_pct:.0f}'si Şahin / Sıkılaşma sinyali taşımaktadır. "
            f"TCMB'nin pozitif reel faiz kararlılığı, zorunlu karşılık adımları ve BDDK'nın kredi büyüme sınırları "
            f"finansman maliyetlerini yüksek seviyede kilitlemektedir. Yüksek risksiz getiri oranı (Rf = %45-50) BIST hisse senetleri için "
            f"iskonto oranını (WACC) yükselterek F/K çarpanlarını baskılamaktadır. Bu rejimde portföy betasından kısılıp "
            f"para piyasası enstrümanlarına (PPF/Mevduat) ağırlık verilmesi Sharpe oranını maksimize eder."
        )
    elif regime_code == "EASING_RISK_ON":
        simple_rationale = (
            "Faiz indirimleri ve piyasaya nakit akışı dönemi başladı. "
            "Mevduat faizleri gerilerken para borsa ve altın gibi reel getiri vadeden yatırımlara hücum ediyor. "
            "Bankada faizde kalmanın cazibesi azaldığı için paranızı Borsa İstanbul'un öncü hisselerine kaydırmanız getirinizi katlayabilir."
        )
        technical_rationale = (
            f"Makro istihbarat akışının %{dovish_pct:.0f}'si Güvercin / Genişleme adımlarına işaret etmektedir. "
            f"Azalan politika faizleri ve bankacılık net faiz marjı (NIM) genişlemesi BIST lokomotif hisselerinde güçlü yeniden değerleme rüzgarı yaratmaktadır. "
            f"Getiri eğrisi normalleşirken tahvil ve hisse senedi ağırlıklarının artırılması taktiksel olarak uygundur."
        )
    elif regime_code == "PIVOT_HIGH_VOLATILITY":
        simple_rationale = (
            "Piyasalarda beklenmedik şoklar, olağanüstü kararlar veya küresel kriz işaretleri var. "
            "Böyle fırtınalı dönemlerde riskli hisselerden çıkıp Gram Altın, döviz ve likit güvenli limanlara sığınmak paranızı korur."
        )
        technical_rationale = (
            f"Son dönemde kaydedilen sinyallerin %{pivot_pct:.0f}'i Eksen Değişimi / Kriz niteliğindedir. "
            f"Türkiye CDS primindeki olası sıçrama ve kur oynaklığı karşısında BIST portföyü defansif hisselerle sınırlandırılmalı, "
            f"Gram Altın ve döviz likiditesi artırılmalıdır."
        )
    else:
        simple_rationale = (
            "Piyasa şu an sakin ve dengeli bir seyirde. "
            "Tek bir varlığa aşırı yüklenmeden sepetinizi hisse senedi, mevduat, döviz ve altın arasında dengeli dağıtmanız en güvenli yoldur."
        )
        technical_rationale = (
            "Makro göstergeler nötr koridorda seyretmekte olup varlık sınıfları arasında keskin bir makro arbitraj oluşmamıştır. "
            "Dengeli varlık dağılımı korunmalıdır."
        )

    # Canlı OpenAI GPT-4o Destekli Taktiksel Portföy Denetimi (6 Aylık Makro Bellek Entegrasyonu)
    memory_context = ""
    try:
        from radar_core.core.llm_engine import LLMEngine
        from radar_macro.memory_engine import get_active_memory_context
        engine = LLMEngine()
        memory_context = get_active_memory_context(months=6)

        if getattr(engine, "openai_api_key", None) or getattr(engine, "gemini_api_key", None):
            top_headlines = [a.summary_title for a, _ in recent_analyses[:5]]
            prompt_review = (
                f"Kullanıcı Portföyü: {current_weights}\n"
                f"Taktiksel Hedef Portföy: {target_weights}\n"
                f"Aktif Makro Rejim: {regime}\n\n"
                f"{memory_context}\n\n"
                f"Son Güncel Kararlar ve Bültenler:\n" + "\n".join(f"- {h}" for h in top_headlines) + "\n\n"
                f"GÖREV: 100.000 TL+ yatırım büyüklüğü için geçmiş 6 aylık politika mirasını ve son bültenleri sentezleyerek:\n"
                f"1. Basit özet (halk diliyle ne yapmalı)\n"
                f"2. Teknik analiz (WACC, risksiz faiz, borsa çarpanları, kur dengesi ve 6 aylık kümülatif aktarım mekanizması)\n"
                f"StructuredAnalysisOutput formatında oluştur."
            )
            ai_res = engine.analyze_structured(prompt=prompt_review, task_type="portfolio_copilot")
            m_ai = ai_res.metrics or {}
            ai_simple = m_ai.get("simple_summary") or ai_res.summary_title
            ai_tech = m_ai.get("technical_analysis") or ai_res.detailed_reasoning
            if ai_simple and len(ai_simple) > 20:
                simple_rationale = ai_simple
            if ai_tech and len(ai_tech) > 30:
                technical_rationale = ai_tech
    except Exception as exc:
        logger.debug("Live AI portfolio review skipped: %s", exc)

    # 6. BIST Şirket Bazlı Seçici Rehberlik (Bu Makro Rejimde Hangileri Alınmalı / Hangilerinden Kaçınılmalı)
    if regime_code == "TIGHT_MONEY_HIGH_TL_YIELD":
        bist_guidance = {
            "top_favored": [
                {"ticker": "ENKAI", "name": "Enka İnşaat", "reason": "Devasa net nakit ve döviz rezervi; faizler arttıkça finansman geliri yazar."},
                {"ticker": "BIMAS", "name": "BİM Mağazalar", "reason": "Borçsuz defansif perakende kalesi; enflasyon ve faiz şoklarına dayanıklı."},
                {"ticker": "FROTO", "name": "Ford Otosan", "reason": "İhracat ağırlıklı döviz cirosu ile iç talep yavaşlamasından korunur."},
                {"ticker": "TCELL", "name": "Turkcell", "reason": "Defansif temel hizmet sağlayıcı; güçlü nakit üretimi ve fiyatlama gücü."},
            ],
            "top_avoid": [
                {"ticker": "EKGYO", "name": "Emlak Konut", "reason": "Yüksek konut kredisi faizleri gayrimenkul talebini ve satışlarını dondurur."},
                {"ticker": "Yüksek Borçlu KOBİ'ler", "name": "Yüksek Finansman Borçlular", "reason": "Artan kredi faizleri net kârı finansman gideri olarak tüketir."},
                {"ticker": "SOKM", "name": "Şok Marketler", "reason": "Kaldıraçlı büyüme modeli yüksek faiz ortamında marj daralması yaşar."},
            ],
        }
    elif regime_code == "EASING_RISK_ON":
        bist_guidance = {
            "top_favored": [
                {"ticker": "GARAN / AKBNK", "name": "Özel Bankalar", "reason": "Mevduat maliyeti hızla düşerken net faiz marjı fırlar."},
                {"ticker": "EKGYO", "name": "Emlak Konut", "reason": "Kredi faizlerinin düşmesiyle konut ve arsa satışları canlanır."},
                {"ticker": "THYAO", "name": "Türk Hava Yolları", "reason": "Ekonomik canlılık ve tüketici talebiyle yolcu trafiği artar."},
            ],
            "top_avoid": [
                {"ticker": "ENKAI", "name": "Enka İnşaat", "reason": "Faiz gelirlerinin gerilemesi nedeniyle büyüme hisselerinin gerisinde kalabilir."},
                {"ticker": "Sadece TL Nakitte Kalanlar", "name": "TL Likidite", "reason": "Düşen faiz karşısında hisse senedi getirilerinin gerisinde kalır."},
            ],
        }
    else:
        bist_guidance = {
            "top_favored": [
                {"ticker": "FROTO", "name": "Ford Otosan", "reason": "Güçlü ihracat geliri ve sağlam bilanço."},
                {"ticker": "BIMAS", "name": "BİM Mağazalar", "reason": "Piyasa dalgalanmalarına karşı sağlam defansif yapı."},
                {"ticker": "TUPRS", "name": "Tüpraş", "reason": "Döviz bazlı rafineri marjları ve yüksek temettü potansiyeli."},
            ],
            "top_avoid": [
                {"ticker": "Döviz Açık Pozisyonlu Şirketler", "name": "Yüksek Borçlu Sanayi", "reason": "Kur ve faiz dalgalanmalarına karşı savunmasız."},
            ],
        }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "regime": regime,
        "regime_code": regime_code,
        "signals_analyzed_count": total_signals,
        "sentiment_stats": {
            "hawkish_pct": round(hawkish_pct, 1),
            "dovish_pct": round(dovish_pct, 1),
            "pivot_pct": round(pivot_pct, 1),
            "neutral_pct": round((neutral_count / total_signals) * 100, 1),
        },
        "current_weights": current_weights,
        "target_weights": target_weights,
        "weight_diffs": diffs,
        "tactical_actions": tactical_actions,
        "rationale": {
            "simple": simple_rationale,
            "technical": technical_rationale,
        },
        "bist_guidance": bist_guidance,
        "macro_memory_summary": memory_context,
    }
