# Backend AUDEX

Squelette FastAPI pour le MVP AUDEX. L’objectif est de fournir rapidement des endpoints d’ingestion, d’analyse et de génération de rapports tout en restant modulable.

## Structure

```
app/
  api/
    v1/
      endpoints/    # Contrôleurs versionnés (ingestion, auth, etc.)
      routes.py     # Regroupe les routers
  core/             # Configuration et constantes
  services/         # Logique métier (pipelines IA, scoring…)
  models/           # Modèles ORM à venir
  schemas/          # Schémas Pydantic (I/O API)
  main.py           # Factory FastAPI + endpoint health
tests/              # Pytest (inclut smoke tests ASGI)
pyproject.toml      # Dépendances et outils (FastAPI, Ruff…)
```

## Démarrage rapide

```bash
make install-backend  # crée backend/.venv et installe les deps
make dev-backend      # lance uvicorn via le virtualenv
```

Depuis le dossier `backend/`, un `Makefile` local propose également :

```bash
cd backend
source .venv/bin/activate  # activer l'environnement virtuel si nécessaire
make test                  # lance pytest
make run                   # démarre uvicorn en local
```

L’API est exposée sur `http://localhost:8000`. La documentation interactive est disponible sur `http://localhost:8000/api/docs`. Pour supprimer l’environnement virtuel créé automatiquement : `make clean-backend-venv`.

## Variables d’environnement

Copier `.env.example` vers `.env` puis adapter les valeurs (chemins de stockage, CORS, secrets JWT…). Les paramètres sont chargés via `pydantic-settings`.

## Tests

```bash
cd backend
pytest
```

Le test de santé (`/health`) vérifie que l’application démarre correctement. De nouveaux tests seront ajoutés à mesure que les services (ingestion, IA, rapport) s’implémentent.
