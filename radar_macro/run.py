"""CLI Runner for radar_macro application."""

import argparse
import logging
from pathlib import Path
import sys
import threading
import time
import webbrowser
import uvicorn

# Ensure project paths are in sys.path
APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent

for p in [str(APP_ROOT), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from radar_macro.config.settings import get_macro_settings, setup_macro_logging
from radar_macro.pipeline import MacroImpactPipeline

logger = logging.getLogger("radar_macro.run")


def run_cycle(
    category: str | None = None,
    jurisdiction: str | None = None,
    batch_size: int = 8,
) -> None:
    """Execute a single ingestion and policy analysis cycle across Turkish and Global feeds."""
    pipeline = MacroImpactPipeline()
    sources = pipeline.get_sources(category=category, jurisdiction=jurisdiction)
    for s in sources:
        s["limit"] = batch_size

    logger.info("Triggering macro surveillance cycle across %d sources...", len(sources))
    stats = pipeline.run(source_configs=sources, batch_size=batch_size * 2)

    # Drain backlog items
    extra_stats = pipeline.process_queue(batch_size=batch_size * 2)
    stats["processing"]["evaluated"] += extra_stats.get("evaluated", 0)
    stats["processing"]["analyzed"] += extra_stats.get("analyzed", 0)
    stats["processing"]["prefiltered_skipped"] += extra_stats.get("prefiltered_skipped", 0)

    ing = stats.get("ingestion", {})
    proc = stats.get("processing", {})

    logger.info(
        "Surveillance Cycle Summary -> Ingested: %d | New Saved: %d | Duplicates Ignored: %d | Evaluated: %d | Analyzed: %d | Skipped: %d",
        ing.get("total_fetched", 0),
        ing.get("new_saved", 0),
        ing.get("duplicates_skipped", 0),
        proc.get("evaluated", 0),
        proc.get("analyzed", 0),
        proc.get("prefiltered_skipped", 0),
    )


def start_macro_dashboard(port: int = 8501, open_browser: bool = True) -> None:
    """Launch the High-Performance Modular Macro Intelligence Financial Terminal."""
    logger.info("Launching Modular Macro Terminal UI on http://127.0.0.1:%d...", port)

    if open_browser:
        def _open():
            time.sleep(1.2)
            webbrowser.open(f"http://127.0.0.1:{port}")
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run("radar_macro.server:app", host="127.0.0.1", port=port, log_level="info")


def main() -> None:
    """Parse CLI flags and dispatch execution."""
    parser = argparse.ArgumentParser(
        description="Radar Macro: Macro & Regulatory Impact Intelligence Surveillance"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Execute a single surveillance pass and exit",
    )
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="Run continuous periodic surveillance loop",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Polling interval in seconds between cycles (default: 3600s / 1hr)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter ingestion to specific category (e.g. 'Central Bank', 'Official Gazette')",
    )
    parser.add_argument(
        "--jurisdiction",
        type=str,
        default=None,
        help="Filter ingestion to specific jurisdiction (e.g. 'Turkey', 'Global')",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Max items to fetch per source (default: 8)",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Launch the modular FastAPI & Vanilla JS macro financial dashboard",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Port for the macro terminal dashboard (default: 8501)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not auto-open browser on dashboard launch",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize isolated macro_radar.db and exit",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level",
    )

    args = parser.parse_args()
    setup_macro_logging(args.log_level)
    settings = get_macro_settings()

    if args.init_db:
        from radar_core.core.database import get_engine, init_db
        get_engine(settings.DATABASE_URL)
        init_db(settings.DATABASE_URL)
        logger.info("Macro database initialized at %s", settings.DATABASE_URL)
        return

    if args.dashboard:
        start_macro_dashboard(port=args.port, open_browser=not args.no_browser)
        return

    if args.run_once or not args.scheduled:
        run_cycle(category=args.category, jurisdiction=args.jurisdiction, batch_size=args.batch_size)
        return

    logger.info(
        "Starting macro surveillance daemon (interval: %ds, category: %s, jurisdiction: %s)...",
        args.interval,
        args.category or "ALL",
        args.jurisdiction or "ALL",
    )
    try:
        while True:
            run_cycle(category=args.category, jurisdiction=args.jurisdiction, batch_size=args.batch_size)
            logger.info("Sleeping for %d seconds...", args.interval)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Received interrupt. Gracefully shutting down macro surveillance daemon.")


if __name__ == "__main__":
    main()
