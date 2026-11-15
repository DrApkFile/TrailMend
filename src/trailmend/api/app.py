import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from trailmend.api import demo, routes_ask, routes_evidence, routes_mend
from trailmend.api.state import Live, build_live
from trailmend.errors import ERROR_SPECS, ErrorCode, TrailMendError
from trailmend.graph.client import HydraClient
from trailmend.settings import load_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("trailmend.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    live = build_live(load_settings())
    app.state.live = live
    app.state.hydra = live.client
    app.state.first_load = asyncio.get_running_loop().run_in_executor(None, demo.load_if_empty, live)
    yield
    live.close()


app = FastAPI(title="TrailMend", lifespan=lifespan)
app.include_router(routes_ask.router)
app.include_router(routes_mend.router)
app.include_router(routes_evidence.router)


@app.exception_handler(TrailMendError)
async def trailmend_error(request: Request, exc: TrailMendError) -> JSONResponse:
    spec = ERROR_SPECS[exc.code]
    logger.error(
        "%s %s answered %s %s: %s",
        request.method,
        request.url.path,
        spec.http_status,
        exc.code.value,
        exc.detail or "no detail given",
        exc_info=exc,
    )
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
    live: Live = app.state.live
    hydra: HydraClient = live.client
    if not hydra.is_healthy():
        raise TrailMendError(ErrorCode.GRAPH_UNAVAILABLE, "healthz failed")
    hydra.require_writable()
    return {"graph_writable": True}
