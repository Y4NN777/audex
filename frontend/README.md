# Frontend AUDEX

Base React + Vite pour le MVP AUDEX. La structure est pensée pour accueillir rapidement l’upload hors-ligne, le tableau de bord et l’assistant conversationnel.

## Stack et structure

```
src/
  App.tsx         # Shell UI provisoire avec liste de lots
  main.tsx        # Point d’entrée React
  styles.css      # Style global minimal (à remplacer par design system)
index.html        # Entrée Vite (monte <App /> dans #root)
public/
  favicon.svg     # Icône AUDEX
package.json      # Scripts npm (dev/build/preview)
tsconfig*.json    # Configuration TypeScript/Vite
```

- Le projet est déclaré en mode ESM (`"type": "module"`) afin d’éviter les avertissements Vite sur l’API CJS obsolète.

## Démarrer en local

```bash
cd frontend
npm install
npm run dev
```

L’application tourne sur `http://localhost:5173`. Le shell affiche des lots simulés et une checklist des prochaines étapes (upload multi-fichiers, liaison API, temps réel).

## Prochaines étapes clés
- Ajouter la couche IndexedDB + synchronisation différée (React Query ou Zustand).
- Implémenter le composant d’upload avec gestion offline/online.
- Connecter l’API FastAPI (`/api/v1/ingestion/batches`) et gérer le suivi de pipeline.
- Introduire un système de design (Tailwind, Mantine, MUI…) pour harmoniser l’interface.
