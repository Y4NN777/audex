# Plan d'amélioration pipeline & Gemini

## Objectifs
- **Réponse API rapide** : libérer `POST /ingestion/batches` dès que les fichiers sont enregistrés.
- **Suivi temps réel fiable** : permettre aux SSE/mécanismes UI de refléter chaque étape du pipeline sans attendre la fin du traitement.
- **Gestion intelligente des quotas Gemini** : exploiter `retry_delay` pour espacer les relances et respecter la limite de 10 minutes par analyse.

## 1. Déclencher le pipeline en tâche de fond

### Ajustements endpoint `POST /ingestion/batches`
1. Persister les fichiers & métadonnées (comportement actuel).
2. Répondre immédiatement (ex. `202 Accepted` ou `200` avec `{"batchId": ..., "status": "processing"}`).
3. Lancer le pipeline dans une tâche asynchrone :
   ```python
   asyncio.create_task(run_pipeline_async(batch_id, stored_files, storage_root))
   ```
4. `run_pipeline_async` reprend l’implémentation actuelle de `IngestionPipeline.run`, publie les événements SSE et met à jour la base.

### Conséquences sur les services
- `IngestionPipeline.run` reste synchrone ; la tâche d’arrière-plan l’exécute et gère les exceptions pour publier `pipeline:error`.
- Le bus d’événements (`event_bus.publish`) fonctionne immédiatement, les abonnés reçoivent les étapes en temps réel.
- **Frontend à aligner** :
  - `useBatchUploader` / `UploadPanel` doivent traiter le `202 Accepted` comme fin d’upload (barre “Transmis” dès `ingestion:received`).
  - `useBatchEvents`, `BatchSection`, `SyncControls` continuent à consommer les SSE pour afficher la progression et les statuts mis à jour.
  - Aucun objet timeline n’est retourné dans la réponse initiale ; l’UI ne doit plus dépendre du payload du POST pour afficher l’état.
- Frontend :
  - la promesse `submitFiles` peut se résoudre dès la réponse initiale (fichiers marqués “Transmis” grâce à l’évènement `ingestion:received`).
  - la carte lot passe en “Analyse en cours” aussitôt.

## 2. Retry Gemini basé sur `retry_delay`

### Implémentation
1. Dans `AdvancedAnalyzer._call_gemini`, intercepter les exceptions 429 (`ResourceExhausted` ou `GoogleAPIError`).
2. Parser le champ `retry_delay` (JSON) pour récupérer le nombre de secondes recommandé.
3. `await asyncio.sleep(delay)` avant la prochaine tentative, avec un garde-fou si le délai dépasse le temps restant (limite 10 min).
4. Journaliser et collecter un warning `gemini-quota-exceeded` afin d’afficher l’information dans la timeline.
5. Si toutes les tentatives échouent, renvoyer un statut `quota_exceeded` sans bloquer indéfiniment l’analyse.

### Sécurité
- Ajout d’un timeout global (ex. `settings.GEMINI_TIMEOUT_SECONDS_TOTAL`) pour arrêter proprement le pipeline si l’attente cumulée dépasse la limite.
- Possibilité de fallback (désactivation automatique de Gemini) en cas de quota non récupérable.

## 3. Garanties de compatibilité
- Aucun changement de schéma ni de modèle ; les nouveaux flux réutilisent les repos existants (`batch_repo.*`).
- Les évènements SSE utilisent toujours la même structure (`stage`, `batchId`, …).
- Les tests existants (ingestion, pipeline) restent valides ; créer un test pour vérifier que le POST renvoie bien immédiatement.
- Documenter dans `backend/README.md` que le pipeline tourne désormais en tâche de fond et que les clients doivent s’appuyer sur SSE ou `GET /batches/{id}` pour connaître l’état.

## 4. Étapes d’implémentation recommandées
1. Refactor `create_batch` pour répondre rapidement et lancer la tâche asynchrone.
2. Adapter `useBatchUploader` côté frontend pour considérer la réponse initiale comme “succès upload”.
3. Implémenter l’extraction de `retry_delay` dans `AdvancedAnalyzer` et ajuster les logs/warnings.
4. Tester : upload d’un lot → vérifier que :
   - la promesse client se résout instantanément ;
   - les vignettes passent en “Transmis” via `ingestion:received` ;
   - la timeline affiche toutes les étapes ;
   - les erreurs Gemini sont espacées selon le délai recommandé.

Ce plan conserve l’architecture actuelle tout en éliminant les blocages, ce qui garantit un comportement plus réactif et conforme aux contraintes (≤ 10 min, respect des quotas).***
