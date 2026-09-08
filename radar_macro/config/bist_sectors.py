"""BIST 30 / 100 Sektör ve Hisse Senedi Makro Duyarlılık Matrisi.
Makroekonomik gelişmeleri, faiz, kur ve regülasyon kararlarını spesifik BIST şirketlerine eşleştirir.
"""

from typing import Any

# Sektör ve Şirket Karakteristikleri
BIST_COMPANIES = {
    # -----------------------------------------------------------------------
    # Bankacılık Endeksi (XBANK)
    # Duyarlılık: TCMB faiz kararları, zorunlu karşılıklar, kredi büyüme sınırları
    # -----------------------------------------------------------------------
    "XBANK": {
        "sector_name": "Bankacılık",
        "tickers": ["GARAN", "AKBNK", "ISCTR", "YKBNK", "VAKBN", "HALKB"],
        "profile": "Faiz marjı, TL mevduat maliyeti ve makroihtiyati düzenlemelere aşırı duyarlı.",
    },

    # -----------------------------------------------------------------------
    # Güçlü İhracatçılar (Döviz Geliri Yüksek / Avrupa & Global Satış)
    # Duyarlılık: EUR/USD paritesi, Avrupa ekonomik büyümesi, Dolar/TL kuru
    # -----------------------------------------------------------------------
    "EXPORTERS": {
        "sector_name": "İhracatçı Sanayi & Havacılık",
        "tickers": ["FROTO", "TOASO", "ARCLK", "TTRAK", "SISE", "ASELS", "THYAO", "TAVHL"],
        "profile": "Gelirlerinin %70+'si döviz cinsindendir. Zayıf TL ve güçlü Avrupa talebinden pozitif etkilenir.",
    },

    # -----------------------------------------------------------------------
    # Nakit Zengini & Defansif Perakende / Hizmet
    # Duyarlılık: Yüksek faiz ortamında net faiz geliri yazan, borçsuz defansif hisseler
    # -----------------------------------------------------------------------
    "CASH_RICH": {
        "sector_name": "Nakit Zengini & Defansif Tüketim",
        "tickers": ["BIMAS", "MGROS", "TCELL", "ENKAI", "CCOLA"],
        "profile": "Net nakit fazlası bulunur; yüksek TL faiz ortamında finansal gelir elde ederler. Enflasyon korumalıdır.",
    },

    # -----------------------------------------------------------------------
    # Faize Duyarlı / Yüksek Borçlu & GYO
    # Duyarlılık: Kredi faizleri ve finansman maliyetlerindeki artıştan olumsuz etkilenenler
    # -----------------------------------------------------------------------
    "RATE_SENSITIVE": {
        "sector_name": "GYO & Faiz Hassasiyeti Yüksek",
        "tickers": ["EKGYO", "ISGYO", "PETKM", "KRDMD", "SOKM"],
        "profile": "Yüksek finansman borcu veya konut/kredi talebine bağımlılık; faiz artışında marjları daralır.",
    },

    # -----------------------------------------------------------------------
    # Enerji & Rafineri & Emtia
    # Duyarlılık: Brent petrol, elektrik sübvansiyonları ve küresel emtia fiyatları
    # -----------------------------------------------------------------------
    "ENERGY_COMMODITY": {
        "sector_name": "Enerji & Rafineri & Emtia",
        "tickers": ["TUPRS", "ENJSA", "AKSA", "EREGL"],
        "profile": "Petrol/emtia fiyatları ve enerji regülasyonlarına doğrudan duyarlıdır.",
    },
}


def map_macro_to_bist_tickers(
    policy_stance: str,
    is_turkish: bool,
    category: str = "",
    text_content: str = "",
) -> dict[str, list[dict[str, str]]]:
    """
    Gelen makro kararın hangi BIST şirketlerine yarayacağını ve hangilerini
    baskılayacağını somut şirket kodları ve gerekçeleriyle eşleştirir.
    """
    lower = text_content.lower()
    stance = policy_stance.upper()

    favored: list[dict[str, str]] = []
    pressured: list[dict[str, str]] = []

    # 1. Yurt İçi Türkiye Gelişmeleri
    if is_turkish:
        if stance in ["ŞAHİN", "HAWKISH"]:
            # Faiz artışı / sıkılaşma ortamı
            favored.extend([
                {"ticker": "ENKAI", "reason": "Devasa net nakit ve döviz portföyü ile yüksek faizden ek getiri yazar."},
                {"ticker": "BIMAS", "reason": "Defansif temel perakende; borçsuz yapısıyla yüksek faiz şokuna dayanıklı."},
                {"ticker": "FROTO", "reason": "İhracat ağırlıklı döviz geliri sayesinde iç talep daralmasından korunur."},
                {"ticker": "TCELL", "reason": "Fiyatlama gücü yüksek defansif nakit akışı."},
            ])
            pressured.extend([
                {"ticker": "EKGYO", "reason": "Yüksek konut kredisi faizleri gayrimenkul talebini baskılar."},
                {"ticker": "AKBNK / GARAN", "reason": "Zorunlu karşılık yükü ve yükselen mevduat maliyeti kısa vadede kredi marjını sıkar."},
                {"ticker": "Borçlu Sanayiler", "reason": "Yüksek borçlanma maliyeti ve finansman giderleri kârlılığı eritir."},
            ])
        elif stance in ["GÜVERCİN", "DOVISH"]:
            # Faiz indirimi / parasal genişleme ortamı
            favored.extend([
                {"ticker": "GARAN / AKBNK / YKBNK", "reason": "Fonlama maliyetleri düşer, net faiz marjı hızla genişler."},
                {"ticker": "EKGYO", "reason": "Kredi faizlerinin düşmesi konut ve gayrimenkul satışlarını canlandırır."},
                {"ticker": "THYAO", "reason": "Ekonomik canlılık ve turizm/seyahat talebi ivmelenir."},
                {"ticker": "Borçlu Sanayiler", "reason": "Finansman giderlerinin azalması hisse değerlemelerine kaldıraç sağlar."},
            ])
            pressured.extend([
                {"ticker": "ENKAI", "reason": "Mevduat ve tahvil faiz gelirlerinde düşüş yaşanır."},
                {"ticker": "TL Nakitte Kalanlar", "reason": "Reel faiz gerilediğinde hisse/altın karşısında getiri erozyonu."},
            ])
        else:
            # Nötr / Sektörel / Enflasyon kararları
            if any(w in lower for w in ["enflasyon", "tüfe", "üfe", "fiyat"]):
                favored.append({"ticker": "BIMAS", "reason": "Hızlı fiyat geçişkenliği ve güçlü nakit akışıyla enflasyona karşı korumalı defansif perakende."})
                favored.append({"ticker": "TCELL", "reason": "Taahhütlü tarife artışları ile enflasyonist ortamda gelirlerini koruma gücü."})
                pressured.append({"ticker": "Borçlu Sanayiler", "reason": "Yüksek enflasyonda işletme sermayesi ihtiyacı ve girdi maliyeti baskısı."})
            elif any(w in lower for w in ["enerji", "petrol", "akaryakıt", "rafineri"]):
                favored.append({"ticker": "TUPRS", "reason": "Enerji ve rafineri marjı dinamiklerini takip eder."})
                favored.append({"ticker": "ENJSA", "reason": "TÜFE'ye endeksli tarife yapısıyla düzenlenmiş enerji şebeke geliri."})
            elif any(w in lower for w in ["ihracat", "vergi", "teşvik", "dış ticaret"]):
                favored.append({"ticker": "FROTO / SISE", "reason": "İhracat teşviklerinden ve dış ticaret düzenlemelerinden yararlanır."})
            else:
                favored.append({"ticker": "BIMAS / FROTO", "reason": "Dengeli piyasa koşullarında sağlam bilanço ve yüksek nakit yaratımıyla öne çıkar."})
                pressured.append({"ticker": "Sığ & Borçlu Hisseler", "reason": "Belirsizlik dönemlerinde düşük likidite ve finansman yükü riski."})

    # 2. Küresel Yayılım (Fed / ECB / ABD / Avrupa -> BIST)
    else:
        if stance in ["ŞAHİN", "HAWKISH"]:
            # Fed faiz artışı / Şahin duruş (Dolar güçlenir, EM'den çıkış)
            favored.extend([
                {"ticker": "FROTO", "reason": "%80+ ihracat geliri; Dolar/Euro güçlenmesi operasyonel kârı besler."},
                {"ticker": "THYAO", "reason": "Gelirlerinin ezici çoğunluğu döviz cinsinden olduğundan kur şoklarına karşı dirençlidir."},
                {"ticker": "ASELS", "reason": "Dövize endeksli savunma sözleşmeleri ve güçlü nakit akışı."},
                {"ticker": "BIMAS", "reason": "Yabancı çıkışında yabancı takası en dirençli defansif perakende kalesi."},
            ])
            pressured.extend([
                {"ticker": "GARAN / ISCTR", "reason": "Küresel fonlar gelişmekte olan piyasa bankalarından ilk satışa geçer."},
                {"ticker": "EKGYO", "reason": "Yükselen küresel borçlanma maliyetleri genel risk primini artırır."},
            ])
        elif stance in ["GÜVERCİN", "DOVISH"]:
            # Fed faiz indirimi / Küresel risk iştahı
            favored.extend([
                {"ticker": "GARAN / AKBNK", "reason": "Türkiye'ye küresel fon akışında yabancıların ilk aldığı en likit hisselerdir."},
                {"ticker": "THYAO / TAVHL", "reason": "Küresel büyüme ve havacılık katsayısı pozitif rüzgar alır."},
                {"ticker": "BIST 30 Lokomotifler", "reason": "Küresel EM fonlarının Türkiye'ye girişiyle endeks ralliye başlar."},
            ])
            pressured.extend([
                {"ticker": "Yalnızca İç Pazara Çalışan Borçlular", "reason": "Yabancı ilgisi ana lokomotiflere kaydığı için geri planda kalabilir."},
            ])
        else:
            if any(w in lower for w in ["petrol", "oil", "enerji", "brent", "gaz"]):
                favored.append({"ticker": "TUPRS", "reason": "Brent petrol ve rafineri marjlarındaki dalgalanmayı bilançoya yansıtır."})
                pressured.append({"ticker": "THYAO", "reason": "Yüksek petrol fiyatları havacılıkta yakıt maliyetini artırır."})
            else:
                favored.append({"ticker": "FROTO / ASELS", "reason": "Küresel döviz gelirleri ve ihracat gücüyle dış dalgalanmalara karşı korunaklıdır."})
                pressured.append({"ticker": "Yüksek Borçlu Şirketler", "reason": "Küresel faiz belirsizliğinde borç çevirme maliyeti artar."})

    return {
        "favored": favored[:4],
        "pressured": pressured[:3],
    }
