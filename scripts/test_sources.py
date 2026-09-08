import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

from radar_macro.config.sources import MACRO_SOURCES
from radar_macro.fetchers.turkish_fetcher import TurkishOfficialFetcher
from radar_core.core.fetchers.rss_fetcher import RSSFetcher

turkish_fetcher = TurkishOfficialFetcher()
rss_fetcher = RSSFetcher()

print("=" * 80)
print(f"CANLI VERİ KAYNAĞI DENETİMİ ({len(MACRO_SOURCES)} Kaynak)")
print("=" * 80)

results = []

for src in MACRO_SOURCES:
    name = src["source_name"]
    strat = src.get("strategy", "rss")
    url = src.get("url", "")
    t0 = time.perf_counter()
    status = "OK"
    items = []
    err_msg = ""

    try:
        if strat == "turkish_official":
            items = turkish_fetcher.fetch(src)
        else:
            items = rss_fetcher.fetch(src)
        
        latency = round((time.perf_counter() - t0) * 1000)
        sample = items[0].title if items else "Veri Yok"
        results.append({
            "name": name,
            "strategy": strat,
            "count": len(items),
            "status": "SUCCESS" if len(items) > 0 else "EMPTY",
            "latency": latency,
            "sample": sample[:55],
            "error": None
        })
        print(f"[{name}] -> {len(items)} öğe ({latency}ms) | Örnek: {sample[:45]}")
    except Exception as exc:
        latency = round((time.perf_counter() - t0) * 1000)
        results.append({
            "name": name,
            "strategy": strat,
            "count": 0,
            "status": "FAILED",
            "latency": latency,
            "sample": "-",
            "error": str(exc)[:60]
        })
        print(f"[{name}] -> HATA ({latency}ms): {exc}")

print("\n" + "=" * 80)
print("ÖZET RAPOR:")
print("=" * 80)
for r in results:
    icon = "✅" if r["status"] == "SUCCESS" else ("⚠️" if r["status"] == "EMPTY" else "❌")
    print(f"{icon} {r['name']:<28} | {r['count']:>2} öğe | {r['latency']:>5}ms | {r['sample']}")
