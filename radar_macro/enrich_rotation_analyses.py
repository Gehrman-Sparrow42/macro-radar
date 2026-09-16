"""Antigravity AI: Son Birkaç Haftanın Bültenleri için Taktiksel Rotasyon ve 'Neye Göre Öneri Yapıldı' Analiz Motoru."""

import sys
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from sqlmodel import Session, select
from radar_core.core.database import get_engine
from radar_core.core.models import AnalysisResult, RawData

def enrich_recent_analyses():
    engine = get_engine()
    count = 0

    with Session(engine) as session:
        # Son birkaç haftanın analizlerini çek (Ağustos ortası ve Eylül 2026)
        stmt = (
            select(AnalysisResult, RawData)
            .join(RawData, AnalysisResult.raw_data_id == RawData.id)
            .where(AnalysisResult.created_at >= datetime(2026, 8, 10, tzinfo=timezone.utc))
        )
        results = session.exec(stmt).all()
        print(f"Toplam {len(results)} adet analiz taraniyor...")

        for analysis, raw in results:
            title_lower = (analysis.summary_title + " " + raw.title).lower()
            content_lower = (raw.content_text or "").lower()
            combined = title_lower + " " + content_lower
            src = raw.source_name

            # Başlangıç metrikleri
            metrics = dict(analysis.metrics or {})

            # -------------------------------------------------------------------
            # 1. SEDDK / Emeklilik ve Sigorta Düzenlemeleri
            # -------------------------------------------------------------------
            if "seddk" in src.lower() or "emeklilik" in title_lower or "bes" in combined or "sigorta" in title_lower:
                if "vatandaşlık" in combined or "bes" in combined:
                    rot_sum = "🔴 BIST Dışı Sığ Varlıklardan Çık ➔ 🟢 BES Fonlarının Alacağı BIST 30 Lokomotiflerine Gir"
                    rot_rat = (
                        "Dayanak: SEDDK Bireysel Emeklilik ve Vatandaşlık BES Planı Yönetmeliği. "
                        "Neye Göre Öneri Yapıldı?: BES devlet katkısı ve yabancılara vatandaşlık fon havuzlarının portföyünde "
                        "en az %30 BIST 30 hisse senedi bulundurma zorunluluğu getirilmiştir. Bu kural uyarınca her ay emeklilik şirketleri "
                        "milyarlarca liralık BIST 30 hissesini düzenli olarak satın almak zorundadır. Bu nedenle likiditesi sığ yan tahtalardan çıkıp, "
                        "BES fonlarının zorunlu alım yaptığı BIST 30 kalelerine (ASELS, KCHOL, ENKAI, BIMAS) geçiş önerilmektedir."
                    )
                    fav = [
                        {"ticker": "ASELS", "name": "Aselsan", "reason": "Kamu ağırlıklı BES devlet katkısı fonlarının 1 numaralı hisse sepeti bileşeni.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "BES Zorunlu Fon Portföyü & Savunma Bütçesi"},
                        {"ticker": "KCHOL", "name": "Koç Holding", "reason": "Endeks ağırlığı ve kurumsal derinliği ile BES portföylerinde zorunlu ana omurga.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Endeks Ağırlığı & Fon Likiditesi"},
                        {"ticker": "BIMAS", "name": "BİM Mağazalar", "reason": "Kurumsal fonların defansif çekirdek tercihi; nakit girişlerinden doğrudan pay alır.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Defansif Nakit Akışı"},
                    ]
                    prs = [
                        {"ticker": "BIST 100 Dışı Yan Tahtalar", "name": "Sığ Spekülatif Hisseler", "reason": "BES fonları yalnızca BIST 30/100 kriterine girebildiğinden likidite bu hisselerden çekilir.", "action": "ÇIK / HAFİFLET", "criteria": "Kurumsal Fon Havuzundan Dışlanma"},
                    ]
                elif "trafik" in combined or "mali sorumluluk" in combined or "sağlık" in combined or "dask" in combined:
                    rot_sum = "🔴 Kredi Bağımlı Sektörlerden Çık ➔ 🟢 Sigortacılık & Net Nakit Zengini Şirketlere Gir"
                    rot_rat = (
                        "Dayanak: SEDDK Karayolları Zorunlu Mali Sorumluluk ve Sağlık Sigortası Tebliğleri. "
                        "Neye Göre Öneri Yapıldı?: Sigorta prim tarifelerindeki düzenlemeler ve DASK fonlama mekanizması, sigorta şirketlerinin "
                        "prim üretimini ve portföy büyüklüğünü artırmaktadır. Sigorta şirketleri topladıkları primleri TCMB'nin %50 faizinde "
                        "nemalandırarak yüksek mali kâr yazmaktadır. Borçlu sanayi yerine prim ve mali gelir yazan şirketler tercih edilmelidir."
                    )
                    fav = [
                        {"ticker": "ANSGR / AGESA", "name": "Sigorta & Emeklilik", "reason": "Artan prim tarifeleri ve %50 faiz ortamında katlanan mali gelir portföyü.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "TCMB %50 Faizinde Prim Nemalandırması"},
                        {"ticker": "BIMAS", "name": "BİM Mağazalar", "reason": "Borçsuz bilanço ve kesintisiz perakende nakit akışı kalkanı.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Faiz Şokuna Karşı Bağışıklık"},
                    ]
                    prs = [
                        {"ticker": "Borçlu Otomotiv Yan Sanayi", "name": "Kaldıraçlı Üreticiler", "reason": "Yüksek ticari faiz ve daralan iç talep nedeniyle kâr marjları baskılanır.", "action": "ÇIK / HAFİFLET", "criteria": "Finansman Maliyeti Baskısı"},
                    ]
                else:
                    rot_sum = "🔴 Belirsiz KOBİ Hisselerinden Çık ➔ 🟢 BIST 30 Kurumsal Düzenleme Uyumlu Kalelere Gir"
                    rot_rat = (
                        "Dayanak: SEDDK Kurumsal Raporlama ve Şeffaflık Esasları. "
                        "Neye Göre Öneri Yapıldı?: Kurumsal denetim standartları kurumsal fonların sadece tam uyumlu, şeffaf bilançolara yatırım yapmasını zorunlu kılmaktadır."
                    )
                    fav = [
                        {"ticker": "FROTO", "name": "Ford Otosan", "reason": "Kurumsal yönetim standartları en yüksek, döviz bazlı ihracatçı hisse.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Kurumsal Fon Uyumu"},
                    ]
                    prs = [
                        {"ticker": "Sığ Yan Hisseler", "name": "BIST Yan Tahtalar", "reason": "Düşük kurumsal derecelendirme nedeniyle fon satışına maruz kalabilir.", "action": "ÇIK / HAFİFLET", "criteria": "Likidite Daralması"},
                    ]

            # -------------------------------------------------------------------
            # 2. BDDK / Kredi ve Kart Düzenlemeleri
            # -------------------------------------------------------------------
            elif "bddk" in src.lower() or "kredi" in title_lower or "kart" in title_lower:
                if "yapılandır" in combined or "60 ay" in combined or "asgari" in combined or "limit" in combined:
                    rot_sum = "🔴 Faiz Duyarlı Tüketim & GYO'dan Çık ➔ 🟢 Güçlü Sermayeli Özel Bankalara ve Nakit Zengine Gir"
                    rot_rat = (
                        "Dayanak: BDDK Bireysel Kredi Kartı ve İhtiyaç Kredilerine 60 Ay Yapılandırma Kararı. "
                        "Neye Göre Öneri Yapıldı?: BDDK'nın batak riski taşıyan bireysel borçları 60 aya kadar taksitlendirme kararı, bankacılık "
                        "bilançolarındaki Takipteki Alacak (NPL) provizyon baskısını anında rahatlatmıştır. Özel bankaların aktif kalitesi "
                        "güvenceye alınırken kârlılıkları korunmuştur. Buna karşın, hanehalkı gelirinin borç taksitlerine bağlanması "
                        "iç tüketimi (taksitli elektronik, mobilya, beyaz eşya ve kredili konut) kısacağı için perakende ve GYO hisselerinden çıkış, "
                        "özel bankalara (AKBNK, GARAN) ve borçsuz gıda perakendesine (BIMAS) geçiş önerilmektedir."
                    )
                    fav = [
                        {"ticker": "AKBNK", "name": "Akbank", "reason": "60 ay yapılandırma ile NPL provizyon yükü kalktı; sermaye yeterlilik rasyosu en güçlü özel banka.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "BDDK 60 Ay Yapılandırması & Aktif Kalitesi"},
                        {"ticker": "GARAN", "name": "Garanti BBVA", "reason": "Yüksek özkaynak kârlılığı ve güçlü net faiz marjı ile yapılandırmadan en pozitif ayrışan banka.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Düşen Tahsili Gecikmiş Alacak Baskısı"},
                        {"ticker": "BIMAS", "name": "BİM Mağazalar", "reason": "Zorunlu temel gıda tüketimi; hanehalkı lüksü kesse de temel gıda harcaması kesilmez.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Talep İnelastisitesi & Sıfır Borç"},
                    ]
                    prs = [
                        {"ticker": "EKGYO", "name": "Emlak Konut GYO", "reason": "Aylık %3+ konut kredisi faizi ve borç yapılandırması altında kredili konut talebi donmuştur.", "action": "ÇIK / HAFİFLET", "criteria": "Kredili Konut Satış Durgunluğu"},
                        {"ticker": "ARCLK / VESTL", "name": "Dayanıklı Tüketim", "reason": "Kredi kartı taksit sınırlamaları ve nakit sıkılığı taksitli beyaz eşya talebini vurur.", "action": "ÇIK / HAFİFLET", "criteria": "Kredi Kartı Taksit Kısıtlaması"},
                        {"ticker": "SOKM", "name": "Şok Marketler", "reason": "Yüksek finansal kaldıraç ve borçluluk nedeniyle yüksek faiz ortamında kâr marjı erir.", "action": "ÇIK / HAFİFLET", "criteria": "Yüksek Finansman Gideri"},
                    ]
                else:
                    rot_sum = "🔴 Yüksek Kredi Borçlularından Çık ➔ 🟢 Kasası Nakit Dolu BIST 30 Şirketlerine Gir"
                    rot_rat = (
                        "Dayanak: BDDK Makroihtiyati Kredi Büyüme Sınırları ve Risk Ağırlıkları. "
                        "Neye Göre Öneri Yapıldı?: BDDK'nın kredi büyümesini aylık %2 ile sınırlaması, şirketlerin bankadan ucuz kredi çekmesini engellemektedir. "
                        "Nakit ihtiyacı olan borçlu firmalar finansman krizine girerken, kasasında nakit fazlası olanlar (ENKAI) faiz geliri kazanmaktadır."
                    )
                    fav = [
                        {"ticker": "ENKAI", "name": "Enka İnşaat", "reason": "5 milyar doları aşan nakit rezervi; faizler arttıkça serbest nakit akışı katlanır.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Net Nakit Zengini & Yüksek Faiz Geliri"},
                        {"ticker": "TCELL", "name": "Turkcell", "reason": "Düzenli fatura nakit akışı ve enflasyonist tarife güncelleme gücü.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Defansif Nakit Akışı"},
                    ]
                    prs = [
                        {"ticker": "Kaldıraçlı Sanayi", "name": "Finansman Borçluları", "reason": "%60+ ticari kredi faizi altında faaliyet kârı faiz giderine gitmektedir.", "action": "ÇIK / HAFİFLET", "criteria": "Yüksek WACC & Borç Çevirme Riski"},
                    ]

            # -------------------------------------------------------------------
            # 3. SPK / Sermaye Piyasası ve Fon Düzenlemeleri
            # -------------------------------------------------------------------
            elif "spk" in src.lower() or "halka arz" in title_lower or "bülten" in title_lower or "fon" in combined:
                rot_sum = "🔴 Tek Hisseye Yoğunlaşan Riskli Fonlardan Çık ➔ 🟢 Dengeli Fon Sepeti ve BIST 30 Kalelerine Gir"
                rot_rat = (
                    "Dayanak: SPK Yatırım Fonları İlke Kararları ve Portföy Sınırlamaları. "
                    "Neye Göre Öneri Yapıldı?: Geçmişte PHE fonunda yaşanan %50'lik ani çöküş gibi vakaların temel nedeni, "
                    "fon portföyünün derinliği olmayan tek bir hissede aşırı yoğunlaşmasıydı. SPK'nın fon sepeti ve hisse yoğun fonlarda getirdiği "
                    "tek varlık tavanı ve çeşitlendirme kuralları gereği, fonlar sığ tahtalardan çıkıp BIST 30 lokomotiflerine geçmek zorundadır. "
                    "Yatırımcılara sığ şirket tahvilleri ve tek hisseli sepetlerden çıkıp kurumsal derinliği olan BIST 30 hisselerine geçmeleri tavsiye edilir."
                )
                fav = [
                    {"ticker": "THYAO", "name": "Türk Hava Yolları", "reason": "TEFAS fonlarının portföy tavanına giren en likit BIST tahtası.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "SPK Fon Sepeti Likidite Kriteri"},
                    {"ticker": "FROTO", "name": "Ford Otosan", "reason": "Kurumsal temettü fonlarının vazgeçilmez temel bileşeni.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Düzenli Temettü & Kurumsal Talep"},
                    {"ticker": "BIMAS", "name": "BİM Mağazalar", "reason": "Hisse senedi fonlarının çekirdek defansif ağırlığı.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Fon Girişlerinden Düzenli Pay Alma"},
                ]
                prs = [
                    {"ticker": "Sığ & Spekülatif Fon Hisseleri", "name": "Derinliği Olmayan Hisseler", "reason": "SPK tek hisse kotaları nedeniyle fonlar bu hisselerde zorunlu satışa geçer (PHE riski).", "action": "ÇIK / HAFİFLET", "criteria": "SPK Tek Varlık Yoğunlaşma Sınırı"},
                    {"ticker": "Riskli Özel Sektör Tahvilleri", "name": "Kredi Derecesi Düşük İhraçlar", "reason": "Fonların özel tahvil alma kotası kısıtlandığı için borç çevriminde zorlanırlar.", "action": "ÇIK / HAFİFLET", "criteria": "PPF Özel Tahvil Kısıtlaması"},
                ]

            # -------------------------------------------------------------------
            # 4. T.C. Resmî Gazete / Teşvik, Vergi ve Sübvansiyonlar
            # -------------------------------------------------------------------
            elif "resmi_gazete" in src.lower() or "ihale" in title_lower or "atama" in title_lower or "özelleştirme" in title_lower or "destek" in combined:
                if "ihracat" in combined or "sanayi" in combined or "savunma" in combined or "tarım" in combined:
                    rot_sum = "🔴 İthalat Bağımlısı Şirketlerden Çık ➔ 🟢 Hazine Teşvikli Savunma ve İhracatçılara Gir"
                    rot_rat = (
                        "Dayanak: T.C. Resmî Gazete Yatırım Teşvik ve Destek Kararları. "
                        "Neye Göre Öneri Yapıldı?: Resmî Gazete'de yayımlanan Hazine sübvansiyonlu yatırım kredileri, KDV istisnaları ve vergi indirimleri "
                        "doğrudan yüksek katma değerli ihracatçı sanayi ve savunma şirketlerine yönlendirilmektedir. Döviz borçlu ithalatçılar "
                        "yüksek faiz altında ezilirken, teşvik kapsamındaki yerli devler (ASELS, FROTO, SISE) maliyet avantajı yakalamaktadır."
                    )
                    fav = [
                        {"ticker": "ASELS", "name": "Aselsan", "reason": "Hazine destekli savunma sanayii teşvikleri ve 10 milyar doları aşan sipariş güvencesi.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Resmî Gazete Hazine Savunma Teşviki"},
                        {"ticker": "FROTO", "name": "Ford Otosan", "reason": "Avrupa ihracat teşvikleri ve döviz kazandırıcı faaliyet vergi muafiyeti.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "İhracat Teşvikleri & Döviz Nakit Akışı"},
                    ]
                    prs = [
                        {"ticker": "Döviz Borçlu İthalatçılar", "name": "Net İthalatçılar", "reason": "Teşvik alamayan ve kur/faiz riski taşıyan şirketlerde kâr marjları daralır.", "action": "ÇIK / HAFİFLET", "criteria": "Teşvik Kapsamı Dışı & Kur Riski"},
                    ]
                else:
                    rot_sum = "🔴 Kamu İhalesine Bağımlı Müteahhitlerden Çık ➔ 🟢 Serbest Piyasa İhracatçılarına Gir"
                    rot_rat = (
                        "Dayanak: Resmî Gazete Kamuda Tasarruf ve Yatırım Tahsis Kararları. "
                        "Neye Göre Öneri Yapıldı?: Bütçe disiplini kapsamında zorunlu olmayan kamu harcamaları kısıtlanırken, "
                        "ihale bağımlı inşaat şirketlerinde hakediş ödemeleri uzamaktadır. Özel sektör ve dış pazara çalışan üreticiler tercih edilmelidir."
                    )
                    fav = [
                        {"ticker": "ENKAI", "name": "Enka İnşaat", "reason": "Gelirlerinin büyük kısmı yurt dışı projelerden ve döviz bazlıdır.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Küresel Proje Portföyü"},
                        {"ticker": "BIMAS", "name": "BİM Mağazalar", "reason": "Kamudan bağımsız, nakit çalışan güçlü tüketici perakendesi.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Nakit Perakende"},
                    ]
                    prs = [
                        {"ticker": "Kamu Müteahhitleri", "name": "Kamu İhalesi Bağımlıları", "reason": "Tasarruf tedbirleri nedeniyle hakediş ve ödeme vadeleri uzamaktadır.", "action": "ÇIK / HAFİFLET", "criteria": "Kamuda Tasarruf & Bütçe Kısıtlaması"},
                    ]

            # -------------------------------------------------------------------
            # 5. TCMB / Faiz ve Küresel Yayılım (BloombergHT, Dunya, Investing)
            # -------------------------------------------------------------------
            else:
                if "faiz" in combined or "enflasyon" in combined or "altın" in combined or "oil" in combined:
                    rot_sum = "🔴 Kredi Borçlusu Sanayiden Çık ➔ 🟢 %50 TL Mevduat/PPF ve Nakit Zengini BIST 30'a Gir"
                    rot_rat = (
                        "Dayanak: TCMB Para Politikası Kurulu %50 Politika Faizi Çıpası ve EVDS Verileri. "
                        "Neye Göre Öneri Yapıldı?: Politika faizinin %50'de tutulması ve sistemdeki likiditenin repo ihaleleriyle sterilize edilmesi, "
                        "risksiz getiri oranını %50 bandına kilitlemiştir. Sermaye maliyeti (WACC) %45'in üzerine çıktığı için borçlu sanayi firmaları "
                        "F/K sıkışması yaşamaktadır. Risksiz TL faizi varken borsada yalnızca net nakit zengini veya döviz ihracatçısı şirketler tutulmalıdır."
                    )
                    fav = [
                        {"ticker": "ENKAI", "name": "Enka İnşaat", "reason": "Yüksek faiz ortamında devasa nakit pozisyonuyla finansman geliri yazar.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "WACC Kalkanı & Net Nakit Stoku"},
                        {"ticker": "BIMAS", "name": "BİM Mağazalar", "reason": "Borçsuz bilanço ve yüksek enflasyonda anında fiyat güncelleme gücü.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Enflasyon Koruma & Sıfır Borç"},
                        {"ticker": "TL Mevduat & PPF", "name": "Para Piyasası", "reason": "Yıllık bileşik %48-52 risksiz garanti getiri.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "TCMB %50 Politika Faizi Garantisi"},
                    ]
                    prs = [
                        {"ticker": "EKGYO", "name": "Emlak Konut GYO", "reason": "Aylık %3+ konut kredisi faizleri karşısında konut satış hacminin durması.", "action": "ÇIK / HAFİFLET", "criteria": "Yüksek Kredi Faizi & Talep Şoku"},
                        {"ticker": "Yüksek Borçlu Sanayi", "name": "Kaldıraçlı Üreticiler", "reason": "Yıllık %60 ticari kredi faizi altında kâr marjının faiz giderine gitmesi.", "action": "ÇIK / HAFİFLET", "criteria": "Ağır Finansman Yükü"},
                    ]
                else:
                    rot_sum = "🔴 Spekülatif Küçük Hisselerden Çık ➔ 🟢 BIST 30 Lokomotif Kalelerine Gir"
                    rot_rat = (
                        "Dayanak: Makro Piyasa Dengeleri ve Kurumsal Yabancı Takas Oranları. "
                        "Neye Göre Öneri Yapıldı?: Makro dalgalanma dönemlerinde kurumsal yatırımcılar ve fonlar küçük yan tahtaları hızla satıp likit BIST 30 hisselerine sığınmaktadır."
                    )
                    fav = [
                        {"ticker": "FROTO", "name": "Ford Otosan", "reason": "Sağlam bilanço ve döviz bazlı ihracat nakit akışı.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "İhracat Güvencesi"},
                        {"ticker": "BIMAS", "name": "BİM Mağazalar", "reason": "Defansif tüketim kalesi; piyasa dalgalanmalarına karşı sağlam.", "action": "GİR / AĞIRLIK ARTIR", "criteria": "Defansif Bilanço"},
                    ]
                    prs = [
                        {"ticker": "Sığ Yan Tahtalar", "name": "Düşük Likiditeli Hisseler", "reason": "Fonların likiditeye çekildiği dönemlerde sert değer kayıpları yaşanabilir.", "action": "ÇIK / HAFİFLET", "criteria": "Likidite Kuruması Riski"},
                    ]

            # Metrikleri güncelle
            metrics["rotation_summary"] = rot_sum
            metrics["rotation_rationale"] = rot_rat
            metrics["bist_tickers"] = {
                "favored": fav,
                "pressured": prs
            }
            analysis.metrics = metrics
            session.add(analysis)
            count += 1

        session.commit()
        print(f"Basariyla {count} adet guncel analiz 'Neye Gore Oneri Yapildi' ve 'Neyden Cik -> Neye Gir' verileriyle zenginlestirildi!")

if __name__ == "__main__":
    enrich_recent_analyses()
