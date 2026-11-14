from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from trailmend.errors import ERROR_SPECS, ErrorCode, TrailMendError
from trailmend.graph.client import HydraClient
from trailmend.settings import load_settings


def _client() -> HydraClient:
    s = load_settings()
    return HydraClient(
        str(s.hydra_url), s.hydra_token.get_secret_value(), s.hydra_graph_id, s.hydra_cell_id, s.hydra_timeout_s
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.hydra = _client()
    yield
    app.state.hydra.close()


app = FastAPI(title="TrailMend", lifespan=lifespan)


@app.exception_handler(TrailMendError)
async def trailmend_error(_: object, exc: TrailMendError) -> JSONResponse:
    spec = ERROR_SPECS[exc.code]
    body = {
        "error": {
            "code": exc.code.value,
            "message": spec.message,
            "retryable": spec.retryable,
            "next_action": spec.next_action,
        }
    }
    return JSONResponse(body, status_code=spec.http_status)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/ready")
def ready() -> dict[str, bool]:
    hydra: HydraClient = app.state.hydra
    if not hydra.is_healthy():
        raise TrailMendError(ErrorCode.GRAPH_UNAVAILABLE, "healthz failed")
    hydra.require_writable()
    return {"graph_writable": True}
