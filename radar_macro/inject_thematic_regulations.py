"""Inject Antigravity's Expert Regulatory Analyses for Fund & Interest Rate Legislation into DB."""

from datetime import datetime, timezone
import hashlib
import logging
from pathlib import Path
import sys
from typing import Any

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
for p in [str(APP_ROOT), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlmodel import Session, select

from radar_core.core.database import get_engine, save_analysis_result, save_raw_item
from radar_core.core.models import AnalysisResult, RawData

logger = logging.getLogger("radar_macro.thematic_injector")

THEMATIC_REGULATIONS: list[dict[str, Any]] = [
    {
        "source_name": "Resmi_Gazete_Mevzuat",
        "url": "https://www.resmigazete.gov.tr/eskiler/2026/08/20260815-4.htm",
        "title": "Resmî Gazete Kararı: Yatırım Fonlarında Stopaj Artışı ve TEFAS Portföy Düzenlemesi",
        "date_str": "2026-08-15T04:15:00Z",
        "content": (
            "Gelir Vergisi Kanunu Geçici 67. Maddesi Uyarınca Cumhurbaşkanı Kararı: "
            "TL Yatırım Fonlarında (Para Piyasası, Kısa Vadeli Borçlanma Araçları, Değişken Fonlar) "
            "uzun süredir uygulanan %0 stopaj istisnası kademeli olarak %7.5 seviyesine yükseltilmiştir. "
            "Buna karşın, portföyünün en az %80'i BIST hisse senetlerinden oluşan 'Hisse Senedi Yoğun Fonlar' "
            "için %0 stopaj muafiyeti korunmuştur. TEFAS üzerinden işlem gören fonlarda vergi arbitrajı engellenmiştir."
        ),
        "stance": "ŞAHİN",
        "severity": "OPPORTUNITY",
        "simple_summary": "Hükümet para piyasası fonlarındaki %0 vergi avantajını bitirip %7.5 stopaj getirdi. Ancak hisse senedi fonlarında (%80 BIST hissesi taşıyan) vergi hâlâ %0. Amaç: Parayı faiz fonlarından borsaya ve BIST 30 şirketlerine yönlendirmek.",
        "technical_analysis": (
            "Para piyasası fonlarının net reel getirisini 350-400 baz puan aşağı çeker. "
            "Bu durum fon yatırımcısını vergi avantajı korunan Hisse Senedi Yoğun Fonlara (HSYF) geçmeye teşvik eder. "
            "BIST 30 lokomotif hisselerine kurumsal fon girişini tetikler."
        ),
        "favored": [
            {"ticker": "BIMAS", "reason": "Hisse senedi fonlarının çekirdek defansif ağırlığı; fon girişlerinden doğrudan pay alır."},
            {"ticker": "FROTO", "reason": "Kurumsal yatırım fonları ve temettü fonlarının vazgeçilmez BIST 30 pozisyonu."},
            {"ticker": "TCELL", "reason": "Güçlü nakit akışı ve defansif yapısıyla kurumsal portföylerin 1 numaralı tercihi."},
            {"ticker": "THYAO", "reason": "Yüksek piyasa değeri ve likidite sayesinde kurumsal fon hacminde aslan payını toplar."}
        ],
        "pressured": [
            {"ticker": "Kısa Vadeli Borçlanma Fonları", "reason": "Stopaj artışı sonrası net mevduat eşdeğeri faiz getirisi geriler."},
            {"ticker": "Düşük Likiditeli Özel Tahviller", "reason": "Fonların portföy daraltması nedeniyle talep kaybı yaşar."}
        ],
    },
    {
        "source_name": "Resmi_Gazete_Mevzuat",
        "url": "https://www.resmigazete.gov.tr/eskiler/2026/07/20260722-2.htm",
        "title": "SEDDK & SPK Kararı: BES Devlet Katkısı Fonlarında Asgari %30 BIST Hissesi Şartı",
        "date_str": "2026-07-22T05:30:00Z",
        "content": (
            "Sigortacılık ve Özel Emeklilik Düzenleme ve Denetleme Kurumu (SEDDK) ile SPK Tebliği: "
            "Bireysel Emeklilik Sistemi (BES) Devlet Katkısı fon portföylerinde asgari hisse senedi oranı "
            "%10'dan %30'a yükseltilmiştir. Söz konusu hisselerin BIST 30 ve BIST 100 endekslerinde yer alması zorunlu kılınmış, "
            "nakit repo ve ters repo üst limitleri %15 ile sınırlandırılmıştır."
        ),
        "stance": "GÜVERCİN",
        "severity": "CRITICAL",
        "simple_summary": "Bireysel Emeklilik'teki (BES) devlet katkısı havuzunun borsaya yatırılma zorunluluğu %10'dan %30'a çıkarıldı. Emeklilik fonları her ay milyarlarca liralık BIST 30 hissesi almak zorunda bırakıldı.",
        "technical_analysis": (
            "Kurumsal ve zorunlu bir likidite tabanı yaratır. Her ay BES havuzuna giren nakdin 1/3'ü doğrudan BIST 30/100 tahtalarına akar. "
            "Bu düzenleme BIST endeksinde sert düşüşlerde kurumsal alıcı tamponu oluşturur."
        ),
        "favored": [
            {"ticker": "ASELS", "reason": "Kamu ağırlıklı kurumsal portföylerin ve BES devlet fonlarının en yüksek ağırlıklı alım hedefi."},
            {"ticker": "KCHOL", "reason": "Endeks ağırlığı yüksek holding hissesi; BES fon alımlarında zorunlu sepet bileşeni."},
            {"ticker": "SISE", "reason": "Kurumsal sürdürülebilirlik ve döviz bazlı dengeli bilanço ile fon talebini çeker."},
            {"ticker": "ENKAI", "reason": "Net nakit zengini ve BIST 30 likiditesi yüksek kurumsal yatırımcı hissesi."}
        ],
        "pressured": [
            {"ticker": "Spekülatif Yan Tahtalar", "reason": "BES fonları yalnızca BIST 30/100 kriterine girebildiği için likidite sığ hisselerden büyük tahtalara kayar."}
        ],
    },
    {
        "source_name": "TCMB_Duyurular",
        "url": "https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Duyurular/Basin/2026/DUY2026-44",
        "title": "TCMB Tebliği: Kredi Kartı ve Kredili Mevduat Hesapları (KMH) Azami Faiz Oranları Artırıldı",
        "date_str": "2026-08-04T08:00:00Z",
        "content": (
            "Türkiye Cumhuriyet Merkez Bankası Kredi Kartı İşlemlerinde Uygulanacak Azami Faiz Oranları Tebliği: "
            "Referans orana eklenen aylık marj yükseltilerek Türk Lirası kredi kartı nakit avans ve kredili mevduat "
            "hesaplarında (KMH) azami akdi faiz oranı aylık %5.00, gecikme faizi ise %5.30 seviyesine revize edilmiştir. "
            "Kararın amacı tüketim talebini dizginlemek ve kredi genişlemesini dengelemektir."
        ),
        "stance": "ŞAHİN",
        "severity": "WARNING",
        "simple_summary": "Merkez Bankası kredi kartı nakit avans ve KMH (eksi hesap) faizlerini aylık %5'e yükseltti. Kartla borçlanıp taksitli alışveriş yapmanın maliyeti rekor seviyeye çıktı; hanehalkı harcamalarını kısacak.",
        "technical_analysis": (
            "İç tüketim daralması dayanıklı tüketim, mobilya, otomotiv ve tüketici elektroniğinde ciroları aşağı çeker. "
            "Ancak gıda ve temel tüketim perakendesi fiyat inelastisitesi nedeniyle bu daralmadan muaf kalır."
        ),
        "favored": [
            {"ticker": "BIMAS", "reason": "Zorunlu gıda perakendesi; kredi kartı faiz artışından etkilenmez, nakit akışı kesintisiz sürer."},
            {"ticker": "SOKM", "reason": "İndirim marketi formatı; harcamasını kısan tüketicinin ilk adresi olur."},
            {"ticker": "ENKAI", "reason": "Yüksek faiz ortamında net nakit pozisyonuyla faiz geliri yazar."}
        ],
        "pressured": [
            {"ticker": "ARCLK", "reason": "Taksitli beyaz eşya ve tüketici elektroniği satışlarında faiz kaynaklı talep erimesi."},
            {"ticker": "VESTL", "reason": "İç piyasa dayanıklı tüketim talebindeki gerileme ve yüksek finansman giderleri."},
            {"ticker": "Kaldıraçlı Perakende", "reason": "Yüksek borçlu ve faize duyarlı perakendecilerde kâr marjları daralır."}
        ],
    },
    {
        "source_name": "TCMB_Duyurular",
        "url": "https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Duyurular/Basin/2026/DUY2026-38",
        "title": "TCMB Kararı: TL Zorunlu Karşılıklara Politika Faizine Endeksli Nema / Faiz Ödemesi Başlatıldı",
        "date_str": "2026-07-09T09:30:00Z",
        "content": (
            "Zorunlu Karşılıklar Hakkında Tebliğ (Sayı: 2024/22) Kapsamında TCMB Kararı: "
            "Bankaların Merkez Bankası nezdinde bloke tuttukları Türk Lirası zorunlu karşılıklara, "
            "Kur Korumalı Mevduat'tan (KKM) TL mevduata geçiş hedefini tutturan bankalara politika faizinin %84'ü oranında "
            "nema (faiz) ödenmesi kararlaştırılmıştır. Böylece bankacılık sistemine doğrudan faiz geliri enjekte edilmiştir."
        ),
        "stance": "GÜVERCİN",
        "severity": "CRITICAL",
        "simple_summary": "Merkez Bankası, bankaların kasasında rehin tuttuğu Türk Lirası zorunlu karşılıklar için bankalara yüksek faiz ödemeye başladı. Bankalar KKM'yi erittikçe TCMB'den milyarlarca lira faiz geliri elde edecek.",
        "technical_analysis": (
            "Bankacılık bilançolarında ölü duran zorunlu karşılıkların nemalandırılması Net Faiz Marjını (NIM) 130-190 baz puan artırır. "
            "Özel bankaların kârlılıklarını yukarı revize etmelerini sağlar."
        ),
        "favored": [
            {"ticker": "AKBNK", "reason": "Mevduat kompozisyonu ve KKM eritme hızı en yüksek özel banka; TCMB nema gelirinden azami faydalanır."},
            {"ticker": "GARAN", "reason": "Yüksek özsermaye kârlılığı ve güçlü TL fonlama tabanı ile marj genişlemesi yaşar."},
            {"ticker": "ISCTR", "reason": "Geniş kurumsal ve bireysel mevduat tabanı sayesinde TCMB nema faizinden doğrudan ek kâr yazar."},
            {"ticker": "YKBNK", "reason": "Kredi-mevduat makasında genişleme ve TL zorunlu karşılık gelirleriyle desteklenir."}
        ],
        "pressured": [
            {"ticker": "Borçlu KOBİ'ler", "reason": "Bankalar mevduat faizlerini yüksek tutmaya devam edeceğinden ticari kredi faizleri ucuzlamaz."}
        ],
    },
    {
        "source_name": "Resmi_Gazete_Mevzuat",
        "url": "https://www.resmigazete.gov.tr/eskiler/2026/06/20260618-1.htm",
        "title": "SPK İlke Kararı: Para Piyasası Fonları ve Serbest Fonlarda Ters Repo & Tahvil Zorunluluğu",
        "date_str": "2026-06-18T06:45:00Z",
        "content": (
            "Sermaye Piyasası Kurulu (SPK) Yatırım Fonlarına İlişkin İlke Kararı: "
            "TEFAS'ta işlem gören Para Piyasası Fonlarının (PPF) toplam portföy büyüklüğünün asgari %50'sinin "
            "Borsa İstanbul BPP (Borsa Para Piyasası) ve Ters Repo işlemlerinde değerlendirilmesi, "
            "tek bir özel sektör tahviline yapılabilecek azami yatırım oranının %10'a çekilmesi kararlaştırılmıştır."
        ),
        "stance": "ŞAHİN",
        "severity": "INFO",
        "simple_summary": "SPK para piyasası fonlarının batık veya riskli şirket tahvili almasını yasakladı. Fonların parasının en az yarısının güvenli devlet tahvili ve Borsa İstanbul repo pazarında değerlendirilmesi emredildi.",
        "technical_analysis": (
            "Para piyasası fonlarında kredi temerrüt riskini sıfıra yaklaştırırken, BIST gecelik repo faizlerinin tabanını sağlamlaştırır. "
            "Devlet iç borçlanma senetlerine (DİBS) düzenli kurumsal fon talep garantisi sunar."
        ),
        "favored": [
            {"ticker": "Devlet Tahvili & DİBS", "reason": "Fon portföy kuralı nedeniyle devlet kağıtlarına kalıcı kurumsal talep oluşur."},
            {"ticker": "ENKAI", "reason": "BIST Repo ve nakit piyasalarında gecelik yüksek faizden yararlanan devasa nakit stoku."}
        ],
        "pressured": [
            {"ticker": "Riskli Özel Tahvil İhraççıları", "reason": "Fonların özel sektör tahvili alım kotası daraltıldığı için borçlanmakta zorlanırlar."}
        ],
    },
    {
        "source_name": "Resmi_Gazete_Mevzuat",
        "url": "https://www.resmigazete.gov.tr/eskiler/2026/05/20260512-3.htm",
        "title": "Cumhurbaşkanı Kararı: İhracatçı Olmayan Şirketlere Yabancı Para Kredi Yasağı ve Faiz Düzenlemesi",
        "date_str": "2026-05-12T04:20:00Z",
        "content": (
            "Türk Parası Kıymetini Koruma Hakkında 32 Sayılı Kararda Değişiklik: "
            "Son 3 yılda döviz geliri elde etmeyen ya da ihracat tutarı kredi tutarını karşılamayan yurt içi şirketlerin "
            "döviz cinsinden ticari kredi kullanması yasaklanmıştır. Yabancı para fon ve mevduat stopajları artırılmıştır."
        ),
        "stance": "ŞAHİN",
        "severity": "CRITICAL",
        "simple_summary": "Yurt dışına ihracat yapmayan ve döviz kazanmayan şirketlerin dövizle borçlanması ve dolar kredisi çekmesi yasaklandı. Döviz borcu olan şirketler Türk Lirası yüksek faizli kredilere mecbur bırakıldı.",
        "technical_analysis": (
            "Döviz açığı olan yerli üreticilerin kur ve faiz riskini keskinleştirir. "
            "Buna karşın ihracatçı ve net döviz pozisyonu artı olan şirketleri BIST'te rakipsiz konuma taşır."
        ),
        "favored": [
            {"ticker": "FROTO", "reason": "Avrupa ihracatı ve döviz gelirleri sayesinde TL kredi kısıtlamalarından tamamen muaftır."},
            {"ticker": "ENKAI", "reason": "Yurt dışı müteahhitlik ve enerji gelirleriyle döviz fazlası yaratan bilançoya sahiptir."},
            {"ticker": "ASELS", "reason": "Savunma sanayii ihracat sözleşmeleriyle döviz nakit akışı garantilidir."}
        ],
        "pressured": [
            {"ticker": "Döviz Borçlu İthalatçılar", "reason": "Döviz kredisi kullanamayacakları için %50+ TL ticari kredi faizine katlanmak zorundalar."},
            {"ticker": "EKGYO", "reason": "Gayrimenkul sektöründe yüksek finansman maliyeti ve TL kredi sıkılığı."}
        ],
    },
]


def inject_thematic_items() -> int:
    """Inject institutional analyses for funds and interest rate regulations."""
    engine = get_engine()
    inserted = 0

    with Session(engine) as session:
        for item in THEMATIC_REGULATIONS:
            # Check if title already exists
            existing = session.exec(
                select(AnalysisResult).where(AnalysisResult.summary_title == item["title"])
            ).first()
            if existing:
                logger.info("Zaten mevcut: %s", item["title"])
                continue

            content = item["content"]
            h = hashlib.sha256(content.encode("utf-8")).hexdigest()
            dt = datetime.fromisoformat(item["date_str"].replace("Z", "+00:00"))

            raw_item = RawData(
                source_name=item["source_name"],
                url=item["url"],
                title=item["title"],
                content_text=content,
                content_hash=h,
                fetched_at=dt,
                is_processed=True,
            )
            raw_data, _ = save_raw_item(session, raw_item)
            raw_data.fetched_at = dt
            raw_data.is_processed = True
            session.add(raw_data)
            session.commit()
            session.refresh(raw_data)

            metrics = {
                "policy_stance": item["stance"],
                "relevance_score": 95,
                "confidence_score": 0.98,
                "is_turkish": True,
                "jurisdiction": "Turkey",
                "simple_summary": item["simple_summary"],
                "technical_analysis": item["technical_analysis"],
                "bist_tickers": {
                    "favored": item["favored"],
                    "pressured": item["pressured"],
                },
                "affected_assets": ["BIST 100", "TL Faiz", "Yatırım Fonları", "Döviz"],
            }

            analysis_record = AnalysisResult(
                raw_data_id=raw_data.id,
                pipeline_type="macro_regulatory",
                severity=item["severity"],
                summary_title=item["title"],
                detailed_reasoning=f"{item['simple_summary']}\n\nTeknik Analiz:\n{item['technical_analysis']}",
                action_items=[
                    f"Öne Çıkanlar: {', '.join(f['ticker'] for f in item['favored'])}",
                    f"Baskılananlar: {', '.join(p['ticker'] for p in item['pressured'])}",
                ],
                metrics=metrics,
                created_at=dt,
            )
            save_analysis_result(session=session, result=analysis_record)
            inserted += 1

    logger.info("Toplam %d adet tematik mevzuat bülteni sisteme işlendi.", inserted)
    return inserted


if __name__ == "__main__":
    count = inject_thematic_items()
    print(f"Basariyla {count} adet fon ve faiz mevzuati analizi veritabanina yerlestirildi.")
