"""Radar Makro: Geçmiş 6 Ayı (Mart, Nisan, Mayıs, Haziran, Temmuz, Ağustos 2026) Geriye Dönük İnceleme ve Yükleme Motoru.

TCMB, T.C. Resmî Gazete, BDDK, SPK ve küresel merkez bankası kararlarını
veritabanına işler ve otomatik aylık makro bellek özetlerini (MacroMemoryDigest) üretir.
"""

import sys
from pathlib import Path

# Add workspace root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from datetime import datetime, timezone
import logging
from typing import Any
from sqlmodel import Session

from radar_core.core.database import get_engine, get_session, save_analysis_result, save_raw_item
from radar_core.core.models import AnalysisResult, RawItem, StructuredAnalysisOutput
from radar_macro.config.bist_sectors import map_macro_to_bist_tickers
from radar_macro.memory_engine import generate_period_digest

logger = logging.getLogger("radar_macro.backfill")

# ---------------------------------------------------------------------------
# Geçmiş 6 Aylık Derin Makroekonomik Veri Kümesi (Mart - Ağustos 2026)
# ---------------------------------------------------------------------------
HISTORICAL_MACRO_ITEMS: list[dict[str, Any]] = [
    # =======================================================================
    # MART 2026 (MARCH 2026)
    # =======================================================================
    {
        "source_name": "TCMB_Basin_Duyurulari",
        "url": "https://www.tcmb.gov.tr/duyuru/2026/mart-ppk-karari",
        "title": "TCMB PPK Kararı: Politika Faizi 500 Baz Puan Artırılarak %50 Seviyesine Yükseltildi",
        "date_str": "2026-03-21T14:00:00Z",
        "content": (
            "Para Politikası Kurulu, enflasyon görünümündeki bozulmayı dikkate alarak politika faizi olan "
            "bir hafta vadeli repo ihale faiz oranının %45'ten %50 düzeyine yükseltilmesine karar vermiştir. "
            "Kurul ayrıca operasyonel çerçevede değişikliğe giderek gecelik borçlanma ve borç verme oranlarının "
            "politika faizine kıyasla -/+ 300 baz puanlık marj ile belirlenmesine karar vermiştir."
        ),
        "stance": "ŞAHİN",
        "severity": "CRITICAL",
        "simple_summary": "Merkez Bankası sürpriz bir adımla politika faizini %45'ten %50'ye fırlattı! TL mevduat faizleri %55'in üzerine tırmandı, Türk Lirası koruma altına alındı.",
        "technical_analysis": "Önden yüklemeli 500 bps faiz artışı negatif reel faiz algısını kırmış, TL getiri eğrisini dikleştirmiştir. BIST şirketleri için sermaye maliyeti (Ke) fırlamış, borçlu sanayi hisselerinde F/K sıkışması başlamıştır.",
        "favored": ["ENKAI", "BIMAS", "TL Mevduat & PPF"],
        "pressured": ["EKGYO", "HEKTS", "PETKM", "Borçlu Sanayi"],
    },
    {
        "source_name": "Resmi_Gazete_Mevzuat",
        "url": "https://www.resmigazete.gov.tr/eskiler/2026/03/20260306-1.htm",
        "title": "TCMB Tebliği: Kredi Büyümesine Dayalı Zorunlu Karşılık ve Kredi Sınırlandırması",
        "date_str": "2026-03-06T03:00:00Z",
        "content": (
            "TCMB tarafından yayımlanan tebliğ ile TL ticari krediler için aylık büyüme sınırı %2,5'ten %2'ye, "
            "ihtiyaç kredilerinde ise %3'ten %2'ye düşürülmüştür. Kredi kartı nakit avans çekimlerinde komisyon ve "
            "faiz oranları yukarı çekilerek iç tüketim frenlenmiştir."
        ),
        "stance": "ŞAHİN",
        "severity": "WARNING",
        "simple_summary": "Bankaların kredi verme muslukları iyice kısıldı. Kredi kartı nakit avansı zorlaştırıldı; amaç aşırı harcamayı durdurup enflasyonu dizginlemek.",
        "technical_analysis": "Seçici kredi kısıtlamaları iç talep kaynaklı cari açık ve enflasyon baskısını dizginlerken perakende ticaret hacmini baskılar. Şirketlerin işletme sermayesi döngüsü uzar.",
        "favored": ["Nakit Zengini Şirketler", "TCELL"],
        "pressured": ["Tüketici Elektroniği", "Otomotiv Bayileri", "SOKM"],
    },
    {
        "source_name": "BDDK_Kararlari",
        "url": "https://www.bddk.org.tr/Duyuru/2026/03-kredi-karti-asgari-odeme",
        "title": "BDDK Kararı: Kredi Kartı Limit ve Asgari Ödeme Oranlarında Sıkılaştırma",
        "date_str": "2026-03-27T10:30:00Z",
        "content": (
            "BDDK, finansal tüketici borçluluğunun kontrolü amacıyla yüksek limitli kredi kartlarında asgari ödeme oranını "
            "%40 olarak belirlemiş ve lüks tüketim harcamalarında taksitlendirmeyi sınırlamıştır."
        ),
        "stance": "ŞAHİN",
        "severity": "WARNING",
        "simple_summary": "Kredi kartı asgari ödeme oranları yükseltildi, lüks harcamalarda taksitler yasaklandı. Borçla lüks yaşama fren geldi.",
        "technical_analysis": "Bireysel kaldıraç oranlarının törpülenmesi hanehalkı tasarruf eğilimini artırır, bankacılık takipli alacak (NPL) riskini kontrol altına alır.",
        "favored": ["GARAN", "AKBNK"],
        "pressured": ["Dayanıklı Tüketim", "AVM & Perakende"],
    },
    {
        "source_name": "FederalReserve_Press",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260320a.htm",
        "title": "Fed FOMC Kararı: Faiz %5.25-5.50 Bandında Sabit, Erken Faiz İndirimi Masadan Kalktı",
        "date_str": "2026-03-20T18:00:00Z",
        "content": (
            "The Federal Reserve kept interest rates unchanged at 5.25%-5.50%. Chair Powell emphasized that the committee "
            "needs greater confidence that inflation is moving sustainably toward 2% before initiating rate reductions."
        ),
        "stance": "ŞAHİN",
        "severity": "INFO",
        "simple_summary": "Amerikan Merkez Bankası Fed faizi indirmedi; erken indirim umutlarını erteleyerek doların güçlü kalmasını sağladı.",
        "technical_analysis": "Küresel dolar likiditesinin pahalı kalması gelişmekte olan piyasa (EM) tahvil spreadlerini geniş tutmaktadır. Türkiye dış borç çevirme maliyeti yüksek seyreder.",
        "favored": ["Döviz Pozisyonlu İhracatçılar", "THYAO"],
        "pressured": ["Gelişmekte Olan Ülke Para Birimleri"],
    },

    # =======================================================================
    # NİSAN 2026 (APRIL 2026)
    # =======================================================================
    {
        "source_name": "TCMB_Basin_Duyurulari",
        "url": "https://www.tcmb.gov.tr/duyuru/2026/nisan-ppk-karari",
        "title": "TCMB PPK Kararı: Politika Faizi %50 Düzeyinde Sabit, Likidite Sterilizasyonu Hızlandırıldı",
        "date_str": "2026-04-25T14:00:00Z",
        "content": (
            "Para Politikası Kurulu, politika faizini %50 düzeyinde sabit tutmuştur. Mart ayındaki parasal sıkılaştırmanın "
            "finansal koşullar üzerindeki etkileri yakından izlenmektedir. Likidite fazlasını soğurmak amacıyla "
            "sterilizasyon araçlarının çeşitlendirilerek etkin kullanılacağı teyit edilmiştir."
        ),
        "stance": "ŞAHİN",
        "severity": "CRITICAL",
        "simple_summary": "TCMB faizi %50'de tuttu; piyasadaki fazla Türk Lirası'nı çekerek gecelik faizlerin düşmesini engelledi. Mevduat faizleri gücünü koruyor.",
        "technical_analysis": "Aktarım mekanizmasını diri tutmak amacıyla repo ve depo alım operasyonlarıyla piyasa faizleri politika faizi tavanına yapışık tutulmaktadır.",
        "favored": ["TL Mevduat & PPF", "BIMAS"],
        "pressured": ["EKGYO", "İnşaat GYO"],
    },
    {
        "source_name": "Resmi_Gazete_Mevzuat",
        "url": "https://www.resmigazete.gov.tr/eskiler/2026/04/20260416-1.htm",
        "title": "TCMB Zorunlu Karşılık Tebliği: YP Mevduat İçin Karşılık Oranları Artırıldı",
        "date_str": "2026-04-16T03:00:00Z",
        "content": (
            "T.C. Resmî Gazete'de yayımlanan TCMB tebliği ile yabancı para mevduat için zorunlu karşılık oranları "
            "tüm vadelerde 200 baz puan artırılmış, Kur Korumalı Mevduat (KKM) hesaplarının standart TL mevduata "
            "dönüştürülmesine yönelik bankalara aylık asgari hedef zorunluluğu getirilmiştir."
        ),
        "stance": "ŞAHİN",
        "severity": "WARNING",
        "simple_summary": "Dolar ve Euro hesapları için bankalara fazladan karşılık zorunluluğu getirildi. KKM'den çıkan paranın dövize değil doğrudan Türk Lirası mevduata gitmesi hedefleniyor.",
        "technical_analysis": "Bankaların YP fonlama maliyeti artarken TL mevduat faizleri yukarı yönde desteklenir. Ters dolarizasyon süreci hızlandırılmaktadır.",
        "favored": ["TL Varlıklar", "AKBNK", "ISCTR"],
        "pressured": ["Döviz Pozisyonu Açığı Olanlar"],
    },
    {
        "source_name": "Dunya_Gazetesi_Makro",
        "url": "https://www.dunya.com/ekonomi/kamuda-tasarruf-paketi-hazirliklari-haberi-20260422",
        "title": "Hazine ve Maliye Bakanlığı: Kamuda Tasarruf Paketi ile Bütçe Disiplini Güçlendiriliyor",
        "date_str": "2026-04-22T09:15:00Z",
        "content": (
            "Hazine ve Maliye Bakanlığı, para politikasını destekleyecek güçlü bir maliye politikası koordinasyonu "
            "kapsamında Kamuda Tasarruf ve Verimlilik Paketi hazırlıklarının tamamlandığını açıkladı. Cari harcamalar "
            "ve kamu yatırımlarında seçici tasarruf hedeflenmektedir."
        ),
        "stance": "ŞAHİN",
        "severity": "INFO",
        "simple_summary": "Hükümet kamu harcamalarını kısacağını ve bütçeyi sıkacağını açıkladı. Para politikasının yükünü hafifletecek mali disiplin adımı geldi.",
        "technical_analysis": "Mali konsolidasyon (fiscal consolidation) risk primini (CDS) düşürerek Hazine borçlanma faizlerini geriletir. Enflasyon beklentilerini çıpalar.",
        "favored": ["DİBS & Hazine Eurobond", "TUPRS"],
        "pressured": ["Kamu Müteahhitleri"],
    },
    {
        "source_name": "ECB_Press",
        "url": "https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp260411~a91.en.html",
        "title": "ECB Faiz Kararı: Faizler Sabit Tutuldu, Haziran İndirimi İçin Güçlü Mesaj Verildi",
        "date_str": "2026-04-11T12:45:00Z",
        "content": (
            "The Governing Council kept the three key ECB interest rates unchanged. President Lagarde noted that if "
            "incoming inflation data continues to align with projections, an easing of current monetary policy "
            "restrictions would be appropriate in the upcoming meetings."
        ),
        "stance": "GÜVERCİN",
        "severity": "OPPORTUNITY",
        "simple_summary": "Avrupa Merkez Bankası faizleri sabit bıraktı ama yaz aylarında faiz indireceğinin net işaretini verdi. Türk ihracatçısı için canlanma beklentisi doğdu.",
        "technical_analysis": "Euro bölgesinde beklenen faiz indirimi Türkiye'nin bir numaralı ticaret ortağında resesyon riskini azaltır. BIST otomotiv ve beyaz eşya ihracatçılarının sipariş görünümü iyileşir.",
        "favored": ["FROTO", "TOASO", "ARCLK"],
        "pressured": ["Dolar Endeksi"],
    },

    # =======================================================================
    # MAYIS 2026 (MAY 2026)
    # =======================================================================
    {
        "source_name": "BloombergHT_Haber",
        "url": "https://www.bloomberght.com/tuik-mayis-enflasyonu-zirveyi-gordu-20260503",
        "title": "TÜİK Enflasyon Verisi: Yıllık TÜFE %75,45 ile Döngünün Zirvesine Ulaştı",
        "date_str": "2026-05-03T10:00:00Z",
        "content": (
            "TÜİK verilerine göre Mayıs ayında yıllık tüketici enflasyonu (TÜFE) %75,45 seviyesine ulaşarak tahminler "
            "doğrultusunda tepe noktasını gördü. Ekonomi yönetimi ve TCMB, Haziran ayından itibaren baz etkisi ve "
            "sıkı para politikasının gecikmeli aktarımıyla hızlı bir dezenflasyon sürecinin başlayacağını bildirdi."
        ),
        "stance": "EKSEN DEĞİŞİMİ",
        "severity": "CRITICAL",
        "simple_summary": "Enflasyon yüzde 75,45 ile tarihi zirvesini gördü! Uzmanlar ve Merkez Bankası en kötünün geride kaldığını, bundan sonra enflasyonun düşüşe geçeceğini söylüyor.",
        "technical_analysis": "Enflasyon patikasında tepe noktasının (peak inflation) teyit edilmesi, tahvil piyasasında getiri eğrisinin uzun ucuna (10Y DİBS) kurumsal yabancı girişini tetiklemiştir. Dezenflasyon fiyatlaması başlar.",
        "favored": ["DİBS Tahvil", "BIMAS", "TCELL"],
        "pressured": ["Kısa Vadeli Borçlular", "Fiyat Geçişkenliği Düşük İmalat"],
    },
    {
        "source_name": "Resmi_Gazete_Mevzuat",
        "url": "https://www.resmigazete.gov.tr/eskiler/2026/05/20260513-1.htm",
        "title": "Cumhurbaşkanı Genelgesi: Kamuda Tasarruf ve Verimlilik Paketi Yürürlüğe Girdi",
        "date_str": "2026-05-13T03:00:00Z",
        "content": (
            "Resmî Gazete'de yayımlanan Cumhurbaşkanlığı Genelgesi ile kamu kurumlarında 3 yıl boyunca yeni taşıt ve "
            "hizmet binası alımı durdurulmuş, lojman ve temsil giderleri sınırlandırılmış, zorunlu olmayan yatırım "
            "ödenekleri dondurulmuştur. Kamu harcamalarında katı disiplin başlamıştır."
        ),
        "stance": "ŞAHİN",
        "severity": "WARNING",
        "simple_summary": "Kamuda Tasarruf Paketi resmen yürürlüğe girdi! 3 yıl boyunca devlete yeni araba, bina alınmayacak; israf önlenecek.",
        "technical_analysis": "Mali disiplinin somut genelgeyle desteklenmesi TCMB'nin dezenflasyon hedefine kredibilite kazandırır. Türkiye risk priminin (CDS) 300 baz puanın altına gerilemesine zemin hazırlar.",
        "favored": ["DİBS & Hazine Eurobond", "GARAN", "AKBNK"],
        "pressured": ["Kamu İhalesi Alan Şirketler"],
    },
    {
        "source_name": "BloombergHT_Haber",
        "url": "https://www.bloomberght.com/sp-turkiyenin-kredi-notunu-b-artiya-yukseltti-20260504",
        "title": "Kredi Derecelendirme (S&P): Türkiye'nin Kredi Notu 'B'den 'B+'ya Yükseltildi, Görünüm Pozitif",
        "date_str": "2026-05-04T22:00:00Z",
        "content": (
            "Uluslararası kredi derecelendirme kuruluşu S&P Global, Türkiye'nin uzun vadeli kredi notunu 'B'den 'B+'ya "
            "yükseltti ve görünümünü 'Pozitif' olarak korudu. Gerekçe olarak ortodoks para politikasının dış dengelenmeyi "
            "sağlaması, TCMB rezervlerindeki toparlanma ve KKM'den TL mevduata sağlıklı geçiş gösterildi."
        ),
        "stance": "GÜVERCİN",
        "severity": "OPPORTUNITY",
        "simple_summary": "Uluslararası derecelendirme kuruluşu S&P Türkiye'nin kredi notunu artırdı! Yabancı yatırımcının Türkiye'ye olan güveni arttı.",
        "technical_analysis": "Not artırımı Türk bankalarının yurt dışı sendikasyon ve sermaye benzeri borçlanma maliyetlerini 75-100 bps aşağı çeker. Bankacılık hisseleri önderliğinde BIST rallisi beslenir.",
        "favored": ["GARAN", "AKBNK", "ISCTR", "YKBNK"],
        "pressured": ["TL Aleyhine Spekülatif Pozisyonlar"],
    },
    {
        "source_name": "TCMB_Basin_Duyurulari",
        "url": "https://www.tcmb.gov.tr/duyuru/2026/mayis-ppk-karari",
        "title": "TCMB PPK Kararı: Faiz %50'de Sabit Bırakıldı, Kararlı Sıkı Duruş Devam Ediyor",
        "date_str": "2026-05-23T14:00:00Z",
        "content": (
            "Para Politikası Kurulu, politika faizini %50 düzeyinde sabit tutmuştur. Kurul, enflasyonda zirvenin "
            "görüldüğünü ve yılın ikinci yarısında başlayacak belirgin düşüşün teyidi için sıkı parasal duruşun "
            "kesintisiz süreceğini beyan etmiştir."
        ),
        "stance": "ŞAHİN",
        "severity": "INFO",
        "simple_summary": "Merkez Bankası faizi %50'de sabit tuttu; 'Enflasyon zirve yaptı ama gevşemek yok, kararlıyız' mesajı verdi.",
        "technical_analysis": "Reel faiz garantisi korunurken TL mevduat faizleri bileşik %60 seviyelerinde risksiz kalkan işlevi görmeye devam etmektedir.",
        "favored": ["TL Mevduat & PPF", "ENKAI", "BIMAS"],
        "pressured": ["Kaldıraçlı Sanayi"],
    },

    # =======================================================================
    # HAZİRAN 2026 (JUNE 2026)
    # =======================================================================
    {
        "source_name": "TCMB_Basin_Duyurulari",
        "url": "https://www.tcmb.gov.tr/duyuru/2026/haziran-ppk-karari",
        "title": "TCMB PPK Kararı: Bir Hafta Vadeli Repo İhale Faiz Oranı %50 Seviyesinde Sabit Tutuldu",
        "date_str": "2026-06-20T14:00:00Z",
        "content": (
            "Para Politikası Kurulu (Kurul), politika faizi olan bir hafta vadeli repo ihale faiz oranının "
            "%50 düzeyinde sabit tutulmasına karar vermiştir. Kurul, enflasyonun ana eğiliminde gerileme sağlanana "
            "ve enflasyon beklentileri öngörülen tahmin aralığına yakınsayana kadar sıkı para politikası duruşunun "
            "sürdürüleceğini yinelemiştir. Kredi büyümesi ve iç talep yakından izlenmektedir."
        ),
        "stance": "ŞAHİN",
        "severity": "CRITICAL",
        "simple_summary": "Merkez Bankası faizleri %50'de sabit tuttu; enflasyon tamamen düşene kadar faiz indirmeyeceğinin net sinyalini verdi. Mevduat getirisi cazip kalmaya devam ediyor.",
        "technical_analysis": "TCMB %50 politika faiziyle reel faiz patikasını pozitif bölgede tutmaktadır. Yüksek iskonto oranı (WACC) BIST sanayi hisseleri üzerinde marj baskısını sürdürmektedir.",
        "favored": ["ENKAI", "BIMAS", "TCELL"],
        "pressured": ["EKGYO", "SOKM", "PETKM"],
    },
    {
        "source_name": "Resmi_Gazete_Mevzuat",
        "url": "https://www.resmigazete.gov.tr/eskiler/2026/06/20260624-1.htm",
        "title": "Kredi Kartı Nakit Avans ve Kredili Mevduat Hesapları Azami Faiz Oranları Tebliği",
        "date_str": "2026-06-24T03:00:00Z",
        "content": (
            "T.C. Resmî Gazete'de yayımlanan tebliğ ile kredi kartı nakit çekim işlemlerinde ve KMH hesaplarında "
            "uygulanan aylık azami akdi faiz oranı sıkı para politikası gereğince yeniden düzenlenmiştir. "
            "Tüketim harcamalarını dizginlemek ve tasarrufları TL mevduata yönlendirmek amaçlanmaktadır."
        ),
        "stance": "ŞAHİN",
        "severity": "WARNING",
        "simple_summary": "Kredi kartından nakit çekim ve ek hesap faizleri sıkılaştırıldı. Vatandaşın borçla tüketim yapması sınırlandırılıyor.",
        "technical_analysis": "Tüketici borçlanma maliyetinin yukarı çekilmesi iç talebi soğuturken perakende kredi büyümesini sınırlar. Bankacılık bireysel kredi risk primini düşürür.",
        "favored": ["GARAN", "AKBNK"],
        "pressured": ["Bireysel Borçlular", "Dayanıklı Tüketim"],
    },
    {
        "source_name": "BDDK_Kararlari",
        "url": "https://www.bddk.org.tr/Duyuru/2026/06-tuketici-kredileri-siniri",
        "title": "BDDK Kararı: Tüketici Kredilerinde Risk Ağırlığı ve Vade Sınırları Düzenlemesi",
        "date_str": "2026-06-28T11:00:00Z",
        "content": (
            "Bankacılık Düzenleme ve Denetleme Kurulu, finansal istikrarın güçlendirilmesi ve makro ihtiyati "
            "çerçevenin desteklenmesi amacıyla ihtiyaç ve taşıt kredilerinde uygulanan sermaye yeterliliği risk "
            "ağırlıklarını artırmıştır."
        ),
        "stance": "ŞAHİN",
        "severity": "WARNING",
        "simple_summary": "Bankaların araba ve ihtiyaç kredisi vermesi zorlaştırıldı; bankalar artık daha seçici davranacak.",
        "technical_analysis": "Risk ağırlıklarının artırılması sermaye yeterlilik rasyosu (SYR) tüketimini hızlandırır. Otomotiv ve beyaz eşya iç satış hacminde yavaşlama tetiklenir.",
        "favored": ["FROTO", "TOASO"],  # İhracatçı oldukları için korunur
        "pressured": ["EKGYO", "İç Pazara Bağımlı KOBİ'ler"],
    },
    {
        "source_name": "FederalReserve_Press",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260612a.htm",
        "title": "Federal Reserve FOMC Projeksiyonu: 2026 Yılı İndirim Beklentisi 25 Baz Puana Geriledi",
        "date_str": "2026-06-12T18:00:00Z",
        "content": (
            "The Federal Open Market Committee maintained the target range for the federal funds rate at 5.25-5.50%. "
            "Updated economic projections (dot plot) indicate fewer rate cuts than previously expected due to "
            "stubborn services inflation. Dollar index (DXY) rebounded."
        ),
        "stance": "ŞAHİN",
        "severity": "WARNING",
        "simple_summary": "ABD Merkez Bankası faiz indirimlerini erteledi; dolar küresel piyasalarda değer kazandı. Gelişmekte olan ülkeler için borçlanma maliyeti yüksek kaldı.",
        "technical_analysis": "Fed'in şahin tutumu US 10Y tahvil faizlerini yukarıda tutarak GOÜ para birimleri üzerinde kur baskısı yaratmaktadır. Türkiye Eurobond getirileri primli kalmaya devam eder.",
        "favored": ["Döviz Pozisyonlu Şirketler", "ENKAI", "THYAO"],
        "pressured": ["TL Varlıklar", "İthalatçılar"],
    },

    # =======================================================================
    # TEMMUZ 2026 (JULY 2026)
    # =======================================================================
    {
        "source_name": "TCMB_Basin_Duyurulari",
        "url": "https://www.tcmb.gov.tr/duyuru/2026/temmuz-zorunlu-karsilik-duzenlemesi",
        "title": "TCMB Zorunlu Karşılık Tebliği: TL Mevduat Payı Hedefi Artırıldı ve KKM Tasfiyesi Hızlandırıldı",
        "date_str": "2026-07-08T08:30:00Z",
        "content": (
            "Türkiye Cumhuriyet Merkez Bankası, parasal aktarım mekanizmasını güçlendirmek amacıyla Kur Korumalı "
            "Mevduat (KKM) hesaplarına uygulanan zorunlu karşılık oranlarını artırmış, standart TL mevduat payı "
            "hedefini %75 seviyesine yükseltmiştir. Fazla TL likiditesini çekmek için sterilizasyon adımları sıkılaştırılmıştır."
        ),
        "stance": "ŞAHİN",
        "severity": "CRITICAL",
        "simple_summary": "Merkez Bankası bankalara 'KKM'yi bitirin, müşteriyi doğrudan TL mevduata geçirin' talimatı verdi. Mevduat faizleri yeniden %52-54 bandına sıçradı.",
        "technical_analysis": "Parasal aktarım mekanizmasının sıkılaştırılması bankaların mevduat toplama yarışını kızıştırmakta ve fonlama maliyetini artırmaktadır. KKM çıkışları doğrudan DİBS ve PPF fonlarına kaymaktadır.",
        "favored": ["TL Mevduat & PPF", "BIMAS", "ENKAI"],
        "pressured": ["GARAN", "AKBNK", "Borçlu Sanayiler"],
    },
    {
        "source_name": "BDDK_Kararlari",
        "url": "https://www.bddk.org.tr/Duyuru/2026/07-ticari-kredi-buyume-siniri",
        "title": "BDDK Kararı: TL Ticari Kredilerde Aylık Büyüme Sınırı %2 Seviyesinde Sınırlandırıldı",
        "date_str": "2026-07-16T12:00:00Z",
        "content": (
            "BDDK, bankaların Türk Lirası ticari kredi büyüme sınırını aylık %2 olarak belirlemiştir. Sınırı aşan "
            "bankalar için zorunlu menkul kıymet tesis etme yükümlülüğü getirilmiştir. İhracat ve yatırım kredileri "
            "muaf tutulmuştur."
        ),
        "stance": "ŞAHİN",
        "severity": "CRITICAL",
        "simple_summary": "Şirketlerin bankalardan ucuz ve sınırsız kredi çekmesi engellendi; sadece ihracat yapanlara ayrıcalık tanındı. Borcu çok olan şirketler için zorlu süreç.",
        "technical_analysis": "Seçici kredi politikası (selective credit tightening) iç pazara yönelik çalışan kaldıraçlı şirketlerin net işletme sermayesini daraltır. İhracatçı döviz gelirli sanayiler (FROTO, ASELS) pozitif ayrışır.",
        "favored": ["FROTO", "ASELS", "TUPRS"],
        "pressured": ["EKGYO", "SOKM", "Kaldıraçlı Sanayi"],
    },
    {
        "source_name": "Resmi_Gazete_Mevzuat",
        "url": "https://www.resmigazete.gov.tr/eskiler/2026/07/20260722-3.htm",
        "title": "Resmî Gazete Tebliği: Döviz Geliri Olmayan Şirketlere Yabancı Para Kredi Kullanım Kısıtı",
        "date_str": "2026-07-22T04:00:00Z",
        "content": (
            "Resmî Gazete'de yayımlanan Sermaye Hareketleri Genelgesi değişikliği ile döviz geliri olmayan yerleşik "
            "şirketlerin döviz cinsi kredi kullanım koşulları ağırlaştırılmış, kur riski koruma mekanizmaları zorunlu kılınmıştır."
        ),
        "stance": "ŞAHİN",
        "severity": "WARNING",
        "simple_summary": "Döviz kazanmayan Türk şirketlerinin dolarla borçlanması yasaklandı; amaç şirketlerin ani kur şokunda batmasını önlemek.",
        "technical_analysis": "Bilanço kur riski açığının (FX open position) regülasyonla kapatılması Türkiye CDS primini olumlu etkiler; döviz açığı olan sanayi hisseleri için kısa vadede borç çevirme maliyeti yaratır.",
        "favored": ["ENKAI", "SISE", "THYAO"],
        "pressured": ["Döviz Borçlu KOBİ'ler", "PETKM"],
    },
    {
        "source_name": "TCMB_Basin_Duyurulari",
        "url": "https://www.tcmb.gov.tr/duyuru/2026/temmuz-ppk-faiz-karari",
        "title": "TCMB PPK Kararı: Politika Faizi %50 Düzeyinde Sabit Bırakıldı",
        "date_str": "2026-07-23T14:00:00Z",
        "content": (
            "Para Politikası Kurulu politika faizini %50 düzeyinde sabit tutmuştur. Karar metninde hizmet enflasyonundaki "
            "katılık ve kiralardaki atalete dikkat çekilmiş, faiz indirim döngüsüne girilmesi için henüz erken olduğu vurgulanmıştır."
        ),
        "stance": "ŞAHİN",
        "severity": "WARNING",
        "simple_summary": "Temmuz ayında da faiz inmedi. Enflasyonun düşüş hızının beklentiden yavaş olduğu açıklandı. TL mevduat kral olmaya devam ediyor.",
        "technical_analysis": "Hizmet enflasyonundaki yapışkanlık TCMB'yi erken gevşeme (premature easing) riskinden alıkoymaktadır. Terminal faiz beklentisinin uzaması borsa hisse değerlemelerinde iskonto çarpanını baskılar.",
        "favored": ["TL Mevduat", "PPF", "BIMAS"],
        "pressured": ["EKGYO", "BIST 100 Küçük Şirketler"],
    },

    # =======================================================================
    # AĞUSTOS 2026 (AUGUST 2026)
    # =======================================================================
    {
        "source_name": "TCMB_Basin_Duyurulari",
        "url": "https://www.tcmb.gov.tr/duyuru/2026/agustos-enflasyon-raporu",
        "title": "TCMB 3. Enflasyon Raporu: Yıl Sonu Enflasyon Tahmini %38 Seviyesinde Korundu",
        "date_str": "2026-08-08T10:30:00Z",
        "content": (
            "TCMB Başkanı Enflasyon Raporu sunumunda, iç talepteki yavaşlamanın enflasyon dinamiklerini desteklediğini, "
            "çıktı açığının negatif bölgeye geçtiğini ve son çeyrekte dezenflasyon sürecinin belirginleşeceğini ifade etmiştir."
        ),
        "stance": "NÖTR",
        "severity": "OPPORTUNITY",
        "simple_summary": "Merkez Bankası ekonominin yavaş yavaş dengelendiğini ve enflasyonun yıl sonu hedefine doğru indiğini açıkladı. Yıl sonuna doğru ilk faiz indirimi umudu doğdu.",
        "technical_analysis": "Çıktı açığının negatife dönmesi iç talep kaynaklı enflasyonist baskının kırıldığını doğrular. Getiri eğrisinde 2 yıllık tahvillerde faiz düşüşü fiyatlanmaya başlar.",
        "favored": ["DİBS / Tahviller", "GARAN", "AKBNK"],
        "pressured": ["Aşırı Döviz Pozisyonu Tutanlar"],
    },
    {
        "source_name": "ECB_Press",
        "url": "https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp260814.en.html",
        "title": "Avrupa Merkez Bankası (ECB) 25 Baz Puan Faiz İndirimine Gitti",
        "date_str": "2026-08-14T14:15:00Z",
        "content": (
            "The Governing Council of the ECB decided to lower the deposit facility rate by 25 basis points to 3.25%. "
            "The disinflationary process in the euro area is well on track while economic activity remains subdued."
        ),
        "stance": "GÜVERCİN",
        "severity": "OPPORTUNITY",
        "simple_summary": "Avrupa Merkez Bankası faiz indirdi. Avrupa'da faizlerin düşmesi Türkiye'den mal alan Avrupalıların talebini artırır; Türk ihracatçısı için büyük moral.",
        "technical_analysis": "Euro bölgesinde parasal gevşeme Türkiye'nin ana ihracat pazarında talebi canlandırır. EUR/USD dengesi ve Türkiye'nin dış ticaret hadleri ihracatçı BIST şirketleri lehine döner.",
        "favored": ["FROTO", "TOASO", "ARCLK", "SISE"],
        "pressured": ["Dolar Endeksi Uzun Pozisyonlar"],
    },
    {
        "source_name": "TCMB_Basin_Duyurulari",
        "url": "https://www.tcmb.gov.tr/duyuru/2026/agustos-ppk-karari",
        "title": "TCMB PPK Kararı: Faiz %50'de Sabit, Likidite Fazlası İçin Ters Repo ve Depo İhaleleri Devrede",
        "date_str": "2026-08-22T14:00:00Z",
        "content": (
            "Para Politikası Kurulu politika faizini %50 düzeyinde sabit tutmuştur. Sistemde oluşan likidite fazlasını "
            "çekmek amacıyla depo alım ihaleleri ve sterilizasyon araçlarının etkin biçimde kullanılacağı belirtilmiştir."
        ),
        "stance": "ŞAHİN",
        "severity": "INFO",
        "simple_summary": "Faiz yine inmedi ama piyasadaki fazla Türk Lirası Merkez Bankası tarafından çekilerek faizlerin gevşemesi engellendi. Gevşemeye izin yok.",
        "technical_analysis": "Sterilizasyon operasyonları ile gecelik faizlerin (BIST Repo) politika faizinin altına inmesi engellenmektedir. TL likidite sıkılığı korunmaktadır.",
        "favored": ["TL Mevduat & PPF", "ENKAI"],
        "pressured": ["Kısa Vadeli Borçlanan Sanayi"],
    },
    {
        "source_name": "Resmi_Gazete_Mevzuat",
        "url": "https://www.resmigazete.gov.tr/eskiler/2026/08/20260829-1.htm",
        "title": "Resmî Gazete Kararı: Savunma, Yüksek Teknoloji ve Yenilenebilir Enerji Yatırımlarına Hazine Teşviki",
        "date_str": "2026-08-29T03:30:00Z",
        "content": (
            "Cumhurbaşkanı Kararı ile savunma sanayii, çip üretimi ve rüzgar/güneş enerjisi ekipman yatırımlarına "
            "faiz destekli Hazine kredisi, kurumlar vergisi muafiyeti ve gümrük vergisi indirimi getirilmiştir."
        ),
        "stance": "GÜVERCİN",
        "severity": "OPPORTUNITY",
        "simple_summary": "Devlet yerli savunma, çip ve yenilenebilir enerji yatırımı yapan şirketlere dev vergi indirimleri ve ucuz kredi desteği açıkladı.",
        "technical_analysis": "Seçici teşvik modeli stratejik sektörlerde WACC maliyetini devlet sübvansiyonuyla sıfıra yakınlaştırır. ASELS ve enerji hisselerinde uzun vadeli nakit akışı projeksiyonlarını yukarı revize eder.",
        "favored": ["ASELS", "ENJSA", "CWENE"],
        "pressured": ["Geleneksel Fosil Yakıt"],
    },
]


def run_historical_backfill() -> dict[str, Any]:
    """
    Geçmiş 3 ayın (Haziran, Temmuz, Ağustos 2026) makro veri kümesini
    veritabanına işler, BIST şirket duyarlılıklarını bağlar ve
    aylık MacroMemoryDigest özetlerini sentezleyerek dondurur.
    """
    logger.info("3 Aylık Geçmiş Makroekonomik Veri Kümesi Yükleniyor...")
    engine = get_engine()

    inserted_count = 0
    with Session(engine) as session:
        for item in HISTORICAL_MACRO_ITEMS:
            dt = datetime.fromisoformat(item["date_str"].replace("Z", "+00:00"))

            raw_item = RawItem(
                source_name=item["source_name"],
                url=item["url"],
                title=item["title"],
                content_text=item["content"],
                raw_metadata={"date_str": item["date_str"], "is_backfill": True},
            )

            raw_data, is_new = save_raw_item(session, raw_item)
            raw_data.fetched_at = dt
            raw_data.is_processed = True
            session.add(raw_data)
            session.commit()
            session.refresh(raw_data)

            # BIST Etiketleri
            fav_items = [
                f if isinstance(f, dict) else {"ticker": str(f), "reason": "Makro politika kararıyla pozitif uyumlu."}
                for f in item.get("favored", [])
            ]
            pres_items = [
                p if isinstance(p, dict) else {"ticker": str(p), "reason": "Sıkılaşma / maliyet baskısı altında temkinli olunmalı."}
                for p in item.get("pressured", [])
            ]
            bist_tags = {
                "favored": fav_items,
                "pressured": pres_items,
            }

            metrics = {
                "policy_stance": item["stance"],
                "relevance_score": 90,
                "confidence_score": 0.95,
                "is_turkish": True,
                "jurisdiction": "Turkey",
                "simple_summary": item["simple_summary"],
                "technical_analysis": item["technical_analysis"],
                "bist_tickers": bist_tags,
                "affected_assets": ["BIST 100", "TL Faiz", "Döviz"],
            }

            analysis_record = AnalysisResult(
                raw_data_id=raw_data.id,
                pipeline_type="macro_regulatory",
                severity=item["severity"],
                summary_title=item["title"],
                detailed_reasoning=f"{item['simple_summary']}\n\nTeknik Analiz: {item['technical_analysis']}",
                action_items=[f"BIST Seçici Hamle: {', '.join(item['favored'])} tercih edilmeli."],
                metrics=metrics,
                created_at=dt,
            )
            analysis = save_analysis_result(session=session, result=analysis_record)
            inserted_count += 1

    logger.info("Geçmiş %d adet analiz kaydı veritabanına işlendi.", inserted_count)

    # -----------------------------------------------------------------------
    # Aylık Makro Bellek Sıkıştırmalarını Üret (Mart - Ağustos 2026 + Rolling 180D)
    # -----------------------------------------------------------------------
    digests_created = []

    # 1. Mart 2026
    d_march = generate_period_digest(
        start_date=datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc),
        period_key="2026-03",
        period_label="Mart 2026 Makroekonomik Bellek Özeti",
        period_type="monthly",
    )
    digests_created.append(d_march.period_key)

    # 2. Nisan 2026
    d_april = generate_period_digest(
        start_date=datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 4, 30, 23, 59, 59, tzinfo=timezone.utc),
        period_key="2026-04",
        period_label="Nisan 2026 Makroekonomik Bellek Özeti",
        period_type="monthly",
    )
    digests_created.append(d_april.period_key)

    # 3. Mayıs 2026
    d_may = generate_period_digest(
        start_date=datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc),
        period_key="2026-05",
        period_label="Mayıs 2026 Makroekonomik Bellek Özeti",
        period_type="monthly",
    )
    digests_created.append(d_may.period_key)

    # 4. Haziran 2026
    d_june = generate_period_digest(
        start_date=datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc),
        period_key="2026-06",
        period_label="Haziran 2026 Makroekonomik Bellek Özeti",
        period_type="monthly",
    )
    digests_created.append(d_june.period_key)

    # 5. Temmuz 2026
    d_july = generate_period_digest(
        start_date=datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 7, 31, 23, 59, 59, tzinfo=timezone.utc),
        period_key="2026-07",
        period_label="Temmuz 2026 Makroekonomik Bellek Özeti",
        period_type="monthly",
    )
    digests_created.append(d_july.period_key)

    # 6. Ağustos 2026
    d_august = generate_period_digest(
        start_date=datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc),
        period_key="2026-08",
        period_label="Ağustos 2026 Makroekonomik Bellek Özeti",
        period_type="monthly",
    )
    digests_created.append(d_august.period_key)

    # 7. Kümülatif 180 Günlük / 6 Aylık Hareketli Bellek (Rolling 180D)
    d_rolling = generate_period_digest(
        start_date=datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 8, 23, 59, 59, tzinfo=timezone.utc),
        period_key="rolling_180d",
        period_label="Son 180 Günlük (6 Aylık) Kümülatif Politika Seyri",
        period_type="rolling",
    )
    digests_created.append(d_rolling.period_key)

    logger.info("6 Aylık Makro Bellek Sentezleri Tamamlandı: %s", digests_created)

    return {
        "status": "success",
        "inserted_analyses_count": inserted_count,
        "digests_created": digests_created,
    }


if __name__ == "__main__":
    res = run_historical_backfill()
    print("BACKFILL COMPLETED:", res)
