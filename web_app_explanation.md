# Pouls Client — Segmentation RFM
### Documentation technique et fonctionnelle

---

## 1. Objectif du projet

L'application met en production un modèle de segmentation client basé
sur la méthode **RFM** (Recency, Frequency, Monetary) et un clustering
**K-Means à 4 groupes**, entraîné dans `Segmentation_des_clients.ipynb`.
Elle permet de :

- scorer un client individuellement, en direct ;
- scorer un lot de clients à partir de transactions brutes ;
- automatiser ce scoring de façon planifiée (hors application) ;
- visualiser les résultats sous forme d'indicateurs business.

Les quatre segments issus du modèle :

| Segment | Sens métier |
|---|---|
| **Champions** | Clients récents, fréquents, à forte valeur — la base la plus rentable |
| **Prometteurs** | Clients en progression, à fidéliser |
| **À risque** | Clients autrefois actifs, dont l'engagement diminue |
| **Perdus** | Clients inactifs depuis longtemps |

---

## 2. Vue d'ensemble de l'architecture

```
                         ┌─────────────────────────┐
                         │   Notebook (entraînement) │
                         │  Segmentation_des_clients │
                         └────────────┬─────────────┘
                                      │ export_pipeline_snippet.py
                                      ▼
                         model/rfm_pipeline.pkl
                         (log1p → StandardScaler → KMeans, un seul objet)
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
   Home.py                 pages/1_Batch_Scoring.py            scheduler.py
 (prédiction live)      (scoring à la demande + analyse)     (scoring planifié,
        │                             │                        hors app)
        └──────────────┬──────────────┴──────────────┬─────────────┘
                        ▼                             ▼
                   core/batch_job.py            core/db.py
              (RFM brut → scoré → Redis)     (client Upstash Redis)
                        │
                        ▼
              Upstash Redis (base clé-valeur)
              client:{id} · batch:last_run
```

**Principe central : une seule logique métier, trois points d'entrée.**
Le calcul RFM, le scoring et l'écriture en base vivent uniquement dans
`core/`. Que le scoring soit déclenché depuis la page 1, la page 2 ou un
cron GitHub Actions, c'est exactement le même code qui s'exécute — donc
aucun risque d'incohérence entre les trois chemins.

---

## 3. Stack technique

| Composant | Rôle |
|---|---|
| **Streamlit** | Framework web de l'application (2 pages) |
| **scikit-learn** | Pipeline de preprocessing + modèle K-Means |
| **joblib** | Sérialisation du pipeline entraîné |
| **pandas / numpy** | Calcul du RFM, manipulation des données |
| **Upstash Redis** | Base clé-valeur serverless, accessible en REST |
| **Plotly** | Graphes interactifs de l'onglet Analyse |
| **GitHub Actions** | Orchestration du scoring planifié (cron) |

Aucune base de données relationnelle, aucun serveur à gérer : Upstash
Redis est facturé à la requête (tier gratuit largement suffisant pour ce
projet) et Streamlit Community Cloud héberge l'app gratuitement.

---

## 4. Le modèle : un pipeline scikit-learn unique

Le fichier `model/rfm_pipeline.pkl` contient un objet
`sklearn.pipeline.Pipeline` à trois étapes :

```
log1p  →  StandardScaler  →  KMeans(n_clusters=4)
```

Ce choix (un seul artefact plutôt que modèle + scaler séparés) élimine
un problème classique de mise en production : le risque que le scaler et
le modèle finissent par ne plus correspondre (données prétraitées
différemment à l'entraînement et à l'inférence). `export_pipeline_snippet.py`
génère ce fichier depuis le notebook, en réutilisant exactement les
paramètres d'entraînement (`random_state=42`, `n_init=10`), donc les
indices de clusters (0 à 3) restent stables et le mapping vers les noms
de segments (`core/preprocessing.py`) reste valide.

---

## 5. Fonctionnalités — Page 1 : Diagnostic client

Formulaire à trois champs (Recency, Frequency, Monetary) :

1. L'utilisateur saisit les métriques d'un client.
2. `pipeline.predict()` renvoie l'index de cluster.
3. L'index est traduit en nom de segment et affiché immédiatement.
4. Si un identifiant client est renseigné, le résultat est archivé dans
   Redis sous la clé `client:{id}`.

Usage typique : un conseiller client vérifie le profil d'un client en
temps réel, par exemple avant un appel commercial.

---

## 6. Fonctionnalités — Page 2 : Scoring par lot

Trois onglets, chacun avec un rôle distinct.

### 6.1 Scoring à la demande
Upload d'un CSV de transactions brutes (`Customer ID`, `Invoice`,
`InvoiceDate`, `Quantity`, `Price`). Le pipeline complet s'exécute :
agrégation RFM (`compute_rfm`) → scoring → écriture en base → affichage
du résultat + téléchargement CSV. Utile pour un scoring ponctuel, à la
volée.

### 6.2 Dernier run planifié
Tableau de bord **passif** : il ne fait aucun calcul, il relit
`batch:last_run` dans Redis et affiche l'état du dernier scoring
automatisé (nombre de clients, horodatage, origine, répartition par
segment). Reflète ce que `scheduler.py` a produit lors de sa dernière
exécution, indépendamment de l'application.

### 6.3 Analyse
Reconstitue une vue d'ensemble à partir de **tous** les clients
actuellement en base (`client:*`), tous runs confondus — pas seulement
le dernier lot :

- indicateurs clés (nombre de clients, revenu total, panier moyen,
  fréquence moyenne) ;
- répartition des clients par segment ;
- part du revenu générée par chaque segment (identifie qui rapporte
  réellement) ;
- distribution de Recency/Frequency/Monetary par segment (boxplots) ;
- nuage de points Fréquence × Montant, coloré par segment ;
- tableau de profils moyens par segment.

C'est la vue destinée à une lecture business plutôt qu'à un contrôle
technique.

---

## 7. Scoring planifié — fonctionnement hors application

Streamlit ne peut pas exécuter de tâche de fond de façon fiable : le
scoring "planifié" est donc un processus **totalement indépendant** de
l'application web.

```
combine_transactions.py   →   scheduler.py   →   Redis
(fusionne les CSV bruts)      (RFM + scoring)     (client:*, batch:last_run)
```

- **`combine_transactions.py`** : regroupe plusieurs fichiers de
  transactions (un export par jour/magasin, etc.) en un seul CSV. Il
  ignore automatiquement tout fichier dont les colonnes ne correspondent
  pas au schéma attendu (ex. `sample_rfm_table.csv`, déjà agrégé).
- **`scheduler.py`** : reçoit un CSV de transactions, exécute le même
  pipeline que la page 2, écrase `batch:last_run` et chaque
  `client:{id}` dans Redis.
- **Déclenchement** : cron (Linux/Mac), Task Scheduler (Windows), ou
  GitHub Actions (`.github/workflows/scheduled_scoring.yml`, déjà
  configuré pour tourner chaque jour à 3h UTC et combiner automatiquement
  les fichiers avant de lancer le scoring).

L'onglet **Dernier run planifié** de la page 2 n'est qu'une fenêtre sur
le résultat de ce processus — il ne le déclenche jamais lui-même.

---

## 8. Base de données — schéma Redis

Redis est une base **clé-valeur** : pas de schéma imposé, la structure
est une convention de nommage définie par l'application.

| Clé | Contenu (JSON) | Écrite par |
|---|---|---|
| `client:{Customer ID}` | `{recency, frequency, monetary, cluster, label, scored_at}` | Page 1, Page 2, `scheduler.py` |
| `batch:last_run` | `{run_at, n_clients, segment_counts, source}` | Page 2 (scoring à la demande), `scheduler.py` |

Chaque client n'a qu'un seul état, écrasé à chaque nouveau scoring — pas
d'historique conservé (choix volontaire pour rester simple ; passer à
une clé par run serait nécessaire pour suivre l'évolution d'un client
dans le temps). L'onglet Analyse reconstruit sa vue à la volée avec
`KEYS client:*` + `MGET`, une approche adaptée à l'échelle de ce projet
mais à remplacer par un `SCAN` par curseur sur un très gros volume.

---

## 9. Interface — système de design

L'interface reprend une métaphore de **moniteur de constantes vitales** :
chaque segment se lit comme un état de santé client plutôt que comme une
étiquette abstraite — Champions en vert (pouls stable), Prometteurs en
ambre, À risque en orange, Perdus en gris (ligne plate). Cette
correspondance couleur/segment est appliquée uniformément aux cartes, aux
graphes Plotly et aux tableaux, pour qu'un segment se reconnaisse
visuellement d'un bout à l'autre de l'application.

Tout le système de design (palette, typographie, composants réutilisables
comme les cartes d'indicateurs ou l'en-tête animé) est centralisé dans
`core/theme.py`, importé par les deux pages — une modification de
palette ou de style s'y fait à un seul endroit.

---

## 10. Déploiement

L'application se déploie gratuitement sur **Streamlit Community Cloud** :
dépôt GitHub connecté, `Home.py` comme point d'entrée, identifiants
Upstash renseignés dans les secrets de l'app. Le scoring planifié tourne
séparément via GitHub Actions, sur le même dépôt.

---

## 11. Structure du projet

```
rfm-app/
├── Home.py                       # Page 1 — prédiction en direct
├── pages/1_Batch_Scoring.py      # Page 2 — scoring par lot + analyse
├── core/
│   ├── model_loader.py           # Charge le pipeline entraîné
│   ├── preprocessing.py          # Mapping cluster → nom de segment
│   ├── db.py                     # Client Upstash Redis
│   ├── batch_job.py              # RFM brut → scoré → Redis
│   ├── analytics.py              # Relit tous les clients scorés
│   └── theme.py                  # Système de design
├── model/rfm_pipeline.pkl        # Pipeline entraîné (généré depuis le notebook)
├── data/                         # Jeux de données d'exemple
├── scheduler.py                  # Scoring planifié, hors application
├── combine_transactions.py       # Fusionne plusieurs CSV de transactions
├── export_pipeline_snippet.py    # Code à coller dans le notebook
└── .github/workflows/
    └── scheduled_scoring.yml     # Cron GitHub Actions
```

Le détail pas-à-pas de l'installation et de la configuration se trouve
dans `README.md`.
