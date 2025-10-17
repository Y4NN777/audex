# AGENTS

Document de coordination pour le développement de l’itération MVP d’AUDEX.

---

## 1. Rôles et responsabilités

- **Product Owner – Yanis**  
  Définit la vision produit, priorise les fonctionnalités et valide les livrables.

- **Tech Lead / IA & Backend – Assistant (Codex)**  
  Conçoit l’architecture, supervise les pipelines IA et le backend FastAPI, arbitre les choix techniques.

- **Frontend Lead**  
  Met en place l’application React, l’IndexedDB offline-first et les visualisations (rapport, carte, assistant).

- **Engineer IA/ML**  
  Entraîne et évalue les modèles OCR/vision/scoring, prépare les jeux d’entraînement, mesure les performances.

- **Engineer Backend & Sécurité**  
  Implémente l’ingestion, l’API, l’authentification JWT/RBAC, la traçabilité blockchain et les tests d’intégration.

- **DevOps / Infrastructure**  
  Prépare les environnements, scripts Docker/Compose, pipelines CI, déploiements Railway/Heroku.

- **QA / Validation**  
  Construit les plans de test, automatise les scénarios E2E, orchestre la démonstration MVP.

Un même membre peut occuper plusieurs rôles selon la capacité disponible.

---

## 2. Backlog MVP (priorité décroissante)

1. **Infrastructure & Qualité**
   - Initialiser structures `frontend/`, `backend/`, `infrastructure/`.
   - Créer gabarits Docker, scripts Makefile, configuration préliminaire CI.
   - Définir conventions de code, linting, formatage.

2. **Ingestion & Validation**
   - Endpoints upload FastAPI, stockage temporaire, extraction métadonnées.
   - Gestion des lots, validation des formats (images, PDF, notes, logs).

3. **Pipeline IA**
   - Modules OCR (Tesseract) et vision (OpenCV) pour détecter anomalies clés.
   - Scoring (scikit-learn/heuristiques) avec calibration manuelle.
   - Jeux de données d’entraînement et scripts d’évaluation.

4. **Génération de rapport**
   - Service de synthèse (tableaux, KPIs, recommandations).
   - Export PDF (WeasyPrint/ReportLab) + génération carte (Folium/Leaflet).

5. **Frontend Offline-first**
   - UX de dépôt fichiers et suivi d’analyse.
   - Tableau de bord, visualisation cartographique, lecture rapport.
   - IndexedDB pour cache et reprise partielle, mode dégradé faible connexion.

6. **Authentification & RBAC**
   - API Auth (inscription restreinte, login), gestion de rôles (Auditeur, Supervisieur, Admin, Lecteur).
   - Protections JWT (refresh, expiration), audit log minimal.

7. **Traçabilité Blockchain**
   - Hachage rapport (SHA-256), ancrage testnet via Web3.py.
   - Endpoint de vérification d’intégrité.

8. **Assistant Conversationnel**
   - Endpoint Q&A (LLM ou règles) basé sur rapport structuré.
   - Interface chat dans le frontend, historique local.

9. **Tests & Préparation Démo**
   - Jeux de données démonstration, script end-to-end.
   - Automatisation tests (pytest, Playwright/Cypress).
   - Scénario de présentation et check-list qualité.

---

## 3. Cadence & rituels

- **Daily** (15 min) : avancement, blocages, priorités du jour.
- **Sprint Review** (fin de séquence) : démonstration des fonctionnalités MVP livrées.
- **Retro courte** : identifier ce qui peut être amélioré sur les prochains lots.
- Outils recommandés : Trello/Linear pour suivi tâches, Google Meet/Discord pour synchronisation.

---

## 4. Flux de travail

1. Créer une issue pour chaque tâche prioritaire (décrivant contexte, objectif, critères d’acceptation).
2. Brancher selon la convention `feature/<module>-<courte-description>`.
3. Assurance qualité : tests locaux, lint, capture de résultats.
4. Pull request avec description claire et références aux issues.
5. Review croisée (minimum 1 approbation) avant merge sur `main`.

---

## 5. Livrables attendus par rôle

- **Frontend** : interface upload, tableau de bord, carte, chat, packaging offline.
- **Backend/IA** : API FastAPI, pipeline IA, génération rapport PDF, endpoints blockchain.
- **DevOps** : scripts de lancement (Docker Compose), environnements `.env.example`, pipeline CI.
- **QA** : suites de tests automatisés + guide de démo chronométrée.

---

## 6. Références

- `README.md` : vision technique et architecture.
- `docs/Documentation Technique/` : diagrammes et design détaillés.
- `docs/Documentation General/` : contexte produit, SRS, PoC.

Ce document sera mis à jour au fil de l’avancement pour refléter les décisions d’équipe et l’état du backlog.
