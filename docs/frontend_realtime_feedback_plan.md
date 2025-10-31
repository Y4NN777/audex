# Amélioration du suivi temps réel lors des uploads longs AUDEX

La première exécution du pipeline IA peut durer plusieurs minutes, notamment à cause du chargement initial d’EasyOCR (≈3 min entre 11:42:30 et 11:45:27). Ce délai déclenche actuellement un timeout côté frontend, et l’interface affiche « ÉCHEC » alors que le traitement continue sur le serveur. Le plan ci‑dessous vise à refléter fidèlement l’état du backend sans attendre la fin du `POST`.

## 1. Feedback backend/pipeline
- `backend/app/services/ocr_engine.py`  
  Émettre des événements timeline `ocr:warmup:start` / `ocr:warmup:complete` avant/après l’initialisation EasyOCR (via `event_bus` ou la callback `progress`). Objectif : rendre visible la phase « Chargement du moteur OCR ».
- `backend/app/services/pipeline.py`  
  Continuer les événements par fichier (`vision:start` / `vision:complete`) et ajouter un battement `analysis:status` toutes les ~30 s indiquant le fichier traité et le pourcentage courant.

## 2. Consommation SSE côté frontend
- `frontend/src/hooks/useBatchEvents.ts`  
  Garantir que l’écoute de `/ingestion/events` commence dès la création locale du lot, avant la résolution du `POST`.
- `frontend/src/hooks/useBatchUploader.ts`  
  - Lignes ~84 : créer la timeline initiale et conserver l’ID local, même si l’appel est encore en vol.  
  - Lignes ~125 : si Axios retourne `ECONNABORTED`, maintenir `status: "processing"` (et non `failed`) puis laisser les SSE / `syncBatchFromServer` finaliser l’état. Ajouter un bandeau prévenant que le serveur continue l’analyse.

## 3. Timeouts et affichage
- `frontend/src/services/api.ts`  
  Timeout par défaut à `0` (déjà modifié). Prévoir `VITE_API_TIMEOUT_MS` pour un plafond configurable (ex. 600 000 ms) et redémarrer Vite après changement.
- `frontend/src/components/TimelinePanel.tsx`  
  Afficher explicitement les étapes « Chargement du moteur OCR » et « Analyse en cours ».
- `frontend/src/components/SyncControls.tsx`  
  Ajouter une info-bulle / alerte lorsque la durée dépasse 1 min (« Pipeline toujours en cours sur le serveur »).

## 4. Réconciliation et synchronisation
- `frontend/src/hooks/useBatchHydrator.ts`  
  Réduire temporairement l’intervalle `HYDRATION` juste après la création d’un lot afin de récupérer rapidement l’état final.
- Après traitement : si `report_url` est présent, forcer `status: "completed"` dans le store et effacer les erreurs locales résiduelles.

## 5. Tests et documentation
- `frontend/README.md`  
  Documenter que la première exécution EasyOCR télécharge les poids et peut durer plusieurs minutes.
- Tests E2E  
  Ajouter un scénario Playwright simulant un traitement long pour vérifier que l’UI reste en « processing » et continue d’afficher la progression au lieu de basculer en erreur.

En implémentant ces actions, le frontend restera synchronisé avec le backend, l’utilisateur verra les étapes « Chargement OCR », « Analyse en cours », etc., et aucune erreur ne sera affichée tant que le pipeline tourne réellement.
