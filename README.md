# Segmentation Client RFM — Web App

Application Streamlit à deux pages pour mettre en production le modèle
K-Means de segmentation RFM, avec Upstash Redis comme base clé-valeur.

- **Page 1 — Home** : prédiction en direct pour un client (formulaire
  Recency/Frequency/Monetary → segment).
- **Page 2 — Batch Scoring** : scoring par lot à la demande (upload CSV),
  dashboard du dernier run planifié, et analyse business (graphes).

---

## Design

The interface reads customer segments as vitals rather than generic KPI
tiles: a scrolling pulse line in each header, colored per-segment (green
for Champions, amber for Prometteurs, orange for À risque, grey — a
flatline — for Perdus), applied consistently across cards, charts, and
tables. Everything lives in `core/theme.py`; adjust the palette or the
ECG path there if you want to restyle it.

## Table des matières

1. [Architecture du projet](#1-architecture-du-projet)
2. [Étape 1 — Exporter le pipeline depuis le notebook](#2-étape-1--exporter-le-pipeline-depuis-le-notebook)
3. [Étape 2 — Créer la base Redis (Upstash)](#3-étape-2--créer-la-base-redis-upstash)
4. [Étape 3 — Schéma de la base Redis](#4-étape-3--schéma-de-la-base-redis)
5. [Étape 4 — Installer et configurer le projet](#5-étape-4--installer-et-configurer-le-projet)
6. [Étape 5 — Lancer l'application](#6-étape-5--lancer-lapplication)
7. [Étape 6 — Tester avec les données d'exemple](#7-étape-6--tester-avec-les-données-dexemple)
8. [Étape 7 — Configurer le scoring planifié](#8-étape-7--configurer-le-scoring-planifié)
9. [Étape 8 — Déployer en ligne](#9-étape-8--déployer-en-ligne)
10. [Dépannage](#10-dépannage)

---

## 1. Architecture du projet

```
rfm-app/
├── Home.py                          # Page 1 : prédiction en direct
├── pages/
│   └── 1_Batch_Scoring.py           # Page 2 : scoring par lot + analyse
├── core/
│   ├── model_loader.py              # Charge model/rfm_pipeline.pkl
│   ├── preprocessing.py             # Mapping cluster -> nom de segment
│   ├── db.py                        # Client Upstash Redis
│   ├── batch_job.py                 # Pipeline RFM brut -> scoré -> Redis
│   ├── analytics.py                 # Relit tous les clients scorés pour les graphes
│   └── theme.py                     # Système de design (palette, CSS, composants)
├── assets/
│   └── icon.png                     # Icône de page
├── model/
│   └── rfm_pipeline.pkl             # ⚠️ à générer (étape 1) — absent au départ
├── data/
│   ├── sample_transactions.csv      # Jeu de données d'exemple (brut)
│   └── sample_rfm_table.csv         # Même jeu, déjà agrégé en RFM
├── scheduler.py                     # Script de scoring planifié (hors app)
├── combine_transactions.py          # Fusionne plusieurs CSV de transactions en un seul
├── export_pipeline_snippet.py       # Code à coller dans le notebook
├── .github/workflows/
│   └── scheduled_scoring.yml        # Cron GitHub Actions prêt à l'emploi
├── .streamlit/
│   └── secrets.toml.example         # Modèle pour vos identifiants Upstash
└── requirements.txt
```

**Comment les pièces s'articulent :** `Home.py` et `pages/1_Batch_Scoring.py`
sont les deux pages Streamlit. Elles ne contiennent aucune logique
métier — tout est dans `core/`, réutilisé aussi par `scheduler.py`. Ainsi
le scoring "en direct", le scoring "à la demande" et le scoring
"planifié" utilisent exactement le même code et ne peuvent jamais donner
des résultats incohérents entre eux.

---

## 2. Étape 1 — Exporter le pipeline depuis le notebook

Le modèle a besoin d'un seul fichier : `model/rfm_pipeline.pkl`, un
`sklearn.pipeline.Pipeline` qui enchaîne `log1p → StandardScaler →
KMeans`. Il n'existe pas encore dans le projet.

1. Ouvrez `Segmentation_des_clients.ipynb`.
2. Repérez la cellule qui entraîne le modèle final (celle qui faisait
   `kmeans_final.fit(rfm_scaled)` puis `rfm['Cluster'] = ...`).
3. Remplacez-la par le contenu de **`export_pipeline_snippet.py`**
   (fourni à la racine du projet).
4. Exécutez la cellule. Elle doit afficher :
   ```
   Modèle entraîné ✓
   ...
   Exporté : rfm_pipeline.pkl — c'est le seul fichier dont l'app a besoin.
   ```
5. Copiez le fichier généré dans le dossier du projet :
   ```
   model/rfm_pipeline.pkl
   ```

> Les cellules suivantes du notebook (profils par cluster,
> `rfm['Nom_Cluster']`, graphiques) continuent de fonctionner normalement
> car le snippet réassigne `rfm['Cluster']` comme le faisait l'ancienne
> cellule.

---

## 3. Étape 2 — Créer la base Redis (Upstash)

1. Allez sur https://console.upstash.com/ et créez un compte (gratuit).
2. Cliquez **Create Database** → donnez-lui un nom (ex. `rfm-segmentation`)
   → choisissez une région proche de vous → **Create**.
3. Sur la page de la base, section **REST API**, notez les deux valeurs :
   - `UPSTASH_REDIS_REST_URL`
   - `UPSTASH_REDIS_REST_TOKEN`

Vous en aurez besoin à l'étape 4. Le tier gratuit suffit largement pour
un projet étudiant (10 000 commandes/jour, 256 Mo).

---

## 4. Étape 3 — Schéma de la base Redis

Upstash Redis est une base **clé-valeur** : pas de tables, pas de
schéma imposé — c'est vous qui décidez de la structure des clés et du
contenu JSON stocké dans chaque valeur. Voici le schéma utilisé par
l'app (déjà implémenté dans `core/batch_job.py` et `core/db.py`,
rien à faire ici — cette section sert de référence) :

### Clé `client:{Customer ID}` — un état par client

Une clé par client, écrasée à chaque nouveau scoring (le scoring le
plus récent fait toujours foi). C'est cette famille de clés que lit
l'onglet **Analyse business** de la page 2.

```
Clé   : client:10023
Valeur (JSON) :
{
  "recency": 12.0,
  "frequency": 18.0,
  "monetary": 2450.75,
  "cluster": 0,
  "label": "Champions",
  "scored_at": "2026-08-10T14:32:00.123456"
}
```

| Champ | Type | Description |
|---|---|---|
| `recency` | float | Jours depuis le dernier achat |
| `frequency` | float | Nombre de factures distinctes |
| `monetary` | float | Montant total dépensé (€) |
| `cluster` | int | Index du cluster K-Means (0-3) |
| `label` | string | Nom métier du segment (Champions, Perdus, À risque, Prometteurs) |
| `scored_at` | string (ISO 8601, UTC) | Horodatage du scoring |

### Clé `batch:last_run` — métadonnées du dernier lot

Une seule clé, écrasée à chaque run (à la demande ou planifié). Lue par
l'onglet **Dernier run planifié** de la page 2.

```
Clé   : batch:last_run
Valeur (JSON) :
{
  "run_at": "2026-08-10T03:00:00.000000",
  "n_clients": 160,
  "segment_counts": {
    "Champions": 40,
    "Prometteurs": 38,
    "À risque": 41,
    "Perdus": 41
  },
  "source": "scheduled"
}
```

| Champ | Type | Description |
|---|---|---|
| `run_at` | string (ISO 8601, UTC) | Horodatage du run |
| `n_clients` | int | Nombre de clients scorés dans ce run |
| `segment_counts` | object | Nombre de clients par segment |
| `source` | string | `"scheduled"` (cron/GitHub Actions) ou `"upload"` (page 2, à la demande) |

### Pourquoi ce schéma ?

- **Un client = une clé** plutôt qu'une seule grosse liste : permet de
  lire/mettre à jour un client précis en une opération, et de faire un
  `client:*` (KEYS) pour reconstituer une vue d'ensemble à la volée sans
  maintenir un index séparé.
- **Écrasement plutôt qu'historique** : chaque clé ne garde que le
  dernier état connu. C'est volontairement simple pour ce projet — si
  vous avez besoin d'historiser les scores dans le temps (ex. suivre
  l'évolution du segment d'un client sur 6 mois), il faudrait passer à
  une clé par run (`client:10023:2026-08-10`) ou à une structure Redis
  de type liste/stream (`XADD`) plutôt que `SET`.
- **JSON en valeur** : Redis stocke des chaînes de caractères ; on
  sérialise/désérialise en JSON (`json.dumps`/`json.loads`) plutôt que
  d'utiliser des hash Redis (`HSET`) — plus simple à faire évoluer
  (ajouter un champ ne casse rien) au prix d'un léger surcoût réseau.

### Limite à connaître

`core/analytics.py` utilise `KEYS client:*` puis `MGET` pour tout
relire d'un coup — parfait pour ce projet (dizaines/centaines de
clients). Sur un vrai volume (dizaines de milliers de clients), `KEYS`
peut bloquer la base : il faudrait migrer vers `SCAN` avec curseur.

---

## 5. Étape 4 — Installer et configurer le projet

1. **Installer les dépendances**
   ```bash
   cd rfm-app
   pip install -r requirements.txt
   ```

2. **Configurer les identifiants Upstash**
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
   Ouvrez `.streamlit/secrets.toml` et collez vos deux valeurs de
   l'étape 2 :
   ```toml
   UPSTASH_REDIS_REST_URL = "https://xxxx.upstash.io"
   UPSTASH_REDIS_REST_TOKEN = "xxxxx"
   ```

3. **Vérifier que le modèle est bien en place**
   ```
   model/rfm_pipeline.pkl   ← doit exister (étape 1)
   ```

---

## 6. Étape 5 — Lancer l'application

```bash
streamlit run Home.py
```

Streamlit ouvre automatiquement votre navigateur. La page 2 apparaît
dans le menu latéral (détectée automatiquement depuis `pages/`).

---

## 7. Étape 6 — Tester avec les données d'exemple

Pour voir l'app fonctionner sans attendre vos vraies données :

1. Allez sur la **Page 2 → onglet "Lancer un scoring"**.
2. Importez `data/sample_transactions.csv` (160 clients synthétiques,
   4 profils Champions/Prometteurs/À risque/Perdus).
3. Le scoring s'exécute, les résultats s'affichent, et sont sauvegardés
   dans Redis.
4. Allez sur l'**onglet "Analyse business"** pour voir les graphes se
   remplir (répartition par segment, part du revenu, boxplots RFM,
   scatter Fréquence/Montant, profils moyens).

`data/sample_rfm_table.csv` contient le même jeu de données déjà
agrégé en RFM (Customer ID, Recency, Frequency, Monetary), utile pour
vérifier le calcul dans Excel/pandas sans repasser par l'app.

---

## 8. Étape 7 — Configurer le scoring planifié

Streamlit ne peut pas exécuter de tâche de fond fiable : le "planifié"
se fait via `scheduler.py`, un script indépendant à lancer en dehors de
l'app.

```bash
python scheduler.py data/sample_transactions.csv
```

Ce script écrase `batch:last_run` et chaque `client:{id}` dans Redis —
l'onglet **Dernier run planifié** de la page 2 affichera toujours l'état
le plus récent.

Si vos transactions arrivent réparties dans plusieurs fichiers (un export
par jour, par magasin, etc.), fusionnez-les d'abord avec
`combine_transactions.py` avant de lancer `scheduler.py` :

```bash
python combine_transactions.py data data/combined_transactions.csv
python scheduler.py data/combined_transactions.csv
```

Il ne combine que les CSV qui ont le schéma de transactions brutes
(`Customer ID`, `Invoice`, `InvoiceDate`, `Quantity`, `Price`) — un
fichier comme `sample_rfm_table.csv`, déjà agrégé, est ignoré
automatiquement.

Trois façons de l'automatiser :

- **Cron (Linux/Mac)** : `crontab -e`, puis par exemple pour un run
  quotidien à 3h :
  ```
  0 3 * * * cd /chemin/vers/rfm-app && /usr/bin/python3 combine_transactions.py data data/combined_transactions.csv && /usr/bin/python3 scheduler.py data/combined_transactions.csv
  ```
- **Task Scheduler (Windows)** : créez une tâche qui exécute
  `python combine_transactions.py data data\combined_transactions.csv && python scheduler.py data\combined_transactions.csv`
  avec le dossier du projet comme répertoire de démarrage.
- **GitHub Actions** (déjà configuré) : `.github/workflows/scheduled_scoring.yml`
  tourne chaque jour à 3h UTC, avec un step `combine_transactions.py`
  avant le scoring. Il faut :
  1. Pousser le projet sur un dépôt GitHub.
  2. Dans *Settings → Secrets and variables → Actions*, ajouter
     `UPSTASH_REDIS_REST_URL` et `UPSTASH_REDIS_REST_TOKEN`.
  3. Adapter `source_dir` dans le step "Combine transaction files" vers
     l'emplacement réel de vos données (dossier du repo, ou téléchargé
     depuis S3/une base avant ce step).

---

## 9. Étape 8 — Déployer en ligne

1. Poussez le projet sur GitHub (le dossier `model/` avec
   `rfm_pipeline.pkl` inclus — ou téléchargez-le au démarrage si vous
   préférez ne pas versionner de binaire).
2. Allez sur https://share.streamlit.io/ → **New app** → sélectionnez
   le repo, branche, et `Home.py` comme point d'entrée.
3. Dans **App settings → Secrets**, collez :
   ```toml
   UPSTASH_REDIS_REST_URL = "https://xxxx.upstash.io"
   UPSTASH_REDIS_REST_TOKEN = "xxxxx"
   ```
4. Déployez — la page 2 (`pages/1_Batch_Scoring.py`) est détectée
   automatiquement.

---

## 10. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `FileNotFoundError: model/rfm_pipeline.pkl not found` | Étape 1 non faite | Exécutez `export_pipeline_snippet.py` dans le notebook et copiez le fichier généré |
| `RuntimeError: Missing Upstash credentials` | Étape 4.2 non faite / mal faite | Vérifiez `.streamlit/secrets.toml` (local) ou *App settings → Secrets* (Streamlit Cloud) |
| `KeyError: 'Cluster'` dans le notebook | La cellule d'entraînement a été remplacée sans réassigner `rfm['Cluster']` | Vérifiez que votre cellule contient bien `rfm['Cluster'] = rfm_pipeline.named_steps["kmeans"].labels_` |
| `ValueError: Input CSV is missing required columns` | Le CSV importé n'a pas les bonnes colonnes | Colonnes attendues : `Customer ID`, `Invoice`, `InvoiceDate`, `Quantity`, `Price` (voir `data/sample_transactions.csv`) |
| Onglet "Analyse business" vide | Aucun client scoré dans Redis pour l'instant | Lancez un scoring (onglet "Lancer un scoring") ou `scheduler.py` au moins une fois |
| Segments incohérents / labels qui ne correspondent plus | `rfm_pipeline.pkl` ré-exporté après un changement dans le notebook | Les index de cluster (0-3) peuvent changer si vous ré-entraînez sur des données différentes — vérifiez le mapping dans `core/preprocessing.py` (`CLUSTER_LABELS`) contre les profils affichés dans le notebook |
