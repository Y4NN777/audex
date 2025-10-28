SHELL := /bin/bash

PYTHON ?= python3
BACKEND_DIR := backend
FRONTEND_DIR := frontend

BACKEND_VENV := $(BACKEND_DIR)/.venv
BACKEND_ACTIVATE := source .venv/bin/activate

.PHONY: install-backend install-frontend install-fix-frontend dev-backend dev-frontend test-backend docker-up docker-down clean-backend-venv

$(BACKEND_VENV):
	cd $(BACKEND_DIR) && $(PYTHON) -m venv .venv

install-backend: $(BACKEND_VENV)
	cd $(BACKEND_DIR) && $(BACKEND_ACTIVATE) && pip install --upgrade pip
	cd $(BACKEND_DIR) && $(BACKEND_ACTIVATE) && pip install -e .[dev]

install-frontend:
	cd $(FRONTEND_DIR) && npm install

deps-fix-frontend:
	cd $(FRONTEND_DIR) && npm audit fix

deps-fix-frontend-offline:
	cd $(FRONTEND_DIR) && npm audit fix --offline

dev-backend:
	cd $(BACKEND_DIR) && $(BACKEND_ACTIVATE) && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd $(FRONTEND_DIR) && npm run dev

test-backend:
	cd $(BACKEND_DIR) && $(BACKEND_ACTIVATE) && pytest

docker-up:
	cd infrastructure && docker compose up --build

docker-down:
	cd infrastructure && docker compose down

clean-backend-venv:
	rm -rf $(BACKEND_VENV)
