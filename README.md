## AUDEX — Plateforme d’audit intelligent

AUDEX est une application web qui automatise l’analyse d’audits de sûreté pour des sites sensibles. Le système intègre vision par ordinateur, traitement de texte, LLM de vision et règles métier afin de produire en quelques minutes des rapports structurés et traçables.


<img width="1457" height="959" alt="image" src="https://github.com/user-attachments/assets/c0170c07-4e09-4d73-a808-fe435d19f851" />
<img width="1457" height="959" alt="image" src="https://github.com/user-attachments/assets/3b9d2189-347c-4af1-89f9-4893be75042d" />




---

### Objectifs techniques
- Ingestion unifiée de médias terrain (photos, vidéos, notes, plans, logs légers).
- Classification IA des anomalies (Incendie, Malveillance, Hygiène, Cyber) et calcul de scores de risque.
- Génération automatique d’un rapport PDF enrichi et d’une cartographie interactive.
- Assistance conversationnelle pour interroger les résultats en langage naturel.
- Traçabilité des rapports via hachage cryptographique et ancrage blockchain.
- Fonctionnement résilient en faible connectivité grâce à un mode semi-hors-ligne.

---

### Architecture cible v1.1
- **Frontend** : React + Vite, IndexedDB pour le cache local, mise en page responsive, visualisations via Leaflet/Folium et composants graphiques.
- **Backend** : FastAPI (Python) exposant des services REST pour ingestion, analyse, scoring, rapports et authentification.
- **Pipeline IA** : modules indépendants pour OCR (EasyOCR via PyTorch), vision (YOLOv8 + Multimodal LLM Gemini 2.0-Flash) , synthèse LLM (Llama 3.1 via Ollama ou Gemini 2.0-Flash) et moteur de scoring métier.
- **Persistance** : SQLite embarqué pour le MVP (passage planifié à PostgreSQL), stockage de médias sur filesystem local ou objet.
- **Traçabilité** : hachage SHA-256 des rapports, Web3.py pour ancrage sur réseau blockchain (testnet).
- **Sécurité** : JWT pour l’authentification, RBAC, chiffrement AES des caches sensibles, validation stricte des uploads.
- **Déploiement** : containerisation Docker, orchestrée sur Railway/Heroku, HTTPS obligatoire.

Le document `docs/Documentation Technique/Audex_Architecture_Technique_et_Conception.pdf` décrit les diagrammes détaillés (cas d’usage, séquence, classes).

---

### Modules fonctionnels
1. **Ingestion & validation** : upload multi-fichiers, extraction de métadonnées, contrôles de cohérence.
2. **Analyse IA** : OCR, détection d’objets, extraction de texte structuré, scoring de risque.
3. **Générateur de rapport** : compilation des anomalies, recommandations, synthèse graphique, export PDF.
4. **Traçabilité** : hachage d'audit et de lots

### Modules non fonctionnels au partiellement implementé
1. **Cartographie** : projection géolocalisée, heatmap et filtres par catégorie/sevérité.
3. **Assistant Conversationnel** : interface chat, requêtes naturelles sur les résultats, rappels de méthodologie.
4. **Traçabilité** : ancrage blockchain, vérification d’intégrité à la consultation.
5. **Administration** : gestion des audits, utilisateurs, rôles, historiques.

---

### Structure du dépôt
```
.
├── docs/
│   ├── Documentation General/     # Vision, SRS, PoC (PDF)
│   └── Documentation Technique/   # Architecture, diagrammes
├── backend/                       # API FastAPI (pyproject, app/, tests/)
├── frontend/                      # UI React (Vite, TypeScript)
├── infrastructure/                # Dockerfiles, docker-compose
├── Makefile                       # Raccourcis (install, dev, docker-up/down)
└── README.md                      # Ce README    
```

> **Note** : les dossiers applicatifs contiennent désormais un squelette fonctionnel (FastAPI + React) pour accélérer la construction du MVP.

---

### Roadmap technique (résumé)
- **MVP** : pipeline complet d’analyse, rapport automatique, UI React offline-first.
- **Pilote** : administration, ancrage blockchain avancé, assistant conversationnel, cartographie, synchronisation différée, analyse approfondie de logs IT, API d’intégration partenaires, tests utilisateurs.
- **Production** : version mobile, monitoring/observabilité, migrations vers PostgreSQL et stockage objet, durcissement sécurité.

---

### Démarrage rapide
1. **Backend**
   ```bash
   make install-backend
   make dev-backend
   ```
   `make install-backend` crée automatiquement un virtualenv (`backend/.venv`) puis installe les dépendances. L’API tourne sur `http://localhost:8000` avec endpoint `/health` et docs Swagger (`/api/docs`).

2. **Frontend**
   ```bash
   make install-frontend
   make dev-frontend
   ```
   L’interface shell est servie sur `http://localhost:5173` et préfigure les écrans d’upload/suivi.

3. **Docker (optionnel)**
   ```bash
   make docker-up
   ```
   Compose lance backend + frontend dans deux conteneurs. `make docker-down` pour arrêter.

4. **Variables d’environnement**
   - Copier `backend/.env.example` vers `backend/.env` et renseigner les secrets.
   - Configurer les clés IA : `OCR_ENGINE=easyocr`, `OCR_LANGUAGES=fr,en`, `VISION_MODEL_PATH=ultralytics/yolov8n.pt` (modifiable selon vos modèles).
   - Adapter `infrastructure/.env.example` pour définir ports/API URL et placeholders blockchain.

5. **Prochaines étapes**
   - Finaliser la pipeline IA avancée et le rapport PDF enrichi (IA-006, IA-007, REPORT-008). Voir `docs/IA_Pipeline_Implementation.md` pour le plan détaillé.
   - Brancher IndexedDB/offline et liaisons API côté React (FRONT-009, FRONT-010).

---

### Collaboration
- Respecter les schémas d’architecture définis dans la documentation.
- Ajouter des tests unitaires et d’intégration pour chaque module clef.
- Documenter les API avec OpenAPI/Swagger.
- Suivre un style de commit conventionnel (`feat`, `fix`, `docs`, etc.).

Pour tout complément de contexte, consulter les dossiers `docs/`.
