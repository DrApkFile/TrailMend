.PHONY: install gate lint typecheck test test-live verify web-install web-lint web-typecheck web-build web evidence-load hydra-up hydra-down api

install:
	uv sync --frozen

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run pyright

test:
	uv run pytest -m "not hydra"

test-live:
	uv run pytest -m hydra

web-install:
	cd apps/web && npm ci

web-lint:
	cd apps/web && npm run lint

web-typecheck:
	cd apps/web && npm run typecheck

web-build:
	cd apps/web && TRAILMEND_API=$${TRAILMEND_API:-http://127.0.0.1:8000} npm run build

web: web-typecheck web-lint web-build

gate: lint typecheck test web

verify: test-live

evidence-load:
	uv run python -m trailmend.eval.load_evidence

hydra-up:
	./scripts/hydra_up.sh

hydra-down:
	./scripts/hydra_down.sh

api:
	uv run uvicorn trailmend.api.app:app --reload --port 8000
