SHELL := /bin/bash

.PHONY: install test run lint

install:
	pip install -e .[dev]

test:
	pytest

venv-activate:
	source .venv/bin/activate

run:
	uvicorn app.main:app --reload --port 8000

lint:
	ruff check app tests
