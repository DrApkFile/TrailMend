from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Self, cast
from uuid import uuid4

import httpx

from trailmend.errors import ErrorCode, TrailMendError
from trailmend.graph.queries import (
    PROBE_CLEANUP_SOURCE,
    PROBE_CLEANUP_TARGET,
    PROBE_READ,
    PROBE_TARGET_ID,
    PROBE_WRITE,
    NamedQuery,
)
from trailmend.graph.values import Cell, decode_cell

type ParamValue = int | float | str | bool | Sequence[Mapping[str, int | float | str | bool]]
type Params = Mapping[str, ParamValue]


@dataclass(frozen=True, slots=True)
class QueryResult:
    query_name: str
    server_query_id: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]


class HydraError(Exception):
    def __init__(self, query_name: str, status: int, code: str, message: str) -> None:
        super().__init__(f"{query_name}: HTTP {status} {code}: {message}")
        self.query_name = query_name
        self.status = status
        self.code = code
        self.message = message


def _as_object(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    return {str(k): v for k, v in cast("dict[object, object]", raw).items()}


def _parse_error(query_name: str, response: httpx.Response) -> HydraError:
    try:
        body = _as_object(response.json())
    except ValueError:
        return HydraError(query_name, response.status_code, "unparseable", response.text[:300])
    error = _as_object(body.get("error")) if body else None
    if error is None:
        return HydraError(query_name, response.status_code, "unknown", response.text[:300])
    return HydraError(
        query_name, response.status_code, str(error.get("code", "unknown")), str(error.get("message", ""))[:300]
    )


def _parse_result(query_name: str, body: dict[str, object]) -> QueryResult:
    columns = body.get("columns")
    rows = body.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise HydraError(query_name, 200, "unparseable", "response lacks columns/rows")
    decoded: list[tuple[Cell, ...]] = []
    for row in cast("list[object]", rows):
        if not isinstance(row, list):
            raise HydraError(query_name, 200, "unparseable", "row is not a list")
        cells = tuple(decode_cell(c) for c in cast("list[object]", row))
        if len(cells) != len(cast("list[object]", columns)):
            raise HydraError(query_name, 200, "unparseable", "row width does not match columns")
        decoded.append(cells)
    names = tuple(str(c) for c in cast("list[object]", columns))
    return QueryResult(query_name, str(body.get("query_id", "")), names, tuple(decoded))


class HydraClient:
    def __init__(self, base_url: str, token: str, graph_id: str, cell_id: str, timeout_s: float) -> None:
        self._graph_id = graph_id
        self._cell_id = cell_id
        self._bookmark: str | None = None
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout_s,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def run(self, query: NamedQuery, params: Params | None = None) -> QueryResult:
        payload: dict[str, object] = {
            "cell_id": self._cell_id,
            "query_id": f"tm-{uuid4().hex}",
            "query": query.cypher,
            "parameters": dict(params or {}),
        }
        if self._bookmark is not None:
            payload["bookmark"] = self._bookmark
        try:
            response = self._http.post(f"/v1/graphs/{self._graph_id}/query", json=payload)
        except httpx.TransportError as exc:
            raise TrailMendError(ErrorCode.GRAPH_UNAVAILABLE, f"{query.name}: {exc}") from exc
        if response.status_code >= 500:
            raise TrailMendError(ErrorCode.GRAPH_UNAVAILABLE, str(_parse_error(query.name, response)))
        if response.status_code != 200:
            raise _parse_error(query.name, response)
        body = _as_object(response.json())
        if body is None:
            raise HydraError(query.name, 200, "unparseable", "response is not an object")
        bookmark = body.get("bookmark")
        if isinstance(bookmark, str) and bookmark:
            self._bookmark = bookmark
        return _parse_result(query.name, body)

    def run_all(self, steps: Sequence[tuple[NamedQuery, Params]]) -> tuple[QueryResult, ...]:
        return tuple(self.run(q, p) for q, p in steps)

    def is_healthy(self) -> bool:
        try:
            return self._http.get("/healthz").status_code == 200
        except httpx.TransportError:
            return False

    def require_writable(self) -> None:
        self.run(PROBE_WRITE)
        result = self.run(PROBE_READ)
        self.run(PROBE_CLEANUP_SOURCE)
        self.run(PROBE_CLEANUP_TARGET)
        if result.rows != ((PROBE_TARGET_ID,),):
            raise TrailMendError(ErrorCode.GRAPH_UNAVAILABLE, f"writability probe read back {result.rows!r}")
