## AUDEX — Plateforme d’audit intelligent

AUDEX est une application web qui automatise l’analyse d’audits de sûreté pour des sites sensibles. Le système intègre vision par ordinateur, traitement de texte et règles métier afin de produire en quelques minutes des rapports structurés et traçables.

---

### Objectifs techniques
- Ingestion unifiée de médias terrain (photos, vidéos, notes, plans, logs légers).
- Classification IA des anomalies (Incendie, Malveillance, Hygiène, Cyber) et calcul de scores de risque.
- Génération automatique d’un rapport PDF enrichi et d’une cartographie interactive.
- Assistance conversationnelle pour interroger les résultats en langage naturel.
- Traçabilité des rapports via hachage cryptographique et ancrage blockchain.
- Fonctionnement résilient en faible connectivité grâce à un mode semi-hors-ligne.

---

### Architecture cible (MVP)
- **Frontend** : React + Vite, IndexedDB pour le cache local, mise en page responsive, visualisations via Leaflet/Folium et composants graphiques.
- **Backend** : FastAPI (Python) exposant des services REST pour ingestion, analyse, scoring, rapports et authentification.
- **Pipeline IA** : modules indépendants pour OCR (Tesseract), vision (OpenCV), NLP léger, scikit-learn pour le scoring.
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
4. **Cartographie** : projection géolocalisée, heatmap et filtres par catégorie/sevérité.
5. **Assistant** : interface chat, requêtes naturelles sur les résultats, rappels de méthodologie.
6. **Traçabilité** : hachage, ancrage blockchain, vérification d’intégrité à la consultation.
7. **Administration** : gestion des audits, utilisateurs, rôles, historiques.

---

### Structure du dépôt
```
.
├── docs/
│   ├── Documentation General/     # Vision, SRS, PoC (PDF)
│   └── Documentation Technique/   # Architecture, diagrammes
└── README.md
```

> **Note** : le code applicatif sera introduit dans des répertoires `frontend/`, `backend/` et `infrastructure/` lors des prochaines étapes.

---

### Roadmap technique (résumé)
- **MVP** : pipeline complet d’analyse, rapport automatique, UI React offline-first, authentification JWT/RBAC, ancrage blockchain basique.
- **Pilote** : synchronisation différée, analyse approfondie de logs IT, API d’intégration partenaires, tests utilisateurs.
- **Production** : version mobile, monitoring/observabilité, migrations vers PostgreSQL et stockage objet, durcissement sécurité.

---

### Démarrage (prévisionnel)
1. Préparer un environnement Python 3.11 et Node.js 20.
2. Créer un `.env` backend contenant les secrets (JWT, clés blockchain).
3. Lancer les services (scripts `make` ou `docker compose` seront fournis).
4. Importer un jeu de test d’audit pour valider le pipeline de bout en bout.

Les instructions précises seront ajoutées au fur et à mesure de l’implémentation.

---

### Collaboration
- Respecter les schémas d’architecture définis dans la documentation.
- Ajouter des tests unitaires et d’intégration pour chaque module clef.
- Documenter les API avec OpenAPI/Swagger.
- Suivre un style de commit conventionnel (`feat`, `fix`, `docs`, etc.).

Pour tout complément de contexte, consulter les dossiers `docs/`.
