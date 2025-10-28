# Infrastructure AUDEX

Outils DevOps pour démarrer rapidement le MVP :

- `docker-compose.yml` : lance backend (FastAPI) + frontend (Vite) avec rechargement à chaud.
- `Dockerfile.backend` / `Dockerfile.frontend` : environnements de build reproductibles.
- `.env.example` : variables partagées (ports, URL API, placeholders blockchain).

Des pipelines CI/CD et scripts de déploiement Railway/Heroku seront ajoutés dans les prochaines itérations.

## Lancement via Docker Compose

```bash
cd infrastructure
docker compose up --build
```

Ports exposés :
- Frontend : `http://localhost:5173`
- Backend : `http://localhost:8000`

Arrêt des services :

```bash
cd infrastructure
docker compose down
```

Le `Makefile` à la racine du dépôt encapsule ces commandes (`make docker-up`, `make docker-down`) et fournit des raccourcis pour lancer le développement local.
