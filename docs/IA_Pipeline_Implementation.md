# IA-006 & IA-007 — Plan d’implémentation détaillé

Ce document synthétise les décisions prises pour l’extension IA du MVP AUDEX et décrit la feuille de route d’implémentation pour les issues **IA-006** et **IA-007**.

---

## 1. Objectifs

### IA-006 – Pipeline OCR & Vision avancé
- Remplacer les heuristiques simples par un pipeline IA capable d’extraire du texte (images, PDF, DOCX) et de détecter des anomalies visuelles.
- Produire des observations structurées (type d’anomalie, sévérité, confiance, zones détectées) et enrichir la timeline persistée.

### IA-007 – Scoring enrichi & synthèse IA
- Implémenter un moteur de scoring métier configurable (pondérations, seuils) basé sur les observations IA.
- Générer un résumé textuel et des recommandations via un LLM (vision/NLP) pour enrichir le rapport PDF et l’API.
- Persister les résultats (scores, synthèse, recommandations) pour consultation et traçabilité.

---

## 2. Architecture cible (rappel)

Les diagrammes fournis (`docs/Documentation Technique/CLASS-DIAGRAM.png`, `SEQUENCE-DIAGRAMME.png`) décrivent :
- `AuditBatch` comme agrégat offrant accès aux fichiers, aux événements de pipeline, aux résultats IA et au rapport.
- Modules IA indépendants (`OcrEngine`, `VisionDetector`, `RiskScorer`, `ReportSynthesizer`) interconnectés par la `IngestionPipeline`.
- Persistance dans SQLite au niveau MVP, puis migrable vers PostgreSQL.

Les décisions prises dans ce document respectent ces schémas pour éviter toute refonte ultérieure.

---

## 3. OCR & Vision (IA-006)

### 3.1 Choix technologiques
- **Images & photos** : EasyOCR (support CPU) avec pré-traitements OpenCV optionnels (redressement, binarisation).  
  - `pip install easyocr` (embarque PyTorch).  
  - Langues configurables via `.env` (`OCR_LANGUAGES=fr,en`).  
- **PDF / DOCX / TXT** :
  - PDF : `PyMuPDF` (texte natif) + `pdf2image` + EasyOCR pour pages scannées.  
  - DOCX : `python-docx`.  
  - TXT : lecture directe.

### 3.2 Implémentation
1. **pipelines/ocr.py**
   - Charger EasyOCR (`easyocr.Reader(lang_list)`).
   - Définir `extract_text(file_meta)` :
     - Route images → (OpenCV pré-traitement +) EasyOCR.
     - Route PDF → texte natif via `PyMuPDF` + OCR sur pages rasterisées.
     - Route DOCX → `python-docx`.
   - Retourner `OCRResult` (fichier source, texte concaténé, métriques de confiance).
   - Logging + gestion erreurs (ajout d’évènements `ocr:error` si besoin).

2. **pipelines/vision.py**
   - Intégrer YOLOv8n (`ultralytics` ou export ONNX) ; OpenCV reste utile pour tâches d’appoint (dessin de bounding boxes, détection flou/luminosité).
   - Retourner `Observation` (label normalisé, sévérité estimée, score, bounding boxes en pixels).

3. **services/pipeline.py**
   - Séparer les étapes : `vision:start/complete`, `ocr:start/complete`.
   - Persister les observations/texte : prévoir nouvelles tables `ocr_texts`, `vision_observations` ou JSON dans `ProcessingEvent` (selon granularité souhaitée).
   - Mettre à jour la timeline pour chaque fichier (`ProcessingEvent` déjà utilisé).

4. **Persistances associées**
   - Tables SQLModel :
     - `ocr_texts` (id, batch_id, file_id, text, confidence, language, created_at).
     - `observations` (id, batch_id, file_id, label, severity, confidence, bbox JSON).
   - Pour MVP : `SQLModel.metadata.create_all()` ; prévoir issue Alembic.

5. **Tests**
   - Unitaires : mocker EasyOCR/Yolo, vérifier mapping, fallback erreurs.
   - Intégration : ingestion d’un dossier `tests/data/ocr/` → vérifier texte + observations persistés.
   - Scripts Evaluation : mettre à jour `scripts/evaluate_pipeline.py` pour calculer métriques (précision, recall) sur dataset PoC.

### 3.3 Configuration
- `.env` :
  - `OCR_ENGINE=easyocr`
  - `OCR_LANGUAGES=fr,en`
  - `VISION_MODEL=ultralytics/yolov8n.pt`
- README / docs : installation PyTorch CPU, `pip install easyocr`, `pip install pymupdf pdf2image python-docx`.

---

## 4. Scoring & Synthèse IA (IA-007)

### 4.1 Moteur de scoring (`RiskScorer`)
- Entrées : observations vision (label, sévérité, confiance), texte OCR (mots clés), métadonnées EXIF (date capture, GPS).
- Pondérations & seuils dans `config/scoring.yaml` :
  - `weights` par catégorie (incendie, malveillance, hygiène, cyber, …).
  - `severity_multipliers` (mineur → 1, majeur → 1.5, critique → 2).
  - Règles bonus/malus (ex. documents périmés).
- Sorties :
  - Score global (0–100).
  - Scores par catégorie avec justification.
  - Liste des observations impactantes.
- Persistances :
  - Table `risk_scores` (batch_id PK, overall, details JSON, created_at).
  - Relation 1–1 avec `AuditBatch`.

### 4.2 Synthèse IA (LLM)
- Module `services/report_summary.py` :
  - Agrège scores, observations, texte OCR.
  - Prépare un prompt structuré et interroge **Llama 3.1 8B** via **Ollama** (service local).
  - Résultats : `summary_text`, `key_findings`, `recommendations`.
- Stockage : table `batch_reports` (batch_id, summary, findings, recommendations JSON, llm_model, created_at).
- Futures options : connector SaaS (OpenAI/Together) ou LLM vision (Donut/BLIP-2) si on traite directement les images.

### 4.3 Rapport PDF & API
- `services/report.py` génère un rapport “rich media” :
  1. **Page de garde & métadonnées**
     - Logo AUDEX, titre, date/heure, site audité, `batch_id`, responsable.
     - Hash SHA-256, versions OCR/YOLO/Scoring/LLM, statut blockchain.
  2. **Vue d’ensemble (dashboard)**
     - Score global (carte ou jauge).
     - Graphique radar/bar chart des scores par catégorie.
     - Tableau “Résultats par catégorie” (score, observations critiques, niveau de risque).
     - Résumé LLM (4–5 phrases).
  3. **Observations détaillées**
     - Cartes/tableau avec miniature ou lien média, catégorie/sévérité (icônes/couleurs), confiance, description (vision+OCR), bounding boxes (optionnel), recommandation associée.
  4. **Synthèse LLM**
     - Résumé narratif (1–2 paragraphes).
     - Points clés (liste à puce : anomalies majeures, bonnes pratiques).
     - Recommandations actionnables (liste priorisée).
  5. **Annexes OCR & métadonnées**
     - Extraits de texte OCR pertinents.
     - Métadonnées EXIF (timestamp, GPS, appareil).
     - Journal de timeline (ingestion → vision → OCR → scoring → rapport) horodaté.
  6. **Traçabilité**
     - Hash SHA-256, ID blockchain (TRACE-012).
     - Historique de génération (auteur, date, versions pipeline/LLM).
     - Clauses de responsabilité/disclaimer.
- API :
  - `GET /batches/{id}` retourne fichiers, timeline, observations, textes OCR, scoring, synthèse LLM.
  - Possibilité d’un endpoint analytique dédié si payload trop volumineux.

### 4.4 Tests
- Scoring : unitaires sur divers jeux d’observations (cas limite, pondérations).
- Synthèse LLM : tester avec mock (pas d’appel réel) pour vérifier format.
- Intégration : pipeline complet (ingestion → IA → scoring → synthèse → rapport).

---

## 5. Roadmap d’implémentation

1. **Préparation**
   - Ajouter dépendances (`easyocr`, `torch`, `pdf2image`, `python-docx`, `pyyaml`).  
   - Mettre à jour `pyproject.toml` + documentation installation (mention libs système).
   - Ajouter clés `.env` + README.

2. **IA-006**
   - Implémenter OCR/Vision + persistance `ocr_texts` / `observations`.  
   - Migrations (ou `create_all()` pour MVP).
   - Tests unitaires/intégration.  
   - Exposer résultats via API (`GET /batches/{id}`).

3. **IA-007**
   - Implémenter `RiskScorer` + config.  
   - Intégrer LLM (module synthèse avec fallback mock).  
   - Stockage (scores, résumé).  
   - Mettre à jour rapport PDF + API.  
   - Tests.

4. **Documentation & Ops**
   - `docs/` : expliquer pipeline IA, configuration, modelisation.  
   - Ajouter tickets futurs : Alembic migrations, GPU support, monitoring (temps d’inférence).

---

## 6. Points d’attention

- **Poids des dépendances** : EasyOCR tire PyTorch (~200 Mo). Prévoir image Docker dédiée ou caches (poetry/pip).  
- **Performance** : tester latence sur CPU ; si > quelques secondes par fichier, prévoir options (batching, GPU).  
- **Sécurité** : vérification queue (pas de payloads malveillants), surveillance des temps, éviter l’exécution de code via LLM (prompt injection).  
- **Fallback** : en cas d’échec OCR/Vision, pipeline doit continuer (rapport mentionnant l’erreur).
- **Traçabilité** : log des scores/LLM (modèle, date, prompt) pour conformité.

---

## 7. Prochaines étapes

1. **Démarrer IA-006** selon le plan ci-dessus (branche `feature/ia-006-ocr-vision`).  
2. **Implémenter IA-007** ensuite (`feature/ia-007-scoring-llm`).  
3. **Migrations Alembic** (issue à créer) avant d’aller plus loin (AUTH, TRACE, etc.).  
4. **Préparer dataset de test** (QA-013) pour valider précision IA.

Ce plan pourra évoluer selon feedbacks ou contraintes (GPU, cloud). Garder ce document à jour après chaque sprint IA.
