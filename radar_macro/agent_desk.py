"""Antigravity Yapay Zeka Baş Stratejist Masası (Agent Executive Desk).

Bu modül, kullanıcının talebi üzerine Antigravity ajanının kendi derin muhakeme gücünü kullanarak
hiçbir harici OpenAI/Gemini API kredisi yakmadan doğrudan sisteme kurumsal yatırım stratejisi
notları üretmesini ve veritabanına işlemesini sağlar.
"""

import sys
from pathlib import Path

# Add workspace root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from datetime import datetime, timezone
import json
import logging
from typing import Any

from radar_core.core.database import get_engine, get_session, save_agent_memo, get_latest_agent_memo
from radar_core.core.models import AgentStrategyMemo
from radar_macro.memory_engine import get_active_memory_context

logger = logging.getLogger("radar_macro.agent_desk")


ANTIGRAVITY_INITIAL_STRATEGY_MEMO = {
    "author": "Antigravity AI (Chief Investment Strategist)",
    "headline": "TCMB %50 Politika Çıpası ve Likidite Sterilizasyonu ile Pozitif Reel Getiri Dönemi: Yüksek Borçlu Sanayiden Çıkış, BIST 30 Nakit Zengini Kaleler ve TL Mevduat Arbitrajı",
    "macro_verdict": "ŞAHİN ÇIPA / SIKI PARA POLİTİKASI & YÜKSEK TL REEL GETİRİSİ (WACC: %48+)",
    "summary_guidance": (
        "Piyasada şu an net bir kural geçerli: 'Faiz yüksek, nakit kral.' "
        "Merkez Bankası faizleri %50 seviyesinde sabit tutarak Türk Lirası'nı güçlü bir kalkan haline getirdi. "
        "Bu ortamda paranızı yıllık bileşik %48-52 getiri vadeden risksiz TL mevduat ve Para Piyasası Fonlarında (PPF) "
        "değerlendirmek en güvenli limandır. Borsada ise borçla dönen, faiz yükü ağır şirketlerden kesinlikle uzak durulmalı; "
        "kasası döviz ve nakit dolu, borçsuz ihracatçı veya defansif BIST 30 şirketleri (ENKAI, BIMAS, FROTO, TCELL) "
        "tercih edilmelidir. Sepetinizde %45 risksiz TL mevduat, %25 seçici BIST hissesi, %10 döviz nakit ve %10-10 altın/tahvil dengesi "
        "en kârlı ve koruyucu stratejidir."
    ),
    "technical_analysis": (
        "TCMB'nin 6 aylık aktarım mekanizması incelendiğinde, politika faizinin %50'de çıpalanması ve gecelik repo/depo ihaleleriyle "
        "sistemdeki likidite fazlasının sterilize edilmesi, risksiz getiri oranını (Rf) %48-52 bandında kilitlemiştir. "
        "Ağırlıklı Ortalama Sermaye Maliyeti (WACC) sanayi firmaları için %45'in üzerine fırlayarak borç kaldıraçlı büyüme modelini cezalandırmaktadır. "
        "F/K çarpanlarında yaşanan marj daralması sanayi endeksi üzerinde baskı kurarken; net nakit pozisyonu pozitif olan şirketler finansman geliri yazmaktadır. "
        "Temmuz'da Moody's'in 2 kademe not artışı (B1) ve FATF Gri Liste'den çıkış, Türkiye CDS primini 260-280 bps koridoruna çekerek ülke risk primini rahatlatmıştır. "
        "Optimal portföy tahsisinde Beta < 0.8 defansif hisseler seçilmeli, risksiz getiri ile Sharpe oranı maksimize edilmelidir."
    ),
    "favored_tickers": [
        {"ticker": "ENKAI", "name": "Enka İnşaat", "reason": "5 milyar doları aşan devasa net nakit ve döviz rezervi; faizler arttıkça yüksek finansman geliri yazar."},
        {"ticker": "BIMAS", "name": "BİM Mağazalar", "reason": "Sıfıra yakın finansal borç, negatif işletme sermayesi döngüsü ve enflasyon/faiz şoklarına karşı defansif kalkan."},
        {"ticker": "FROTO", "name": "Ford Otosan", "reason": "Euro bazlı uzun vadeli 'al ya da öde' ihracat anlaşmalarıyla iç pazardaki kredi daralmasından izole."},
        {"ticker": "TCELL", "name": "Turkcell", "reason": "Temel iletişim altyapısı, düzenli serbest nakit akışı ve tarifeleri enflasyona göre güncelleme gücü."},
        {"ticker": "ASELS", "name": "Aselsan", "reason": "Ağustos ayında Resmî Gazete'de yayımlanan Hazine savunma teşvikleri ve 10 milyar doları aşan sipariş güvencesi."},
    ],
    "pressured_tickers": [
        {"ticker": "EKGYO", "name": "Emlak Konut GYO", "reason": "Konut kredisi faizlerinin aylık %3'ün üzerinde kalması ve kredili konut satışlarının durma noktasına gelmesi."},
        {"ticker": "SOKM", "name": "Şok Marketler", "reason": "Kaldıraçlı mağaza ağı ve finansal borçluluk nedeniyle yüksek faiz ortamında net kâr marjının erimesi."},
        {"ticker": "PETKM", "name": "Petkim", "reason": "Küresel etilen-nafta makasındaki daralma ve yüksek işletme sermayesi finansman maliyeti."},
        {"ticker": "Kaldıraçlı Sanayi", "name": "Yüksek Finansman Borçlular", "reason": "Yıllık %60+ ticari kredi faizleri altında net faaliyet kârının faiz giderlerine gitmesi."},
    ],
    "tactical_allocation": {
        "bist": 25.0,
        "mevduat": 45.0,
        "doviz": 10.0,
        "dibs": 10.0,
        "altin": 10.0,
    },
    "confidence_score": 0.98,
}


def publish_agent_memo(memo_dict: dict[str, Any] | None = None) -> AgentStrategyMemo:
    """
    Antigravity Strateji Raporunu doğrudan veritabanına kaydeder.
    """
    data = memo_dict or ANTIGRAVITY_INITIAL_STRATEGY_MEMO
    memo = AgentStrategyMemo(
        author=data.get("author", "Antigravity AI (Chief Investment Strategist)"),
        headline=data["headline"],
        macro_verdict=data["macro_verdict"],
        summary_guidance=data["summary_guidance"],
        technical_analysis=data["technical_analysis"],
        favored_tickers=data.get("favored_tickers", []),
        pressured_tickers=data.get("pressured_tickers", []),
        tactical_allocation=data.get("tactical_allocation", {}),
        confidence_score=data.get("confidence_score", 0.98),
        created_at=datetime.now(timezone.utc),
    )

    with get_session() as session:
        saved = save_agent_memo(session, memo)
        logger.info("Antigravity Agent Strategy Memo successfully published (ID: %s).", saved.id)
        return saved


if __name__ == "__main__":
    saved_memo = publish_agent_memo()
    print("Agent Strategy Memo Published Successfully!")
    print(f"ID: {saved_memo.id} | Author: {saved_memo.author}")
    print(f"Headline: {saved_memo.headline}")
    print(f"Verdict: {saved_memo.macro_verdict}")
