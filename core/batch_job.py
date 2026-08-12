"""
Batch scoring pipeline: raw transactions -> RFM -> pipeline.predict() -> KV store.

Reused by both the Streamlit "upload & score" tab and scheduler.py
(run standalone via cron / GitHub Actions), so the two code paths can
never drift apart.
"""
import datetime as dt
import json

import pandas as pd

from core.preprocessing import RFM_COLUMNS, CLUSTER_LABELS

RAW_TRANSACTION_COLUMNS = ["Customer ID", "Invoice", "InvoiceDate", "Quantity", "Price"]

# Upstash free tier caps command size; chunk client writes to be safe on
# large batches instead of one giant pipeline.
WRITE_CHUNK_SIZE = 500


def compute_rfm(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Mirrors notebook sections 3-4: cleaning + RFM aggregation."""
    missing = set(RAW_TRANSACTION_COLUMNS) - set(raw_df.columns)
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {missing}")

    df = raw_df.dropna(subset=["Customer ID"]).copy()
    df = df[df["Quantity"] > 0]
    df = df[df["Price"] > 0]
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["TotalPrice"] = df["Quantity"] * df["Price"]

    date_reference = df["InvoiceDate"].max() + pd.Timedelta(days=1)

    rfm = (
        df.groupby("Customer ID")
        .agg(
            Recency=("InvoiceDate", lambda x: (date_reference - x.max()).days),
            Frequency=("Invoice", "nunique"),
            Monetary=("TotalPrice", "sum"),
        )
        .reset_index()
    )
    return rfm


def score_rfm(rfm_df: pd.DataFrame, pipeline) -> pd.DataFrame:
    """pipeline handles log1p + scaling + clustering internally."""
    scored = rfm_df.copy()
    scored["cluster"] = pipeline.predict(rfm_df[RFM_COLUMNS])
    scored["label"] = scored["cluster"].map(CLUSTER_LABELS)
    return scored


def persist_results(scored_df: pd.DataFrame, db, source: str) -> dict:
    now = dt.datetime.utcnow().isoformat()

    rows = scored_df.to_dict(orient="records")
    for i in range(0, len(rows), WRITE_CHUNK_SIZE):
        chunk = rows[i : i + WRITE_CHUNK_SIZE]
        pipe = db.pipeline()
        for row in chunk:
            record = {
                "recency": float(row["Recency"]),
                "frequency": float(row["Frequency"]),
                "monetary": float(row["Monetary"]),
                "cluster": int(row["cluster"]),
                "label": row["label"],
                "scored_at": now,
            }
            pipe.set(f"client:{row['Customer ID']}", json.dumps(record))
        pipe.exec()

    segment_counts = scored_df["label"].value_counts().to_dict()
    summary = {
        "run_at": now,
        "n_clients": len(scored_df),
        "segment_counts": segment_counts,
        "source": source,
    }
    db.set("batch:last_run", json.dumps(summary))
    return summary


def run_batch_job(raw_df: pd.DataFrame, pipeline, db, source: str = "scheduled"):
    """End-to-end: raw transactions -> scored + persisted. Returns (scored_df, summary)."""
    rfm_df = compute_rfm(raw_df)
    scored_df = score_rfm(rfm_df, pipeline)
    summary = persist_results(scored_df, db, source)
    return scored_df, summary
