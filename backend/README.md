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

- Les tests existants couvrent l’endpoint `/health`, l’ingestion multi-fichiers et le pipeline IA de base.
- Ajoutez vos fixtures/datasets dans `backend/tests/data/` si nécessaire.

## Pipeline IA (MVP stub)

Les composants OCR/Vision résident dans `app/pipelines/`. Lorsque `pytesseract` ou OpenCV ne sont pas disponibles, des heuristiques de repli renvoient néanmoins des observations structurées. Un service de scoring (`app/services/scoring.py`) agrège ensuite les observations pour produire un score de risque normalisé. Enfin, `app/services/report.py` génère un PDF minimal (ReportLab) incluant le score et la liste des anomalies.

Un script d’évaluation est fourni pour valider rapidement la boucle :

```bash
python backend/scripts/evaluate_pipeline.py --dataset data/samples
```

Le script parcourt un dossier local (images, PDF, textes) et affiche les observations et extraits OCR générés.
