import json

import pandas as pd
import plotly.express as px
import streamlit as st

from core.analytics import load_all_clients
from core.batch_job import run_batch_job
from core.db import get_client
from core.model_loader import load_pipeline
from core.theme import (
    SEGMENT_COLOR_MAP,
    inject,
    plotly_layout,
    pulse_header,
    segment_pill,
    tone_for,
    vital_card,
    vital_grid,
)

st.set_page_config(page_title="Pouls Client — Lot", page_icon="assets/icon.png", layout="wide")
inject()

METRIC_LABELS = {"recency": "Recency", "frequency": "Frequency", "monetary": "Monetary"}


@st.cache_resource
def get_model():
    return load_pipeline()


@st.cache_resource
def get_db():
    return get_client()


pulse_header("Traitement par lot", "Scoring & analyse")

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

tab_run, tab_dashboard, tab_analysis = st.tabs(["Scoring à la demande", "Dernier run planifié", "Analyse"])

with tab_run:
    st.caption(
        "CSV de transactions brutes — colonnes attendues : Customer ID, Invoice, "
        "InvoiceDate, Quantity, Price. Exemple fourni dans data/sample_transactions.csv."
    )
    uploaded = st.file_uploader("Fichier CSV", type="csv", label_visibility="collapsed")

    if uploaded is not None and models_ok and db_ok:
        raw_df = pd.read_csv(uploaded)
        with st.spinner("Calcul en cours…"):
            try:
                result_df, summary = run_batch_job(raw_df, pipeline, db, source="upload")
            except ValueError as e:
                st.error(str(e))
                result_df, summary = None, None

        if result_df is not None:
            st.caption(f"{summary['n_clients']} clients scorés et archivés.")
            st.dataframe(result_df.head(50), use_container_width=True)
            csv_bytes = result_df.to_csv(index=False).encode("utf-8")
            st.download_button("Télécharger le résultat", csv_bytes, "rfm_scoring_results.csv", "text/csv")
            st.caption("Détails par segment — onglet Analyse.")

with tab_dashboard:
    st.caption(
        "État du dernier job planifié, exécuté hors application "
        "(cron / Task Scheduler / GitHub Actions via scheduler.py)."
    )
    if db_ok:
        try:
            last_run_raw = db.get("batch:last_run")
        except Exception as e:
            last_run_raw = None
            st.warning(f"Lecture impossible — {e}")

        if last_run_raw:
            last_run = json.loads(last_run_raw)
            vital_grid([
                vital_card("Clients scorés", last_run.get("n_clients", "—")),
                vital_card("Exécuté (UTC)", str(last_run.get("run_at", "—"))[:19].replace("T", " ")),
                vital_card("Origine", last_run.get("source", "—")),
            ])

            counts = last_run.get("segment_counts", {})
            if counts:
                order = [s for s in SEGMENT_COLOR_MAP if s in counts]
                fig = px.bar(
                    x=order, y=[counts[s] for s in order],
                    color=order, color_discrete_map=SEGMENT_COLOR_MAP,
                    labels={"x": "", "y": "Clients"},
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(plotly_layout(fig, height=320), use_container_width=True)
        else:
            st.info("Aucun run planifié pour le moment — configurez scheduler.py (voir README).")
    else:
        st.info("Base non connectée.")

with tab_analysis:
    st.caption("Ensemble des clients actuellement archivés en base — dernier état connu, tous runs confondus.")

    if not db_ok:
        st.info("Base non connectée.")
    else:
        clients_df = load_all_clients(db)

        if clients_df.empty:
            st.info("Aucun client en base — lancez un scoring pour peupler cette vue.")
        else:
            total_clients = len(clients_df)
            total_revenue = clients_df["monetary"].sum()
            avg_monetary = clients_df["monetary"].mean()
            avg_frequency = clients_df["frequency"].mean()

            vital_grid([
                vital_card("Clients", f"{total_clients:,}"),
                vital_card("Revenu total", f"{total_revenue:,.0f}", " €"),
                vital_card("Panier moyen", f"{avg_monetary:,.0f}", " €"),
                vital_card("Fréquence moy.", f"{avg_frequency:.1f}"),
            ])

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Répartition par segment**")
                seg_counts = clients_df["label"].value_counts()
                order = [s for s in SEGMENT_COLOR_MAP if s in seg_counts.index]
                fig = px.bar(
                    x=order, y=[seg_counts[s] for s in order],
                    color=order, color_discrete_map=SEGMENT_COLOR_MAP,
                    labels={"x": "", "y": "Clients"},
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(plotly_layout(fig), use_container_width=True)

            with col_b:
                st.markdown("**Part du revenu par segment**")
                rev_by_seg = clients_df.groupby("label")["monetary"].sum()
                order = [s for s in SEGMENT_COLOR_MAP if s in rev_by_seg.index]
                fig = px.pie(
                    names=order, values=[rev_by_seg[s] for s in order],
                    color=order, color_discrete_map=SEGMENT_COLOR_MAP, hole=0.55,
                )
                fig.update_traces(textfont=dict(family="IBM Plex Mono, monospace"))
                st.plotly_chart(plotly_layout(fig), use_container_width=True)

            st.markdown("**Distribution par segment**")
            metric_choice = st.radio(
                "Métrique", list(METRIC_LABELS.keys()), horizontal=True,
                format_func=lambda x: METRIC_LABELS[x], label_visibility="collapsed",
            )
            fig = px.box(
                clients_df, x="label", y=metric_choice, color="label",
                color_discrete_map=SEGMENT_COLOR_MAP, points="outliers",
                category_orders={"label": [s for s in SEGMENT_COLOR_MAP if s in clients_df["label"].unique()]},
            )
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title=METRIC_LABELS[metric_choice])
            st.plotly_chart(plotly_layout(fig), use_container_width=True)

            st.markdown("**Fréquence vs montant**")
            fig = px.scatter(
                clients_df, x="frequency", y="monetary", color="label", size="monetary",
                color_discrete_map=SEGMENT_COLOR_MAP,
                hover_data=["customer_id", "recency"],
                labels={"frequency": "Frequency", "monetary": "Monetary", "label": "Segment"},
                opacity=0.75,
            )
            st.plotly_chart(plotly_layout(fig, height=420), use_container_width=True)

            st.markdown("**Profil moyen par segment**")
            profils = clients_df.groupby("label")[["recency", "frequency", "monetary"]].mean().round(1)
            profils.columns = ["Recency", "Frequency", "Monetary"]
            profils["Clients"] = clients_df["label"].value_counts()
            profils["Part"] = (profils["Clients"] / total_clients * 100).round(1).astype(str) + "%"
            order = [s for s in SEGMENT_COLOR_MAP if s in profils.index]
            st.dataframe(profils.loc[order], use_container_width=True)
