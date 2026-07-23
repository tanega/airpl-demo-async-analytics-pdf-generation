# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## État du projet

**`ROADMAP.md` est la source de vérité** pour l'architecture cible, la stack et le découpage en épics — le lire avant toute implémentation. Épics 1 (socle) et 2 (référentiel + pipeline horaire) implémentés dans `backend/`.

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
