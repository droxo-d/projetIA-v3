"""
Upstash Redis (KV, REST-based) client wrapper.

Credentials are read from, in order:
  1. Environment variables UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN
     (used by scheduler.py, cron, GitHub Actions)
  2. Streamlit secrets (.streamlit/secrets.toml, or the Streamlit Cloud
     "Secrets" panel) — used when running inside the app.
"""
import os


def get_client():
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

    if not url or not token:
        try:
            import streamlit as st
            url = url or st.secrets.get("UPSTASH_REDIS_REST_URL")
            token = token or st.secrets.get("UPSTASH_REDIS_REST_TOKEN")
        except Exception:
            pass

    if not url or not token:
        raise RuntimeError(
            "Missing Upstash credentials. Set UPSTASH_REDIS_REST_URL and "
            "UPSTASH_REDIS_REST_TOKEN as environment variables, or add them "
            "to .streamlit/secrets.toml (see .streamlit/secrets.toml.example)."
        )

    from upstash_redis import Redis
    return Redis(url=url, token=token)
