"""Specialized fetcher for Turkish Official Gazettes (Resmî Gazete) and regulatory bodies (TCMB, SPK, BDDK)."""

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
        else:
            return self._fetch_resmi_gazete(source_name, limit)

    def _fetch_resmi_gazete(self, source_name: str, limit: int) -> list[RawItem]:
        """Scrape current daily issues, presidential decrees, regulations and communiqués from Resmî Gazete."""
        url = "https://www.resmigazete.gov.tr/"
        items: list[RawItem] = []

        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=12)
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                logger.warning("Resmî Gazete returned status %d", resp.status_code)
                return items

            soup = BeautifulSoup(resp.text, "html.parser")
            today_str = datetime.now().strftime("%d.%m.%Y")

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                title = a.get_text(strip=True)

                if len(title) < 15:
                    continue

                lower_title = title.lower()
                is_decree = any(k in lower_title for k in [
                    "karar", "kanun", "yönetmelik", "tebliğ", "genelge",
                    "fiyat", "vergi", "bakan", "hazine", "merkez bankası",
                    "borçlanma", "destekleme", "ithalat", "ihracat", "özelleştirme"
                ]) or any(k in href for k in ["eskiler", ".htm", ".pdf", "ilanlar"])

                if not is_decree:
                    continue

                clean_title = title.lstrip("–- ").strip()
                full_url = href if href.startswith("http") else f"https://www.resmigazete.gov.tr/{href.lstrip('/')}"

                content = (
                    f"T.C. Resmî Gazete İlanı / Mevzuat Değişikliği\n"
                    f"Tarih: {today_str}\n"
                    f"Başlık / Karar Metni: {clean_title}\n"
                    f"Belge Bağlantısı: {full_url}\n"
                    f"Resmî Gazete Yürütme ve İdare Bölümü uyarınca yayımlanan karar veya düzenleme."
                )

                item = RawItem(
                    source_name=source_name,
                    url=full_url,
                    title=clean_title,
                    content_text=content,
                    raw_metadata={
                        "jurisdiction": "Turkey",
                        "gazette_date": today_str,
                        "category": "Official Gazette",
                    },
                )
                items.append(item)

                if len(items) >= limit:
                    break

        except Exception as exc:
            logger.error("Failed fetching Resmî Gazete: %s", exc)

        logger.info("Resmî Gazete extracted %d regulatory decrees/laws.", len(items))
        return items

    def _fetch_tcmb(self, source_name: str, limit: int) -> list[RawItem]:
        """Fetch TCMB (Central Bank of Turkey) press releases and monetary policy announcements."""
        url = "https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Duyurular/Basin/"
        items: list[RawItem] = []

        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=12)
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                return items

            soup = BeautifulSoup(resp.text, "html.parser")
            today_str = datetime.now().strftime("%d.%m.%Y")

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(strip=True)

                if len(text) < 18:
                    continue

                if any(w in text.lower() for w in ["faiz", "para", "politika", "enflasyon", "zorunlu", "mevduat", "duyuru", "ppk", "tcmb", "karar"]):
                    full_url = href if href.startswith("http") else f"https://www.tcmb.gov.tr{href}"
                    content = (
                        f"Türkiye Cumhuriyet Merkez Bankası (TCMB) Basın Duyurusu\n"
                        f"Tarih: {today_str}\n"
                        f"Konu: {text}\n"
                        f"TCMB Para Politikası ve Makroihtiyati Düzenleme Bildirimi.\n"
                        f"Detay URL: {full_url}"
                    )
                    items.append(
                        RawItem(
                            source_name=source_name,
                            url=full_url,
                            title=text,
                            content_text=content,
                            raw_metadata={
                                "jurisdiction": "Turkey",
                                "category": "Central Bank",
                            },
                        )
                    )

                if len(items) >= limit:
                    break

        except Exception as exc:
            logger.error("Failed fetching TCMB press releases: %s", exc)

        logger.info("TCMB extracted %d policy releases.", len(items))
        return items

    def _fetch_spk(self, source_name: str, limit: int) -> list[RawItem]:
        """Fetch SPK (Capital Markets Board of Turkey) bulletins and announcements."""
        url = "https://spk.gov.tr/duyurular"
        items: list[RawItem] = []

        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=12)
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                return items

            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(strip=True)

                if len(text) > 20 and ("bülten" in text.lower() or "duyuru" in text.lower() or "karar" in text.lower() or "tedbir" in text.lower()):
                    full_url = href if href.startswith("http") else f"https://spk.gov.tr{href}"
                    content = (
                        f"Sermaye Piyasası Kurulu (SPK) Duyurusu\n"
                        f"Konu / Başlık: {text}\n"
                        f"Sermaye piyasaları ve halka arz/yaptırım bildirimi: {full_url}"
                    )
                    items.append(
                        RawItem(
                            source_name=source_name,
                            url=full_url,
                            title=text,
                            content_text=content,
                            raw_metadata={"jurisdiction": "Turkey", "category": "Securities Regulator"},
                        )
                    )
                    if len(items) >= limit:
                        break

        except Exception as exc:
            logger.error("Failed fetching SPK duyurular: %s", exc)

        logger.info("SPK extracted %d announcements.", len(items))
        return items

    def _fetch_bddk(self, source_name: str, limit: int) -> list[RawItem]:
        """Scrape BDDK (Banking Regulation and Supervision Agency) decisions and press releases."""
        url = "https://www.bddk.org.tr/Duyuru/Liste/39"
        items: list[RawItem] = []

        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, verify=False, timeout=12)
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                return items

            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(strip=True)

                if len(text) > 15 and "/duyuru/detay/" in href.lower():
                    clean_text = text.lstrip("0123456789. ")
                    full_url = href if href.startswith("http") else f"https://www.bddk.org.tr{href}"
                    content = (
                        f"Bankacılık Düzenleme ve Denetleme Kurumu (BDDK) Kararı / Basın Açıklaması\n"
                        f"Konu: {text}\n"
                        f"Kredi büyüme sınırlamaları, konut/tüketici kredileri, kart limitleri ve makroihtiyati finansal düzenleme bildirimi.\n"
                        f"Detay URL: {full_url}"
                    )
                    items.append(
                        RawItem(
                            source_name=source_name,
                            url=full_url,
                            title=clean_text,
                            content_text=content,
                            raw_metadata={"jurisdiction": "Turkey", "category": "Banking Regulator"},
                        )
                    )
                    if len(items) >= limit:
                        break

        except Exception as exc:
            logger.error("Failed fetching BDDK duyurular: %s", exc)

        logger.info("BDDK extracted %d announcements.", len(items))
        return items
