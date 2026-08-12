"""
Cluster label mapping. All numeric preprocessing (log1p + scaling) now
lives INSIDE the exported sklearn Pipeline (model/rfm_pipeline.pkl), so
there's nothing to replicate here manually anymore.
"""
RFM_COLUMNS = ["Recency", "Frequency", "Monetary"]

# Cluster index -> business label, taken from the notebook's interpretation
# (section 11). Fixed because the pipeline is loaded already fitted, not
# retrained, so cluster indices never shuffle between runs.
CLUSTER_LABELS = {
    0: "Champions",
    1: "Perdus",
    2: "À risque",
    3: "Prometteurs",
}
