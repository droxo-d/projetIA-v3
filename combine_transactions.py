#!/usr/bin/env python3
"""
Merge every raw transaction CSV in a directory into one file, so a single
scheduled run scores everyone at once instead of one file at a time.

Only files matching the raw transaction schema (Customer ID, Invoice,
InvoiceDate, Quantity, Price) are combined — sample_rfm_table.csv is
skipped automatically since it's already aggregated RFM, not raw
transactions, and mixing the two formats would break compute_rfm().

Usage:
    python combine_transactions.py [source_dir] [output_path]
    Defaults: source_dir=data, output_path=data/combined_transactions.csv
"""
import glob
import sys

import pandas as pd

from core.batch_job import RAW_TRANSACTION_COLUMNS


def main():
    source_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "data/combined_transactions.csv"

    csv_files = sorted(glob.glob(f"{source_dir}/*.csv"))
    frames = []

    for path in csv_files:
        if path == output_path:
            continue
        header = pd.read_csv(path, nrows=0)
        if set(RAW_TRANSACTION_COLUMNS).issubset(header.columns):
            frames.append(pd.read_csv(path))
        else:
            print(f"Ignoré (colonnes incompatibles) : {path}")

    if not frames:
        print("Aucun fichier de transactions brutes trouvé.")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(output_path, index=False)
    print(f"{len(frames)} fichier(s) combinés -> {output_path} ({len(combined)} lignes)")


if __name__ == "__main__":
    main()
