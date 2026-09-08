"""CLI Entrypoint for radar_core running scheduled or on-demand pipeline ingestion and analysis."""

import argparse
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
PARENT_ROOT = PROJECT_ROOT.parent
if str(PARENT_ROOT) not in sys.path:
    sys.path.insert(0, str(PARENT_ROOT))

from radar_core.config.settings import setup_logging
from radar_core.core.database import init_db
from radar_core.pipelines.dummy_pipeline import get_pipeline

logger = logging.getLogger("radar_core.main")


def run_pipeline_cycle(pipeline_name: str, batch_size: int) -> None:
    """Execute a single ingestion and processing cycle for the chosen pipeline."""
    pipeline = get_pipeline(pipeline_name)
    sources = getattr(pipeline, "get_default_sources", lambda: [])()
    logger.info("Starting radar execution cycle for [%s] with %d sources...", pipeline_name, len(sources))

    stats = pipeline.run(source_configs=sources, batch_size=batch_size)

    ingest_stats = stats.get("ingestion", {})
    process_stats = stats.get("processing", {})

    logger.info(
        "Execution summary for [%s] -> Fetched: %d | New Saved: %d | Duplicates Ignored: %d | Evaluated: %d | Analyzed: %d | Skipped: %d",
        pipeline_name,
        ingest_stats.get("total_fetched", 0),
        ingest_stats.get("new_saved", 0),
        ingest_stats.get("duplicates_skipped", 0),
        process_stats.get("evaluated", 0),
        process_stats.get("analyzed", 0),
        process_stats.get("prefiltered_skipped", 0),
    )


def start_dashboard() -> None:
    """Launch the local Streamlit dashboard."""
    dashboard_path = PROJECT_ROOT / "dashboard" / "app.py"
    logger.info("Launching Streamlit dashboard from %s...", dashboard_path)
    cmd = [sys.executable, "-m", "streamlit", "run", str(dashboard_path)]
    subprocess.run(cmd)


def main() -> None:
    """Parse CLI arguments and dispatch pipeline execution or dashboard."""
    parser = argparse.ArgumentParser(
        description="Radar Core: Shared Ingestion & Analysis Engine for Macro Risk & Market Discovery"
    )
    parser.add_argument(
        "--pipeline",
        type=str,
        choices=["dummy", "finance", "market"],
        default="dummy",
        help="Target radar pipeline to execute (default: dummy)",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Execute a single pass of the pipeline and exit",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Interval in seconds between scheduled cycles (default: 300s)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Max items to process in each cycle (default: 10)",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database tables and exit",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Launch the Streamlit intelligence dashboard",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging verbosity level",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    # Initialize SQLite database
    init_db()

    if args.init_db:
        logger.info("Database initialized successfully. Exiting as requested.")
        return

    if args.dashboard:
        start_dashboard()
        return

    if args.run_once:
        logger.info("Running single-pass execution for [%s]...", args.pipeline)
        run_pipeline_cycle(args.pipeline, args.batch_size)
        logger.info("Single pass complete.")
        return

    # Scheduled execution loop
    logger.info(
        "Starting scheduled continuous loop for [%s] (interval: %ds, batch_size: %d)...",
        args.pipeline,
        args.interval,
        args.batch_size,
    )
    try:
        while True:
            run_pipeline_cycle(args.pipeline, args.batch_size)
            logger.info("Sleeping for %d seconds before next cycle...", args.interval)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal. Gracefully shutting down radar core.")


if __name__ == "__main__":
    main()
