# Frontend AUDEX

Base React + Vite pour le MVP AUDEX. La structure est pensée pour accueillir rapidement l’upload hors-ligne, le tableau de bord et l’assistant conversationnel.

## Stack et structure

```
src/
  App.tsx                # Shell principal (upload + historique + bannières)
  main.tsx               # Point d’entrée React
  styles.css             # Styles globaux
  hooks/
    useBatchUploader.ts  # Gestion upload + synchronisation offline
    useOnlineStatus.ts   # Détection état réseau
  services/
    db.ts                # Abstraction IndexedDB (lots + fichiers)
  state/
    useBatchesStore.ts   # Store Zustand des lots
  components/
    UploadPanel.tsx      # UI de dépôt drag & drop
    BatchList.tsx        # Historique des lots
    ConnectionBanner.tsx # Notification offline/online
  types/
    batch.ts             # Types partagés (Batch, StoredFile)
index.html               # Entrée Vite (monte <App /> dans #root)
public/
  favicon.svg            # Icône AUDEX
package.json             # Scripts npm (dev/build/preview)
tsconfig*.json           # Configuration TypeScript/Vite
```

- Le projet est déclaré en mode ESM (`"type": "module"`) afin d’éviter les avertissements Vite sur l’API CJS obsolète.

## Démarrer en local

```bash
cd frontend
npm install
npm run dev
```

L’application tourne sur `http://localhost:5173`.

## Fonctionnalités actuelles
- Dépôt multi-fichiers via drag & drop et bouton explorateur.
- Stockage local des lots et fichiers dans IndexedDB (mode hors-ligne résilient).
- Synchronisation automatique à la reconnexion (`/api/v1/ingestion/batches`) + bouton manuel.
- Abonnement SSE (`/api/v1/ingestion/events`) pour suivre les statuts en temps réel.
- Historique des lots (séparé en synchronisés / en attente), téléchargement de rapport PDF et affichage du hash.

## Prochaines étapes clés
- Brancher un suivi temps réel (SSE/WebSocket) pour refléter l’analyse IA.
- Afficher l’aperçu des rapports PDF générés et leur hachage blockchain.
- Ajouter l’authentification/rôles côté client puis un design system homogène.

## Remarques d'exécution
- Lors de la première analyse, le backend initialise EasyOCR et télécharge ses poids. Cette étape peut prendre plusieurs minutes et la requête HTTP peut expirer côté navigateur ; surveillez la timeline temps réel qui reflète l’état du pipeline (étapes « Chargement du moteur OCR », « Analyse en cours », etc.).
