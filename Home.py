import datetime as dt
import json

import pandas as pd
import streamlit as st

from core.db import get_client
from core.model_loader import load_pipeline
from core.preprocessing import CLUSTER_LABELS, RFM_COLUMNS
from core.theme import inject, pulse_header, result_panel, tone_for

st.set_page_config(page_title="Pouls Client — RFM", page_icon="assets/icon.png", layout="centered")
inject()


@st.cache_resource
def get_model():
    return load_pipeline()


@st.cache_resource
def get_db():
    return get_client()


pulse_header("Diagnostic client", "Lecture en direct")
st.caption("Renseignez les métriques d'un client pour lire son état — segment K-Means à 4 profils.")

try:
    pipeline = get_model()
    models_ok = True
except FileNotFoundError as e:
    models_ok = False
    st.error(str(e))

try:
    db = get_db()
    db_ok = True
except RuntimeError as e:
    db_ok = False
    st.warning(f"Base non connectée — {e}")

if models_ok:
    with st.form("rfm_form"):
        client_id = st.text_input("Identifiant client (facultatif — pour archiver le résultat)")
        col1, col2, col3 = st.columns(3)
        recency = col1.number_input("Recency — jours depuis le dernier achat", min_value=0, value=30)
        frequency = col2.number_input("Frequency — factures distinctes", min_value=1, value=5)
        monetary = col3.number_input("Monetary — total dépensé (€)", min_value=0.0, value=500.0, step=10.0)
        submitted = st.form_submit_button("Lire le segment")

    if submitted:
        df = pd.DataFrame([{"Recency": recency, "Frequency": frequency, "Monetary": monetary}])
        cluster = int(pipeline.predict(df[RFM_COLUMNS])[0])
        label = CLUSTER_LABELS.get(cluster, f"Cluster {cluster}")
        tone = tone_for(label)

        result_panel(f"Segment — <b>{label}</b> &nbsp;·&nbsp; cluster {cluster}", tone["hex"])

        if client_id and db_ok:
            record = {
                "recency": recency,
                "frequency": frequency,
                "monetary": monetary,
                "cluster": cluster,
                "label": label,
                "scored_at": dt.datetime.utcnow().isoformat(),
            }
            try:
                db.set(f"client:{client_id}", json.dumps(record))
                st.caption(f"Archivé — client:{client_id}")
            except Exception as e:
                st.warning(f"Écriture impossible — {e}")
        elif not client_id:
            st.caption("Sans identifiant, ce résultat n'est pas archivé.")

st.divider()
st.page_link("pages/1_Batch_Scoring.py", label="Scoring par lot →")
