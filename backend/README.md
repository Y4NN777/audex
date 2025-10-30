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

## Pipeline IA (MVP en cours d’enrichissement)

- Les composants OCR/Vision sont désormais accessibles via `app/services/ocr_engine.py` et `app/services/vision_engine.py`, ce qui prépare l’intégration d’EasyOCR et de YOLO (voir `docs/IA_Pipeline_Implementation.md`).
- Tant que les modules avancés ne sont pas branchés, le backend utilise encore les heuristiques de repli (`pytesseract` + OpenCV) pour garantir une pipeline fonctionnelle.
- Le service de scoring (`app/services/scoring.py`) calcule un score de risque et la génération de rapport (`app/services/report.py`) produit un PDF minimal.

Un script d’évaluation est fourni pour valider rapidement la boucle :

```bash
python backend/scripts/evaluate_pipeline.py --dataset data/samples
```

Le script parcourt un dossier local (images, PDF, textes) et affiche les observations et extraits OCR générés.
