#!/usr/bin/env python3
"""
Standalone scheduled scoring script.

Run this OUTSIDE Streamlit — via cron, Windows Task Scheduler, or a
GitHub Actions workflow (see .github/workflows/scheduled_scoring.yml).
Streamlit apps don't run background jobs on their own, so this script
is what actually performs the "5. Batch/pipeline" scheduled scoring;
the app's dashboard tab just displays what this script last wrote.

Usage:
    python scheduler.py path/to/transactions.csv
"""
import sys

import pandas as pd

from core.batch_job import run_batch_job
from core.db import get_client
from core.model_loader import load_pipeline


def main():
    if len(sys.argv) < 2:
        print("Usage: python scheduler.py <transactions.csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    raw_df = pd.read_csv(csv_path)

    pipeline = load_pipeline()
    db = get_client()

    _, summary = run_batch_job(raw_df, pipeline, db, source="scheduled")

    print(f"Batch scoring done: {summary['n_clients']} clients, run at {summary['run_at']}")
    print(f"Segment counts: {summary['segment_counts']}")


if __name__ == "__main__":
    main()
