# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## État du projet

**`ROADMAP.md` est la source de vérité** pour l'architecture cible, la stack et le découpage en épics — le lire avant toute implémentation. Épics 1 (socle), 2 (référentiel + pipeline horaire), 3 (template Quarto), 4 (orchestration Celery), 5 (API REST) et 6 (traçabilité + MinIO) implémentés dans `backend/`.

Résumé : démo backend qui génère automatiquement des rapports PDF (hebdo/mensuel) à partir de données quotidiennes, via un pipeline asynchrone distribué (FastAPI + Celery + Redis + Quarto/Typst). Voir `ROADMAP.md` §1-2 pour le périmètre exact, §4 pour la stack et les alternatives écartées, §5 pour le schéma d'architecture, §6 pour les épics.

Le nom du dossier (`airpl-demo-drf-async-pdf`) est historique : DRF a été écarté au profit de FastAPI (`ROADMAP.md` §4, section « Alternatives écartées »).

## Structure

Monorepo `backend/` + `frontend/` (`ROADMAP.md` §4) :
- `backend/` — API FastAPI + workers Celery + tests. Toutes les commandes ci-dessous s'exécutent depuis ce dossier.
- `frontend/` — vide pour l'instant (bootstrap prévu séparément), déjà routable via Traefik.
- `data/` — sources brutes partagées, hors de `backend/` (montées en lecture seule par les workers).
- `traefik/dynamic.yml` — routage statique (provider `file`, pas `docker` : le socket Docker Desktop renvoie des réponses tronquées à Traefik sur cette machine, cf. commit de l'Épic infra).

## Commandes (depuis `backend/`)

```bash
python3 -m venv .venv && .venv/bin/python3 -m pip install -r requirements-dev.txt
.venv/bin/python3 -m ruff check .
.venv/bin/python3 -m pytest -q
```

Depuis la racine du repo :

```bash
cp backend/.env.example backend/.env   # une fois, en local
docker compose up -d --build
curl http://api.localhost/health       # via Traefik
```

Le référentiel communal (SQLite, `backend/var/db/reports.db`) est reconstruit automatiquement au démarrage de chaque worker (signal `worker_ready`, cf. `app/tasks/bootstrap.py`) — pas d'étape manuelle nécessaire.

### Orchestration des rapports (Épic 4)

Trois queues Celery dédiées, un worker Docker par queue (cf. `docker-compose.yml`) :
- `ingestion` (`worker-ingestion`) — `tasks.generate_hourly_readings`, planifiée chaque heure.
- `reports-weekly` (`worker-weekly`) — `tasks.generate_weekly_report` (7 derniers jours complets), lundi 2h.
- `reports-monthly` (`worker-monthly`) — `tasks.generate_monthly_report` (mois courant), 1er du mois 3h.

`app/tasks/reports.py` appelle `quarto` en subprocess puis déplace le PDF vers `var/reports/` avec `shutil.move` (pas un simple rename : `reports/` et `var/reports/` sont deux volumes Docker distincts, un rename direct échoue en cross-device).

### Traçabilité des rapports + stockage MinIO (Épic 6)

`app/storage.py` upload chaque PDF vers MinIO (bucket `reports`, créé à la volée par `_ensure_bucket`) via boto3, endpoint S3-compatible. Le PDF rendu localement (`var/reports/`) n'est qu'un fichier de passage : uploadé puis supprimé (`Path.unlink()`) — MinIO est la seule copie durable. En local hors Docker, `S3_ENDPOINT_URL` par défaut pointe sur `http://localhost:9000` (MinIO du compose expose ce port sur l'hôte) ; en conteneur, les workers weekly/monthly reçoivent `S3_ENDPOINT_URL=http://minio:9000` (`docker-compose.yml`).

Table `report_runs` (SQLite, cf. `app/db.py`) : un enregistrement par exécution de `generate_weekly_report`/`generate_monthly_report` — `report_type`, `period_start`/`period_end`, `status` (`success`/`failed`), `started_at`, `duration_seconds`, `storage_location` (URI `s3://bucket/clé`, pas un chemin local), `file_size_bytes`, `error_message`. Écrit par `app/reports_history.record_run()` (succès **et** échecs — l'exception est aussi re-levée pour que Celery reflète l'échec). Lecture via `list_runs()`/`get_run()`, consommées par l'API (Épic 5).

**Piège docker-compose** : le service `api` doit monter le même volume `db-data:/code/var/db` que les workers, sinon il lit une SQLite vide (chacun sa propre copie éphémère sinon). Pareil pour `S3_ENDPOINT_URL` — l'API en a besoin pour signer les URLs de téléchargement.

### API REST (Épic 5)

`app/api/reports.py` (monté sur `/reports` dans `app/main.py`) :
- `POST /reports/weekly`, `POST /reports/monthly` (`?reference_date=YYYY-MM-DD` optionnel) — déclenchement manuel, retourne `{task_id}` (202).
- `GET /reports/tasks/{task_id}` — statut Celery (`PENDING`/`SUCCESS`/`FAILURE`, résultat ou erreur).
- `GET /reports/history` (`?report_type=weekly|monthly&limit=`) — historique `report_runs`.
- `GET /reports/{run_id}/download` — URL présignée MinIO (404 si `run_id` inconnu, 409 si pas encore réussi).

Doc OpenAPI auto-générée sur `/docs`. Piège corrigé : `presigned_url_for()` signe avec `s3_public_endpoint_url` (défaut `http://localhost:9000`), **pas** `s3_endpoint_url` (`http://minio:9000` en conteneur) — signer une URL est une opération locale (pas d'appel réseau), mais `minio:9000` n'est résoluble que dans le réseau Docker ; un lien de téléchargement doit rester utilisable par un client externe.

### Rendu des rapports Quarto (Épic 3)

Quarto CLI + Typst sont installés dans l'image Docker backend (tarball CLI téléchargé dans le `Dockerfile`, Typst est bundlé par Quarto — pas de paquet système séparé). Pour rendre `backend/reports/report_template.qmd` en local, hors Docker :

```bash
# une fois : binaires hors du repo, sans sudo
curl -sL -o /tmp/quarto.tar.gz "https://github.com/quarto-dev/quarto-cli/releases/download/v1.9.38/quarto-1.9.38-macos.tar.gz"
tar -xzf /tmp/quarto.tar.gz -C "$HOME/.local/opt"   # -> $HOME/.local/opt/bin/quarto
brew install typst   # formule, pas de cask -> pas de sudo

cd backend
export PATH="$HOME/.local/opt/bin:$PATH"
export QUARTO_PYTHON="$(pwd)/.venv/bin/python3"   # sinon quarto ne trouve pas jupyter/pandas/geopandas
quarto render reports/report_template.qmd --to typst -P start_date:2026-07-16 -P end_date:2026-07-22
```

Le kernel Jupyter s'exécute avec `cwd=backend/reports/`, pas `backend/` — le template neutralise ça lui-même (ajout de `backend/` à `sys.path`, `DB_PATH`/`DATA_DIR` forcés en absolu) ; pas besoin de lancer `quarto` depuis un autre dossier.

## Données (`/data`)

Trois sources hétérogènes, sans base de données existante — tout est en fichiers plats, à joindre sur le code INSEE commune. Détail complet dans `ROADMAP.md` §3.

| Fichier | Contenu | Clé de jointure |
|---|---|---|
| `data/indice_ATMO_2026-1-1_2026-7-22_commune.csv` | Indice ATMO quotidien, 363 codes zone distincts (pas les 1228 communes — Air PDL publie par « commune représentative de zone ») | `code_zone` |
| `data/geo/communes_pays_de_la_loire.geojson` | 1228 communes Pays de la Loire (geometry + attributs admin : dept, EPCI, arrondissement), filtrées depuis georef-france-commune (Opendatasoft, **source non officielle**) | `insee_code` |
| `data/geo/epci_communes_pays_de_la_loire.csv` | 1219 communes × EPCI + population officielle (DGCL), filtré sur les 5 départements (44, 49, 53, 72, 85) | `insee` |

Points d'attention avant toute jointure :
- La couverture n'est jamais 1:1 entre les trois fichiers (363 zones ATMO vs 1228 communes géo vs 1219 lignes EPCI) — prévoir des communes sans indice ATMO plutôt que de supposer une couverture exhaustive. Le pipeline horaire (`backend/app/tasks/hourly.py`) ignore silencieusement les codes zone sans commune connue plutôt que d'échouer.
- 2 codes zone du CSV ATMO (`72287`, `72298`) ne matchent pas directement `insee_code` — probable renumérotation (commune nouvelle) à vérifier via `insee_code_actuel`.
- Le fichier geojson communal vient d'une source communautaire (Opendatasoft), pas de l'INSEE/IGN directement — acceptable pour cette démo, pas pour un usage réglementaire.
- Le référentiel communal combinant ces trois sources est matérialisé en base (table `communes`), pas rejoint à chaque génération de rapport (`ROADMAP.md` §3.4, Épic 2).

## Version control

Ce dépôt utilise GitButler (`but`), pas Git directement, pour les commits/branches/PR. Une branche dédiée par épic/session (`epic1-...`, `epic2-...`, etc.), empilées avec `but`.
