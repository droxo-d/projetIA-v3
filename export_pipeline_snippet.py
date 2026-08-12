# Remplace la cellule "Entraînement du modèle final" (celle qui faisait
# à l'origine kmeans_final.fit(rfm_scaled) puis rfm['Cluster'] = ...) par
# ce bloc. Il fait la même chose, mais avec un seul Pipeline qui embarque
# log1p + StandardScaler + KMeans.

import numpy as np
import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, FunctionTransformer
from sklearn.cluster import KMeans

RFM_COLUMNS = ["Recency", "Frequency", "Monetary"]

rfm_pipeline = Pipeline([
    ("log1p", FunctionTransformer(np.log1p, validate=True)),
    ("scaler", StandardScaler()),
    ("kmeans", KMeans(n_clusters=4, random_state=42, n_init=10)),
])

# Fit directement sur le RFM brut (non-loggé, non-scalé) — le pipeline
# s'occupe du log1p + de la normalisation en interne.
rfm_pipeline.fit(rfm[RFM_COLUMNS])

# IMPORTANT : réassigner la colonne Cluster sur rfm, comme le faisait
# l'ancienne cellule — sinon toutes les cellules suivantes (profils par
# cluster, graphiques, rfm['Nom_Cluster'] = ...) échouent avec un
# KeyError: 'Cluster'.
rfm['Cluster'] = rfm_pipeline.named_steps["kmeans"].labels_

print("Modèle entraîné.")
print("\nRépartition des clients par cluster :")
print(rfm['Cluster'].value_counts().sort_index())

joblib.dump(rfm_pipeline, "rfm_pipeline.pkl")
print("\nExporté : rfm_pipeline.pkl — c'est le seul fichier dont l'app a besoin.")
