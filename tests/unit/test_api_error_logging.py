import asyncio
import json
import logging

import pytest
from starlette.requests import Request

from trailmend.api.app import trailmend_error
from trailmend.errors import ERROR_SPECS, ErrorCode, TrailMendError


def _request(method: str, path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "scheme": "https",
            "server": ("testserver", 443),
        }
    )


def _answer(exc: TrailMendError, method: str = "POST", path: str = "/v1/ask") -> tuple[int, dict[str, object]]:
    response = asyncio.run(trailmend_error(_request(method, path), exc))
    payload: dict[str, object] = json.loads(bytes(response.body))
    return response.status_code, payload


def test_the_public_body_says_only_the_closed_code_message_and_next_action() -> None:
    detail = "seed entity svc:s1-billing resolved to 3 candidates from the phrase 'billing'"
    status, payload = _answer(TrailMendError(ErrorCode.AMBIGUOUS_SEED, detail))

    assert status == ERROR_SPECS[ErrorCode.AMBIGUOUS_SEED].http_status
    assert payload == {
        "error": {
            "code": "ambiguous_seed",
            "message": ERROR_SPECS[ErrorCode.AMBIGUOUS_SEED].message,
            "retryable": False,
            "next_action": ERROR_SPECS[ErrorCode.AMBIGUOUS_SEED].next_action,
        }
    }
    assert detail not in json.dumps(payload)


def test_the_detail_and_the_route_are_logged_server_side(caplog: pytest.LogCaptureFixture) -> None:
    detail = "probe_write: HTTP 403 permission_denied"
    with caplog.at_level(logging.ERROR, logger="trailmend.api"):
        _answer(TrailMendError(ErrorCode.GRAPH_UNAVAILABLE, detail), "GET", "/v1/ready")

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "GET /v1/ready" in logged
    assert "503 graph_unavailable" in logged
    assert detail in logged


def _timed_out() -> TrailMendError:
    cause = TimeoutError("read timed out after 30.0s")
    error = TrailMendError(ErrorCode.GRAPH_UNAVAILABLE, "query timed out")
    error.__cause__ = cause
    return error


def test_the_cause_of_the_error_is_logged_with_its_traceback(caplog: pytest.LogCaptureFixture) -> None:
    exc = _timed_out()
    with caplog.at_level(logging.ERROR, logger="trailmend.api"):
        _answer(exc, "POST", "/v1/judge")

    record = caplog.records[-1]
    assert record.exc_info is not None
    logged = record.exc_info[1]
    assert logged is not None
    assert "read timed out after 30.0s" in str(logged.__cause__)


def test_an_error_with_no_detail_still_logs_the_route_and_the_code(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="trailmend.api"):
        _answer(TrailMendError(ErrorCode.RATE_LIMITED), "POST", "/v1/ask")

    logged = caplog.records[-1].getMessage()
    assert "429 rate_limited" in logged
    assert "no detail given" in logged
