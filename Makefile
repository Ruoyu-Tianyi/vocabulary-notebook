PYTHON ?= .venv/bin/python
NPM ?= npm
NODE ?= node

.PHONY: help check check-backend check-frontend check-desktop lint test build

help:
	@echo "make check          Run backend, frontend and desktop checks; build frontend/dist"
	@echo "make lint           Run Python and JavaScript static checks"
	@echo "make test           Run isolated backend and frontend tests"
	@echo "make build          Rebuild the frontend served by python app.py"
	@echo "Override PYTHON=python if your environment is already activated."

check: check-backend check-frontend check-desktop

check-backend:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m pytest -q

check-frontend:
	$(NPM) --prefix frontend run check

check-desktop:
	$(NODE) --test desktop/test/*.test.cjs

lint:
	$(PYTHON) -m ruff check .
	$(NPM) --prefix frontend run lint

test:
	$(PYTHON) -m pytest -q
	$(NPM) --prefix frontend test
	$(NODE) --test desktop/test/*.test.cjs

build:
	$(NPM) --prefix frontend run build
