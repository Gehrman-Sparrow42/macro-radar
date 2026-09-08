"""Source registries for Central Banks, Official Gazettes, and Macro Regulatory Bodies."""

from typing import Any

MACRO_SOURCES: list[dict[str, Any]] = [
    # -----------------------------------------------------------------------
    # 🇹🇷 Turkish Official & Macro Sources
    # -----------------------------------------------------------------------
    {
        "source_name": "Resmi_Gazete_Mevzuat",
        "category": "Official Gazette",
        "jurisdiction": "Turkey",
        "strategy": "turkish_official",
        "sub_strategy": "resmi_gazete",
        "url": "https://www.resmigazete.gov.tr/",
        "limit": 12,
        "enabled": True,
    },
    {
        "source_name": "TCMB_Basin_Duyurulari",
        "category": "Central Bank",
        "jurisdiction": "Turkey",
        "strategy": "turkish_official",
        "sub_strategy": "tcmb_press",
        "url": "https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Duyurular/Basin/",
        "limit": 8,
        "enabled": True,
    },
    {
        "source_name": "SPK_Duyurulari",
        "category": "Securities Regulator",
        "jurisdiction": "Turkey",
        "strategy": "turkish_official",
        "sub_strategy": "spk_announcements",
        "url": "https://spk.gov.tr/duyurular",
        "limit": 6,
        "enabled": True,
    },
    {
        "source_name": "BDDK_Kararlari",
        "category": "Banking Regulator",
        "jurisdiction": "Turkey",
        "strategy": "turkish_official",
        "sub_strategy": "bddk_announcements",
        "url": "https://www.bddk.org.tr/Duyuru/Liste/39",
        "limit": 8,
        "enabled": True,
    },
    {
        "source_name": "Dunya_Ekonomi",
        "category": "Macro Shift",
        "jurisdiction": "Turkey",
        "strategy": "rss",
        "url": "https://www.dunya.com/rss",
        "limit": 8,
        "enabled": True,
    },
    {
        "source_name": "BloombergHT_Piyasa",
        "category": "Macro Shift",
        "jurisdiction": "Turkey",
        "strategy": "rss",
        "url": "https://www.bloomberght.com/rss",
        "limit": 8,
        "enabled": True,
    },
    {
        "source_name": "AA_Ekonomi",
        "category": "Macro Shift",
        "jurisdiction": "Turkey",
        "strategy": "rss",
        "url": "https://www.aa.com.tr/tr/rss/default?cat=guncel",
        "limit": 8,
        "enabled": True,
    },

    # -----------------------------------------------------------------------
    # 🌐 Global Central Banks & Sovereign Institutions
    # -----------------------------------------------------------------------
    {
        "source_name": "FederalReserve_Press",
        "category": "Central Bank",
        "jurisdiction": "United States",
        "strategy": "rss",
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "limit": 8,
        "enabled": True,
    },
    {
        "source_name": "FederalReserve_Monetary_Policy",
        "category": "Central Bank",
        "jurisdiction": "United States",
        "strategy": "rss",
        "url": "https://www.federalreserve.gov/feeds/press_monetary.xml",
        "limit": 6,
        "enabled": True,
    },
    {
        "source_name": "ECB_Press",
        "category": "Central Bank",
        "jurisdiction": "Eurozone",
        "strategy": "rss",
        "url": "https://www.ecb.europa.eu/rss/press.html",
        "limit": 8,
        "enabled": True,
    },
    {
        "source_name": "BankOfEngland_News",
        "category": "Central Bank",
        "jurisdiction": "United Kingdom",
        "strategy": "rss",
        "url": "https://www.bankofengland.co.uk/rss/news",
        "limit": 8,
        "enabled": True,
    },

    # -----------------------------------------------------------------------
    # 🌐 Global Regulatory Bodies & Securities Watchdogs
    # -----------------------------------------------------------------------
    {
        "source_name": "SEC_Press_Releases",
        "category": "Securities Regulator",
        "jurisdiction": "United States",
        "strategy": "rss",
        "url": "https://www.sec.gov/news/pressreleases.rss",
        "limit": 8,
        "enabled": True,
    },

    # -----------------------------------------------------------------------
    # 🌐 Global Market & Macroeconomic Shifts
    # -----------------------------------------------------------------------
    {
        "source_name": "Macro_MarketWatch",
        "category": "Macro Shift",
        "jurisdiction": "Global / US",
        "strategy": "rss",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "limit": 8,
        "enabled": True,
    },
    {
        "source_name": "Investing_Economic_News",
        "category": "Macro Shift",
        "jurisdiction": "Global",
        "strategy": "rss",
        "url": "https://www.investing.com/rss/news_14.rss",
        "limit": 8,
        "enabled": True,
    },
    {
        "source_name": "Investing_Emtia_Petrol",
        "category": "Commodity / Energy",
        "jurisdiction": "Global / Turkey Impact",
        "strategy": "rss",
        "url": "https://www.investing.com/rss/commodities.rss",
        "limit": 8,
        "enabled": True,
    },
]


def get_active_macro_sources(
    category: str | None = None,
    jurisdiction: str | None = None,
) -> list[dict[str, Any]]:
    """Return enabled sources with optional category and jurisdiction filtering."""
    sources = [s for s in MACRO_SOURCES if s.get("enabled", True)]
    if category:
        sources = [s for s in sources if s.get("category", "").lower() == category.lower()]
    if jurisdiction:
        sources = [s for s in sources if s.get("jurisdiction", "").lower() == jurisdiction.lower()]
    return sources
