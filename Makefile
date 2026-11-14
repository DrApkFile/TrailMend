.PHONY: install gate lint typecheck test test-live verify hydra-up hydra-down api

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

gate: lint typecheck test

verify: test-live

hydra-up:
	./scripts/hydra_up.sh

hydra-down:
	docker compose down

api:
	uv run uvicorn trailmend.api.app:app --reload --port 8000
