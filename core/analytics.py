"""
Reads every scored client (client:*) back out of the KV store into a
DataFrame, for the business-analysis charts on the batch scoring page.

Note: uses KEYS + MGET, which is fine at the scale of a school/demo
project. For a production dataset with tens of thousands of clients,
swap to SCAN with a cursor to avoid blocking the Redis instance on a
single KEYS call.
"""
import json

import pandas as pd


def load_all_clients(db) -> pd.DataFrame:
    keys = db.keys("client:*")
    if not keys:
        return pd.DataFrame()

    values = db.mget(*keys)
    records = []
    for key, raw in zip(keys, values):
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        rec["customer_id"] = key.split("client:", 1)[1]
        records.append(rec)

    return pd.DataFrame(records)
