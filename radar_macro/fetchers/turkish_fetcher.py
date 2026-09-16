"""Specialized fetcher for Turkish Official Gazettes (Resmî Gazete) and regulatory bodies (TCMB, SPK, BDDK, SEDDK).

Deep Extraction Strategy
------------------------
- **SPK**: Downloads PDF bulletins from the official archive and extracts full decision text via pypdf.
- **BDDK**: Scrapes the announcement list (/Duyuru/Liste/39) then follows each /Duyuru/Detay/ link
  to extract the full press release body text (market-moving credit/card limit decisions).
- **Resmî Gazete**: Downloads today's .pdf and .htm gazette documents, extracts article text so that
  financial regulations (fon, vergi, stopaj, BES, döviz) surface their full text for AI analysis.
- **TCMB**: Scrapes the static press-release page + reads the EVDS interest rate XML feed.
- **SEDDK**: Scrapes insurance/private-pension regulation links (yönetmelikler) from seddk.gov.tr and
  follows the linked Resmî Gazete .htm pages to extract the regulation body text.
"""

from datetime import datetime, timezone
import logging
from typing import Any
import urllib3
from bs4 import BeautifulSoup
import requests

from radar_core.core.fetchers.base import BaseFetcher, register_fetcher
from radar_core.core.models import RawItem

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("radar_macro.fetchers.turkish")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


@register_fetcher("turkish_official")
class TurkishOfficialFetcher(BaseFetcher):
    """
    Ingestion strategy specialized for Turkish governmental gazettes and financial regulators.
    Handles non-standard Windows SSL certificate authority issues natively.
    """

    def fetch(self, source_config: dict[str, Any]) -> list[RawItem]:
        mode = source_config.get("sub_strategy", "resmi_gazete")
        source_name = source_config.get("source_name", "Resmi_Gazete")
        limit = source_config.get("limit", 15)

        logger.info("Executing Turkish official ingestion for '%s' (mode=%s)...", source_name, mode)

        if mode == "resmi_gazete":
            return self._fetch_resmi_gazete(source_name, limit)
        elif mode == "tcmb_press":
            return self._fetch_tcmb(source_name, limit)
        elif mode == "spk_announcements":
            return self._fetch_spk(source_name, limit)
        elif mode == "bddk_announcements":
            return self._fetch_bddk(source_name, limit)
        elif mode == "seddk_mevzuat":
            return self._fetch_seddk(source_name, limit)
        else:
            return self._fetch_resmi_gazete(source_name, limit)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get(self, url: str, timeout: int = 15):
        """GET with shared headers and SSL bypass; returns None on failure."""
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=timeout)
            resp.encoding = "utf-8"
            return resp if resp.status_code == 200 else None
        except Exception as exc:
            logger.warning("GET failed for %s: %s", url, exc)
            return None

    def _extract_html_text(self, url: str, max_chars: int = 4500) -> str:
        """Download an HTML page and return clean body text (nav/footer stripped)."""
        resp = self._get(url, timeout=12)
        if not resp:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all(["nav", "header", "footer", "script", "style", "aside", "form"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)[:max_chars]

    def _extract_pdf_text(self, url: str, max_chars: int = 4500) -> str:
        """Download a PDF and extract text from the first 6 pages via pypdf."""
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.warning("pypdf not installed; skipping PDF extraction for %s", url)
            return ""
        import io
        resp = self._get(url, timeout=18)
        if not resp:
            return ""
        try:
            reader = PdfReader(io.BytesIO(resp.content))
            text = ""
            for idx in range(min(6, len(reader.pages))):
                page_text = reader.pages[idx].extract_text()
                if page_text:
                    text += f"\n--- Sayfa {idx + 1} ---\n{page_text}"
            return text[:max_chars]
        except Exception as exc:
            logger.warning("PDF parse error for %s: %s", url, exc)
            return ""

    # ------------------------------------------------------------------
    # Resmî Gazete  –  full-text PDF/HTM extraction
    # ------------------------------------------------------------------

    def _fetch_resmi_gazete(self, source_name: str, limit: int) -> list[RawItem]:
        """Scrape today's Resmî Gazete and extract full text from PDF/HTM documents."""
        url = "https://www.resmigazete.gov.tr/"
        items: list[RawItem] = []
        today_str = datetime.now().strftime("%d.%m.%Y")

        resp = self._get(url, timeout=15)
        if not resp:
            logger.warning("Resmî Gazete main page unavailable.")
            return items

        soup = BeautifulSoup(resp.text, "html.parser")
        doc_links: list[tuple[str, str]] = []
        seen_urls: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            title = a.get_text(strip=True)
            lower_title = title.lower()
            lower_href = href.lower()

            is_doc = ".pdf" in lower_href or ".htm" in lower_href
            is_relevant = is_doc or any(k in lower_title for k in [
                "karar", "kanun", "yönetmelik", "tebliğ", "genelge",
                "fiyat", "vergi", "bakan", "hazine", "merkez bankası",
                "borçlanma", "destekleme", "ithalat", "ihracat", "özelleştirme",
                "fon", "stopaj", "bes", "emeklilik", "sermaye", "sigorta",
            ])

            if not is_relevant or len(title) < 5:
                continue

            clean_title = title.lstrip("–- ").strip() or f"Resmî Gazete ({href.split('/')[-1]})"
            full_url = href if href.startswith("http") else f"https://www.resmigazete.gov.tr/{href.lstrip('/')}"

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            doc_links.append((clean_title, full_url))

        for clean_title, doc_url in doc_links[:limit]:
            lower_url = doc_url.lower()

            full_text = ""
            if ".pdf" in lower_url:
                full_text = self._extract_pdf_text(doc_url, max_chars=4500)
            elif ".htm" in lower_url:
                full_text = self._extract_html_text(doc_url, max_chars=4500)

            content = (
                f"T.C. Resmî Gazete İlanı / Mevzuat Değişikliği\n"
                f"Tarih: {today_str}\n"
                f"Başlık / Karar Metni: {clean_title}\n"
                f"Belge Bağlantısı: {doc_url}\n"
                f"Resmî Gazete Yürütme ve İdare Bölümü uyarınca yayımlanan karar veya düzenleme."
            )
            if full_text.strip():
                content += f"\n\n=== BELGE TAM METNİ ===\n{full_text}"

            items.append(RawItem(
                source_name=source_name,
                url=doc_url,
                title=clean_title,
                content_text=content,
                raw_metadata={
                    "jurisdiction": "Turkey",
                    "gazette_date": today_str,
                    "category": "Official Gazette",
                    "has_full_text": bool(full_text.strip()),
                },
            ))

        logger.info("Resmî Gazete extracted %d regulatory decrees/laws.", len(items))
        return items

    # ------------------------------------------------------------------
    # TCMB  –  press releases + EVDS interest rate feed
    # ------------------------------------------------------------------

    def _fetch_tcmb(self, source_name: str, limit: int) -> list[RawItem]:
        """Fetch TCMB press releases and current policy interest rate from EVDS."""
        items: list[RawItem] = []
        today_str = datetime.now().strftime("%d.%m.%Y")

        # ---- 1. EVDS interest rate XML (static API, no JS required) ----
        evds_url = (
            "https://evds2.tcmb.gov.tr/service/evds/series=TP.MB.S.F3&"
            "startDate=01-01-2024&endDate={}&type=xml&key=anonymoususer".format(
                datetime.now().strftime("%d-%m-%Y")
            )
        )
        evds_resp = self._get(evds_url, timeout=12)
        if evds_resp and evds_resp.text.strip():
            try:
                evds_soup = BeautifulSoup(evds_resp.text, "xml")
                data_rows = evds_soup.find_all("items")[-5:]
                rate_data = ""
                for row in data_rows:
                    tarih = row.find("Tarih")
                    deger = row.find("TP_MB_S_F3")
                    if tarih and deger:
                        rate_data += f"  {tarih.text}: %{deger.text} (Politika Faizi)\n"

                if rate_data:
                    content = (
                        f"Türkiye Cumhuriyet Merkez Bankası (TCMB) Politika Faiz Oranı Güncel Veri\n"
                        f"Tarih: {today_str}\n"
                        f"Kaynak: TCMB EVDS (Elektronik Veri Dağıtım Sistemi)\n\n"
                        f"Son Politika Faiz Oranları:\n{rate_data}"
                        f"\nTCMB Para Politikası Kurulu (PPK) kararlarıyla belirlenen politika faiz oranı.\n"
                        f"Yüksek faiz → TL mevduat cazip, hisse/tahvil değerlemeleri baskı altında.\n"
                        f"Düşen faiz → Kredi büyümesi, tüketici harcamaları, BIST yükselişi beklentisi."
                    )
                    items.append(RawItem(
                        source_name=source_name,
                        url=evds_url,
                        title=f"TCMB Politika Faizi – {today_str}",
                        content_text=content,
                        raw_metadata={
                            "jurisdiction": "Turkey",
                            "category": "Central Bank",
                            "data_type": "interest_rate_evds",
                        },
                    ))
            except Exception as exc:
                logger.warning("TCMB EVDS parse error: %s", exc)

        # ---- 2. TCMB Press Release static page ----
        press_url = "https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Duyurular/Basin/"
        resp = self._get(press_url, timeout=12)
        if resp:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(strip=True)

                # Skip nav/anchor links and short menu items
                if (len(text) < 25 or href == "#" or href.startswith("javascript:")
                        or "Main+Menu/Banka+Hakkinda" in href
                        or "Main+Menu/Istatistikler" in href
                        or "Main+Menu/Yayinlar" in href):
                    continue

                if any(w in text.lower() for w in [
                    "faiz", "para", "politika", "enflasyon", "zorunlu",
                    "mevduat", "duyuru", "ppk", "tcmb", "karar", "kur",
                    "rezerv", "likidite", "swap",
                ]):
                    full_url = href if href.startswith("http") else f"https://www.tcmb.gov.tr{href}"
                    content = (
                        f"Türkiye Cumhuriyet Merkez Bankası (TCMB) Basın Duyurusu\n"
                        f"Tarih: {today_str}\n"
                        f"Konu: {text}\n"
                        f"TCMB Para Politikası ve Makroihtiyati Düzenleme Bildirimi.\n"
                        f"Detay URL: {full_url}"
                    )
                    items.append(RawItem(
                        source_name=source_name,
                        url=full_url,
                        title=text,
                        content_text=content,
                        raw_metadata={
                            "jurisdiction": "Turkey",
                            "category": "Central Bank",
                        },
                    ))

                if len(items) >= limit:
                    break

        logger.info("TCMB extracted %d policy releases (EVDS + press).", len(items))
        return items

    # ------------------------------------------------------------------
    # SPK  –  PDF bulletin archive
    # ------------------------------------------------------------------

    def _fetch_spk(self, source_name: str, limit: int) -> list[RawItem]:
        """Fetch real SPK (Capital Markets Board of Turkey) PDF bulletins and extract decision texts."""
        bulletin_page_url = "https://spk.gov.tr/spk-bultenleri/2026-yili-spk-bultenleri"
        items: list[RawItem] = []

        resp = self._get(bulletin_page_url, timeout=12)
        if not resp:
            logger.warning("SPK bültenler sayfası erişilemiyor.")
            return items

        soup = BeautifulSoup(resp.text, "html.parser")
        bulletin_entries: list[tuple[str, str]] = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True)
            if ".pdf" in href.lower() and ("2026-" in href or "bulten" in href.lower() or "bülten" in text.lower()):
                full_url = href if href.startswith("http") else f"https://spk.gov.tr{href}"
                clean_title = text if len(text) > 10 else f"SPK Bülteni ({full_url.split('/')[-1]})"
                bulletin_entries.append((clean_title, full_url))

        for title, pdf_url in bulletin_entries[:limit]:
            content = (
                f"Sermaye Piyasası Kurulu (SPK) Resmî Haftalık Bülteni\n"
                f"Bülten Başlığı: {title}\n"
                f"Kaynak URL: {pdf_url}\n\n"
            )

            full_text = self._extract_pdf_text(pdf_url, max_chars=4500)
            if full_text.strip():
                content += f"Bülten Karar ve Tebliğ Metinleri:\n{full_text}"

            items.append(RawItem(
                source_name=source_name,
                url=pdf_url,
                title=title,
                content_text=content,
                raw_metadata={
                    "jurisdiction": "Turkey",
                    "category": "Securities Regulator",
                    "doc_type": "official_pdf_bulletin",
                },
            ))

        logger.info("SPK extracted %d official PDF bulletins.", len(items))
        return items

    # ------------------------------------------------------------------
    # BDDK  –  deep text extraction from detail pages
    # ------------------------------------------------------------------

    def _fetch_bddk(self, source_name: str, limit: int) -> list[RawItem]:
        """Scrape BDDK announcements list then extract full text from each detail page."""
        list_url = "https://www.bddk.org.tr/Duyuru/Liste/39"
        items: list[RawItem] = []

        resp = self._get(list_url, timeout=12)
        if not resp:
            logger.warning("BDDK duyuru listesi erişilemiyor.")
            return items

        soup = BeautifulSoup(resp.text, "html.parser")
        detail_links: list[tuple[str, str]] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True)

            # BDDK uses /Duyuru/Detay/ (capital D) for individual press releases
            if len(text) > 10 and "/Duyuru/Detay/" in href and href not in seen:
                seen.add(href)
                full_url = href if href.startswith("http") else f"https://www.bddk.org.tr{href}"
                # Strip date prefix if present (e.g. "07.09.2026Basın Açıklaması")
                clean_text = text.strip()
                if len(clean_text) > 12 and clean_text[2] == "." and clean_text[5] == ".":
                    clean_text = clean_text[10:].strip()
                detail_links.append((clean_text or "BDDK Basın Açıklaması", full_url))

        for announcement_title, detail_url in detail_links[:limit]:
            full_text = self._extract_html_text(detail_url, max_chars=4000)

            content = (
                f"Bankacılık Düzenleme ve Denetleme Kurumu (BDDK) Kararı / Basın Açıklaması\n"
                f"Konu: {announcement_title}\n"
                f"Kredi büyüme sınırlamaları, konut/tüketici kredileri, kart limitleri ve makroihtiyati finansal düzenleme bildirimi.\n"
                f"Detay URL: {detail_url}"
            )
            if full_text.strip():
                content += f"\n\n=== KARAR METNİ ===\n{full_text}"

            items.append(RawItem(
                source_name=source_name,
                url=detail_url,
                title=announcement_title,
                content_text=content,
                raw_metadata={
                    "jurisdiction": "Turkey",
                    "category": "Banking Regulator",
                    "has_full_text": bool(full_text.strip()),
                },
            ))

        logger.info("BDDK extracted %d announcements with deep text.", len(items))
        return items

    # ------------------------------------------------------------------
    # SEDDK  –  insurance & private pension (BES) regulations
    # ------------------------------------------------------------------

    def _fetch_seddk(self, source_name: str, limit: int) -> list[RawItem]:
        """Scrape SEDDK insurance/BES regulation list and extract full text from Resmî Gazete pages."""
        list_url = "https://www.seddk.gov.tr/tr/mevzuat/sigortacilik/yonetmelikler"
        items: list[RawItem] = []
        today_str = datetime.now().strftime("%d.%m.%Y")

        resp = self._get(list_url, timeout=12)
        if not resp:
            logger.warning("SEDDK mevzuat sayfası erişilemiyor.")
            return items

        soup = BeautifulSoup(resp.text, "html.parser")
        reg_links: list[tuple[str, str]] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True)

            if len(text) < 20:
                continue

            is_regulation_link = (
                "resmigazete.gov.tr" in href or
                "mevzuat.gov.tr" in href or
                href.endswith(".pdf") or
                href.endswith(".htm")
            )

            if is_regulation_link and href not in seen:
                seen.add(href)
                full_url = href if href.startswith("http") else f"https://www.seddk.gov.tr{href}"
                reg_links.append((text.strip(), full_url))

        for reg_title, reg_url in reg_links[:limit]:
            lower_url = reg_url.lower()

            full_text = ""
            if ".htm" in lower_url and "resmigazete" in lower_url:
                full_text = self._extract_html_text(reg_url, max_chars=4000)
            elif ".pdf" in lower_url:
                full_text = self._extract_pdf_text(reg_url, max_chars=4000)

            content = (
                f"Sigortacılık ve Özel Emeklilik Düzenleme ve Denetleme Kurumu (SEDDK) Mevzuat Değişikliği\n"
                f"Düzenleme Başlığı: {reg_title}\n"
                f"Yürürlük: Resmî Gazete / Mevzuat.gov.tr yayımı\n"
                f"Kapsam: BES (Bireysel Emeklilik Sistemi), Sigorta ve Reasürans Şirketleri, Emeklilik Fonları\n"
                f"Belge URL: {reg_url}\n"
                f"Tarih (çekim): {today_str}"
            )
            if full_text.strip():
                content += f"\n\n=== YÖNETMELİK / TEBLİĞ TAM METNİ ===\n{full_text}"

            items.append(RawItem(
                source_name=source_name,
                url=reg_url,
                title=reg_title,
                content_text=content,
                raw_metadata={
                    "jurisdiction": "Turkey",
                    "category": "Insurance & Pension Regulator",
                    "has_full_text": bool(full_text.strip()),
                    "doc_type": "seddk_regulation",
                },
            ))

        logger.info("SEDDK extracted %d insurance/BES regulations.", len(items))
        return items
