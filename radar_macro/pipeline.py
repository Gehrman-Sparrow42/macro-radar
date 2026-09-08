"""Radar Makro: Türkiye Yatırımları ve Çift Katmanlı Makroekonomik Yayılım İstihbarat Hattı.
Açıklamaları hem sıradan bir yatırımcının anlayacağı sade dille hem de kurumsal teknik analizle üretir.
"""

import logging
from pathlib import Path
from typing import Any

from radar_core.core.database import get_engine, init_db
from radar_core.core.llm_engine import LLMEngine
from radar_core.core.models import RawData, StructuredAnalysisOutput
from radar_core.pipelines.base_pipeline import BasePipeline

import radar_macro.fetchers.turkish_fetcher  # noqa: F401
from radar_macro.config.bist_sectors import map_macro_to_bist_tickers
from radar_macro.config.settings import get_macro_settings
from radar_macro.config.sources import get_active_macro_sources

logger = logging.getLogger("radar_macro.pipeline")

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "macro_analysis.txt"


def _load_macro_prompt() -> str:
    """Makro analiz prompt şablonunu yükler."""
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "Makroekonomik ve yasal istihbarat maddesini Türkiye yatırımları yayılım filtresinden analiz et:\n"
        "KAYNAK: {source}\nURL: {url}\nBAŞLIK: {title}\n\nİÇERİK:\n{content}\n"
    )


class MacroImpactPipeline(BasePipeline):
    """
    T.C. Resmî Gazete, TCMB, SPK ve küresel merkez bankası (Fed/ECB) kararlarını
    Türk finansal varlıkları (BIST 100, Dolar/TL, DİBS, 5Y CDS, Gram Altın) üzerinde
    hem sade halk diliyle hem de teknik finansal mekanizmayla analiz eden istihbarat hattı.
    """

    def __init__(self, db_url: str | None = None, api_key: str | None = None):
        settings = get_macro_settings()
        target_db = db_url or settings.DATABASE_URL

        get_engine(db_url=target_db)
        init_db(db_url=target_db)

        llm = LLMEngine(
            gemini_api_key=api_key or settings.GEMINI_API_KEY,
            openai_api_key=settings.OPENAI_API_KEY,
            gemini_model=settings.GEMINI_MODEL,
            openai_model_fast=settings.OPENAI_MODEL_FAST,
            openai_model_heavy=settings.OPENAI_MODEL_HEAVY,
            max_retries=settings.MAX_RETRIES,
            backoff_factor=settings.BACKOFF_FACTOR,
        )

        bilingual_macro_keywords = [
            # Türkçe Terimler
            "faiz", "enflasyon", "merkez bankası", "tcmb", "ppk", "politika faizi",
            "tebliğ", "yönetmelik", "karar", "cumhurbaşkanı kararı", "genelge",
            "kanun", "bddk", "spk", "hazine", "maliye", "rezerv", "döviz",
            "türk lirası", "kur", "tahvil", "mevduat", "zorunlu karşılık",
            "sıkılaşma", "sıkı para politikası", "likidite", "resmi gazete",
            "kamu borçlanma", "ihale", "özelleştirme", "yaptırım", "tedbir",
            "sermaye piyasası", "bist", "borsa", "kredi", "vergi", "bütçe",

            # İngilizce Küresel Terimler
            "interest", "rate", "inflation", "central bank", "regulation",
            "treasury", "yield", "policy", "debt", "tariff", "liquidity",
            "reserve", "securities", "sanction", "enforcement", "decree",
            "gazette", "monetary", "cpi", "fomc", "ecb", "basis points",
            "capital requirement", "basel", "audit", "compliance", "bank",
            "fed", "boe", "market", "currency", "bond", "stimulus", "emerging",
            "turkey", "turkish", "lira", "bist", "cds", "eurobond",
        ]

        super().__init__(
            pipeline_name="macro_regulatory",
            llm_engine=llm,
            include_keywords=bilingual_macro_keywords,
            min_content_length=settings.MIN_CONTENT_LENGTH,
        )
        self.prompt_template = _load_macro_prompt()

    def build_prompt(self, raw_data: RawData) -> str:
        prompt = self.prompt_template
        prompt = prompt.replace("{source}", str(raw_data.source_name))
        prompt = prompt.replace("{url}", str(raw_data.url))
        prompt = prompt.replace("{title}", str(raw_data.title))
        prompt = prompt.replace("{content}", str(raw_data.content_text[:5000]))
        return prompt

    def get_sources(
        self,
        category: str | None = None,
        jurisdiction: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_active_macro_sources(category=category, jurisdiction=jurisdiction)

    def _heuristic_fallback_analysis(self, item: RawData) -> StructuredAnalysisOutput:
        """
        Çift katmanlı (Basit Anlatım + Derin Teknik Analiz) yerel kural tabanlı makro analiz motoru.
        """
        lower_txt = (item.title + " " + item.content_text).lower()

        is_turkish = any(
            k in lower_txt or k in item.source_name.lower()
            for k in [
                "resmi_gazete", "tcmb", "spk", "bddk", "bloomberght", "aa_ekonomi",
                "türkiye", "karar", "tebliğ", "faiz", "türk lirası", "lira", "bist",
            ]
        )

        source_jurisdiction = "Türkiye" if is_turkish else (
            "ABD" if any(w in lower_txt or w in item.source_name.lower() for w in ["fed", "sec", "united states", "federal reserve"]) else (
                "Euro Bölgesi" if "ecb" in lower_txt or "ecb" in item.source_name.lower() else (
                    "İngiltere" if "england" in lower_txt or "boe" in item.source_name.lower() else "Küresel"
                )
            )
        )

        # Şahin / Güvercin / Eksen Değişimi
        hawkish_signals = [
            "hike", "tightening", "curb", "hawkish", "higher for longer", "sanction",
            "enforcement", "faiz artış", "sıkılaş", "sıkı para", "enflasyonla mücadele",
            "tedbir", "ceza", "iptal", "yaptırım", "karşılık artır",
        ]
        dovish_signals = [
            "cut", "easing", "dovish", "liquidity support", "stimulus", "slowdown",
            "faiz indir", "gevşe", "likidite desteği", "destekleme", "teşvik",
        ]
        pivot_signals = [
            "emergency", "crisis", "default", "collapse", "investigation",
            "olağanüstü", "kriz", "müdahale", "istifa", "soruşturma",
        ]

        if any(w in lower_txt for w in hawkish_signals):
            stance = "ŞAHİN"
            sev = "WARNING"
        elif any(w in lower_txt for w in dovish_signals):
            stance = "GÜVERCİN"
            sev = "OPPORTUNITY"
        elif any(w in lower_txt for w in pivot_signals):
            stance = "EKSEN DEĞİŞİMİ"
            sev = "CRITICAL"
        else:
            stance = "NÖTR"
            sev = "INFO"

        urgency = "ACİL UYUM" if any(w in lower_txt for w in ["enforcement", "sanction", "yürürlüğe girdi", "derhal", "ceza", "tedbir"]) else (
            "TASLAK DÜZENLEME" if any(w in lower_txt for w in ["rule", "proposal", "taslak", "tebliğ", "yönetmelik", "kanun"]) else "İZLEME"
        )

        # -------------------------------------------------------------------
        # ÇİFT KATMANLI AÇIKLAMA ÜRETİMİ (SADE DİL + TEKNİK ANALİZ)
        # -------------------------------------------------------------------
        if is_turkish:
            # 1. Yurt İçi Türkiye Gelişmesi
            if stance == "ŞAHİN":
                simple_summary = (
                    "Merkez Bankası veya ekonomi yönetimi piyasadaki parayı ve kredileri kısmaya yönelik sıkılaştırıcı adımlar atıyor. "
                    "Bu durum Türk Lirası mevduat faizlerini yüksek tutarak paranızı faizde değerlendirmeyi cazip kılar; "
                    "ancak borçlanmayı zorlaştırdığı için borsadaki şirketlerin kâr marjlarını ve harcamaları bir miktar baskılayabilir."
                )
                technical_analysis = (
                    f"{item.source_name} kaynaklı parasal ve makroihtiyati sıkılaşma adımı. "
                    f"Politika faizindeki artış veya zorunlu karşılık yükümlülükleri, bankacılık sistemi fonlama maliyetlerini (WACC) yukarı çekmektedir. "
                    f"BIST 100 ve bankacılık endeksinde (XBANK) net faiz marjı (NIM) baskısı oluşurken, yüksek TL mevduat getirisi carry trade cazibesi oluşturarak "
                    f"Dolar/TL kuru üzerinde çıpa görevi görmektedir. DİBS getiri eğrisinde kısa vadeli tahviller yukarı yönlü yeniden fiyatlanmaktadır."
                )
                asset_impact = {
                    "BIST 100 / Hisse Senetleri": "Negatif (Sermaye maliyetinde artış, XBANK marj baskısı)",
                    "Dolar/TL (USD/TRY) & TL Mevduat": "TL Lehine (Cazip TL mevduat getirisi, kurda istikrar)",
                    "DİBS (Devlet Tahvili) & 5Y CDS": "Negatif (Gösterge faizler yükselir, tahvil fiyatları geriler)",
                    "Gram Altın (TL)": "Nötr (TL'deki istikrar Ons etkisini dengeler)",
                }
                actions = [
                    "Yüksek getiri sunan Türk Lirası mevduat ve kısa vadeli DİBS getirilerini sabitleyin",
                    "Yüksek borçlu BIST sanayi hisselerinde ağırlığı azaltıp net nakit pozisyonu güçlü şirketlere yönelin",
                    "Resmî Gazete'de yayımlanan bankacılık ve kredi düzenleme takvimini yakından izleyin",
                ]
            elif stance == "GÜVERCİN":
                simple_summary = (
                    "Ekonomi yönetimi piyasaya daha rahat para girişi sağlamak veya faiz yükünü hafifletmek için adımlar atıyor. "
                    "Kredilerin ucuzlaması ve piyasaya likidite girmesi şirketler ve Borsa İstanbul için olumlu bir büyüme rüzgarı yaratır; "
                    "fakat mevduat faizleri gerileyebileceğinden döviz ve altına olan talebi canlandırabilir."
                )
                technical_analysis = (
                    f"{item.source_name} kaynaklı parasal genişleme veya likidite rahatlatıcı adım. "
                    f"Kredi faizlerinin gerilemesi ve munzam karşılıkların gevşetilmesi, hanehalkı ve kurumsal talep kanalını açarak hisse senedi çarpanlarında (F/K) "
                    f"yeniden değerleme katalizörü yaratır. Ancak TL reel faizinin zayıflaması halinde döviz tevdiat hesaplarına (DTH) kayış ve kur geçişkenliği "
                    f"enflasyon görünümü açısından risk taşımaktadır."
                )
                asset_impact = {
                    "BIST 100 / Hisse Senetleri": "Pozitif (Kredi genişlemesi ve hisse çarpanlarında değer artışı)",
                    "Dolar/TL (USD/TRY) & TL Mevduat": "TL Aleyhine (Mevduat faizinde gerileme, dövize yönelim riski)",
                    "DİBS (Devlet Tahvili) & 5Y CDS": "Pozitif (Tahvil faizlerinde gerileme, tahvil rallisi)",
                    "Gram Altın (TL)": "Pozitif (Kur ve küresel ons desteğiyle Gram Altın yükseliş eğilimi)",
                }
                actions = [
                    "BIST hisse senedi pozisyonlarını artırın (özellikle büyüme ve döngüsel sektörler)",
                    "Olası kur dalgalanmalarına karşı portföyde Gram Altın ve döviz korunma payı bulundurun",
                    "Sabit getirili uzun vadeli Türk devlet tahvillerinde (DİBS) vadeyi uzatın",
                ]
            else:
                simple_summary = (
                    "Bu gelişme Resmî Gazete veya ilgili kurumların olağan idari bir bültenidir. "
                    "Doğrudan döviz kuru, altın veya borsa fiyatları üzerinde ani ve sarsıcı bir değişiklik yaratması beklenmez; "
                    "mevcut birikimlerinizi aynı dengede koruyabilirsiniz."
                )
                technical_analysis = (
                    f"{item.source_name} kaynaklı operasyonel resmî gazete kararı veya olağan duyuru. "
                    f"Makro ihtiyati çerçeveyi veya sistemik likidite dengesini bozacak bir regülasyon değişikliği içermemektedir. "
                    f"Özet Alıntı: {item.content_text[:250]}..."
                )
                asset_impact = {
                    "BIST 100 / Hisse Senetleri": "Nötr",
                    "Dolar/TL (USD/TRY) & TL Mevduat": "Nötr",
                    "DİBS (Devlet Tahvili) & 5Y CDS": "Nötr",
                    "Gram Altın (TL)": "Nötr",
                }
                actions = [
                    "Türk finansal varlıklarında mevcut portföy dağılımını koruyun",
                    "TCMB Para Politikası Kurulu (PPK) takvimini ve Resmî Gazete tebliğlerini takip edin",
                ]
        else:
            # 2. Küresel Yayılım (Fed / ECB / ABD / Küresel -> Türkiye)
            if stance == "ŞAHİN":
                simple_summary = (
                    "Amerika Merkez Bankası (Fed) veya küresel kurumlar faizleri yüksek tutacaklarını belirtiyor. "
                    "Bu durum dünyadaki parayı dolara yönlendirir. Türkiye gibi gelişmekte olan ülkelerden yabancı para çıkışı görülebileceğinden, "
                    "Dolar/TL kuru üzerinde yukarı yönlü baskı oluşabilir ve borsadaki yabancı yatırımcılar satışa geçebilir."
                )
                technical_analysis = (
                    f"{item.source_name} ({source_jurisdiction}) kaynaklı küresel sıkılaşma sinyali. "
                    f"Yayılım Mekanizması: ABD 2Y/10Y Hazine getirilerinin yükselmesi DXY (Dolar Endeksi) rallisini tetikler. "
                    f"Gelişmekte olan ülke (EM) portföylerinden sermaye çıkışı, Türkiye'nin 5 yıllık kredi iflas takası (CDS) spread'ini genişletir. "
                    f"Dolar/TL kuru üzerindeki yukarı yönlü baskı TCMB'nin döviz rezervi yönetiminde manevra alanını daraltırken BIST çarpanlarını baskılar."
                )
                asset_impact = {
                    "BIST 100 / Hisse Senetleri": "Negatif (Gelişmekte olan ülkelerden ve Türkiye'den yabancı çıkışı)",
                    "Dolar/TL (USD/TRY) & TL Mevduat": "TL Aleyhine (Güçlenen DXY endeksi Dolar/TL üzerinde yukarı baskı kurar)",
                    "DİBS (Devlet Tahvili) & 5Y CDS": "Negatif (Türkiye 5Y CDS risk primi artar, Eurobond borçlanma maliyeti yükselir)",
                    "Gram Altın (TL)": "Pozitif (Dolar/TL'deki yükseliş iç piyasada Gram Altını destekler)",
                }
                actions = [
                    "Döviz cinsi borç ve açık pozisyonları Dolar/TL vadeli kontratlarıyla hedge edin",
                    "BIST portföyünde döviz geliri olan güçlü Türk ihracatçı şirketleri önceliklendirin",
                    "Türkiye 5Y CDS genişlemesine karşı Eurobond pozisyonlarında temkinli kalın",
                ]
            elif stance == "GÜVERCİN":
                simple_summary = (
                    "Amerika veya Avrupa'da faizlerin düşeceği ve piyasaya bol para verileceği sinyali geldi. "
                    "Dünyada faizler düşünce küresel fonlar daha yüksek kâr arayışıyla Türkiye gibi ülkelere akar. "
                    "Bu durum Dolar/TL'deki yükseliş baskısını azaltır, Borsa İstanbul'da yabancı alımlarını artırır ve altın fiyatlarını destekler."
                )
                technical_analysis = (
                    f"{item.source_name} ({source_jurisdiction}) kaynaklı küresel parasal gevşeme adımı. "
                    f"Yayılım Mekanizması: Fed/ECB faiz indirimleri küresel sermaye maliyetini düşürerek yüksek getirili EM varlıklarına risk iştahı yaratır. "
                    f"Türkiye 5Y CDS priminin daralması Eurobond ve Hazine borçlanma faizlerini düşürür. Zayıflayan Dolar Endeksi (DXY) Dolar/TL üzerindeki kur baskısını "
                    f"azaltırken Borsa İstanbul'a (özellikle likit banka ve holdinglere) güçlü yabancı kurumsal giriş sağlar."
                )
                asset_impact = {
                    "BIST 100 / Hisse Senetleri": "Pozitif (Küresel risk iştahı artışı, BIST'e yabancı fon akışı)",
                    "Dolar/TL (USD/TRY) & TL Mevduat": "TL Lehine (Zayıflayan dolar Dolar/TL kurundaki baskıyı hafifletir)",
                    "DİBS (Devlet Tahvili) & 5Y CDS": "Pozitif (Türkiye CDS risk primi daralır, Eurobond fiyatları yükselir)",
                    "Gram Altın (TL)": "Pozitif (Küresel Ons Altın rallisi doğrudan Gram Altına yansır)",
                }
                actions = [
                    "Beklenen yabancı portföy girişleri doğrultusunda BIST 100 ve bankacılık hisselerine ağırlık verin",
                    "Daralan Türk CDS risk priminden faydalanarak Türk Hazine Eurobond pozisyonlarını artırın",
                    "Küresel faiz indirimi rüzgarında Gram Altın birikimlerini koruyun",
                ]
            else:
                simple_summary = (
                    "Küresel piyasalarda rutin bir ekonomik veri açıklandı. "
                    "Türkiye'deki döviz kuru, borsa ve faizler üzerinde doğrudan ani bir şok veya bozulma yaratması beklenmemektedir."
                )
                technical_analysis = (
                    f"{item.source_name} ({source_jurisdiction}) kaynaklı küresel makroekonomik bülten. "
                    f"Gelişmekte olan piyasalara yönelik risk priminde ve swap kanallarında anlamlı bir kırılma yaratmamaktadır. "
                    f"Özet Alıntı: {item.content_text[:250]}..."
                )
                asset_impact = {
                    "BIST 100 / Hisse Senetleri": "Nötr",
                    "Dolar/TL (USD/TRY) & TL Mevduat": "Nötr",
                    "DİBS (Devlet Tahvili) & 5Y CDS": "Nötr",
                    "Gram Altın (TL)": "Nötr",
                }
                actions = [
                    "Küresel tahvil getirilerini ve BIST yabancı takas oranını izlemeye devam edin",
                ]

        flag = "🇹🇷" if is_turkish else "🌐"
        source_tag = "Yurt İçi Doğrudan" if is_turkish else f"Küresel Yayılım ({source_jurisdiction})"
        headline = f"{flag} [{source_tag}] {item.title[:105]}"

        # Birleştirilmiş detaylı gerekçelendirme metni (çift katmanlı)
        combined_reasoning = (
            f"💡 BASİTÇE NE DEMEK? (HERKES İÇİN):\n"
            f"{simple_summary}\n\n"
            f"🔬 TEKNİK ANALİZ & MAKRO YAYILIM MEKANİZMASI (PROFESYONELLER İÇİN):\n"
            f"{technical_analysis}"
        )

        # BIST Şirket & Sektör Duyarlılık Eşleştirmesi
        bist_tickers = map_macro_to_bist_tickers(
            policy_stance=stance,
            is_turkish=is_turkish,
            category=item.category if hasattr(item, "category") else "",
            text_content=item.title + " " + item.content_text,
        )

        metrics = {
            "policy_stance": stance,
            "regulatory_urgency": urgency,
            "jurisdiction": source_jurisdiction,
            "is_turkish": is_turkish,
            "simple_summary": simple_summary,
            "technical_analysis": technical_analysis,
            "turkey_impact_profile": "Doğrudan Yurt İçi" if is_turkish else "Türkiye'ye Küresel Yayılım",
            "asset_impact": asset_impact,
            "bist_tickers": bist_tickers,
            "relevance_score": 90 if is_turkish else (80 if sev in ["CRITICAL", "WARNING"] else 70),
            "tags": [item.source_name.lower(), stance.lower(), urgency.lower(), "turkiye_yatirimlari"],
            "mode": "macro_dual_layer_analysis",
        }

        return StructuredAnalysisOutput(
            severity=sev,
            summary_title=headline,
            detailed_reasoning=combined_reasoning,
            action_items=actions,
            metrics=metrics,
        )
