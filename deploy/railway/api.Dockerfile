FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config
COPY evidence/*.json evidence/*.jsonl ./evidence/
RUN uv sync --frozen --no-dev
EXPOSE 8000
CMD ["sh", "-c", "uv run --no-dev uvicorn trailmend.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
