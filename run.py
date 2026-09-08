"""
Yatırım Radarı - Root Entrypoint Script
Usage:
    python run.py --dashboard            # Starts the web terminal on http://127.0.0.1:8501
    python run.py --run-once             # Runs single ingestion & analysis cycle
    python run.py --daemon               # Runs scheduled ingestion daemon
    python run.py --backfill             # Backfills 3-month macro memory
"""
import sys
from pathlib import Path

# Add project root to sys.path so radar_core and radar_macro are importable
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from radar_macro.run import main

if __name__ == "__main__":
    main()
