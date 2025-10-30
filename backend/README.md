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

Copier `.env.example` vers `.env` puis adapter les valeurs (chemins de stockage, CORS, secrets JWT…). Les principaux paramètres sont chargés via `pydantic-settings` :

| Clé | Description |
| --- | --- |
| `STORAGE_PATH` | Répertoire local où sont stockés les fichiers uploadés |
| `DATABASE_URL` | URL SQLAlchemy (par défaut `sqlite+aiosqlite:///./audex.db`) |
| `OCR_ENGINE` | Moteur OCR (`easyocr` par défaut, fallback `tesseract`) |
| `OCR_LANGUAGES` | Langues OCR (ex. `fr,en`) |
| `VISION_MODEL_PATH` | Modèle YOLO utilisé (`ultralytics/yolov8n.pt` recommandé) |

> Après changement des dépendances IA, relancer `pip install -e .` dans `backend/` pour installer EasyOCR, PyMuPDF, pdf2image, python-docx, etc.

## Tests

```bash
cd backend
pytest
```

- Les tests par défaut couvrent l’endpoint `/health`, l’ingestion multi-fichiers, la persistance Gemini (mockée) et le pipeline IA.
- Ajoutez vos fixtures/datasets dans `backend/tests/data/` si nécessaire.

### Tests d’intégration Gemini (optionnels)

Pour vérifier la connexion au service Gemini en conditions réelles :

```bash
export GEMINI_ENABLED=true
export GEMINI_API_KEY="xxx"
cd backend
pytest -m integration
```

Le test `tests/test_ingestion_integration.py` est automatiquement ignoré si la clé n’est pas configurée. Il génère une petite image, appelle l’API Gemini et vérifie que la réponse JSON est valide. N’exécutez cette commande que ponctuellement (coût/quota d’API).

### Warm-up EasyOCR

```bash
make warmup-ocr
```

Télécharge les poids EasyOCR nécessaires (images, PDF, DOCX) afin d’éviter un téléchargement lors du premier traitement. À lancer une fois après l’installation ou dans vos pipelines CI/CD.

## Pipeline IA (MVP)

- OCR EasyOCR + vision YOLO (`app/services/ocr_engine.py`, `app/services/vision_engine.py`) avec fallback legacy. Voir `docs/IA_Pipeline_Implementation.md` pour les détails et la calibration prévue.
- Scoring métier (`app/services/scoring.py`) persisté dans la table `risk_scores` et exposé via l’API (`BatchResponse.risk_score`).
- Analyse avancée Gemini (`app/services/advanced_analyzer.py`) + synthèse IA (`app/services/report_summary.py`). Les résumés sont stockés dans `batch_reports` et injectés dans la réponse API (`BatchResponse.summary`) ainsi que dans le PDF (`app/services/report.py`).
- Rapport PDF enrichi (score, observations locales/Gemini, synthèse IA) généré par `ReportBuilder`.

### Configuration Gemini

Ajouter dans `backend/.env` :

```
GEMINI_ENABLED=true
GEMINI_API_KEY=...
GEMINI_SUMMARY_ENABLED=true
GEMINI_SUMMARY_API_KEY=...    # peut réutiliser GEMINI_API_KEY
GEMINI_SUMMARY_REQUIRED=false
GEMINI_SUMMARY_MODEL=gemini-2.0-flash-exp
GEMINI_SUMMARY_TIMEOUT_SECONDS=30
GEMINI_SUMMARY_MAX_RETRIES=2
SUMMARY_FALLBACK_ENABLED=false
SUMMARY_FALLBACK_MODEL=ollama/llama3.1
```

Les tests unitaires moquent les appels Gemini. Pour vérifier les appels réels, lancer `pytest -m integration` (consomme des crédits Gemini).

Un script d’évaluation est fourni pour valider rapidement la boucle :

```bash
python backend/scripts/evaluate_pipeline.py --dataset data/samples
```

Le script parcourt un dossier local (images, PDF, textes) et affiche les observations, extraits OCR, scores et synthèse générés.
