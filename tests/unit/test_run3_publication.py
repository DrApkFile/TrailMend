import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from trailmend.api import routes_evidence
from trailmend.eval import evidence
from trailmend.eval.v3 import report


def test_run3_api_reports_absent_then_serves_the_measured_payload_with_its_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(evidence, "EVIDENCE_DIR", tmp_path)
    app = FastAPI()
    app.include_router(routes_evidence.router)
    with TestClient(app) as client:
        assert client.get("/v1/evidence/summary_v3").json()["available"] is False
        payload = {"rows": [{"run_id": "v3-test", "verdicts": {"R1": "FAIL", "R2": "FAIL", "R3": "PASS"}}]}
        path = tmp_path / "summary_v3.json"
        path.write_text(json.dumps(payload))
        response = client.get("/v1/evidence/summary_v3")
        assert response.status_code == 200
        assert response.json()["payload"] == payload
        assert response.json()["sha256"] == evidence.digest(path)


def test_run3_curve_uses_its_own_route_and_never_reads_run_two(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "curve_v3_northwind.jsonl"
    monkeypatch.setitem(routes_evidence.CURVES, "curve-v3-northwind", path)
    app = FastAPI()
    app.include_router(routes_evidence.router)
    with TestClient(app) as client:
        assert client.get("/v1/evidence/curve-v3-northwind").json()["available"] is False
        row = {"run_id": "v3-test", "arm": "full_v2_abstain", "round": 5}
        path.write_text(json.dumps(row) + "\n")
        body = client.get("/v1/evidence/curve-v3-northwind").json()
        assert body["available"] is True
        assert body["rows"] == [row]


def test_run3_readme_writer_preserves_other_runs_and_replaces_only_its_own_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary = tmp_path / "summary_v3.json"
    summary.write_text(
        json.dumps({"rows": [{"run_id": "v3-test", "seeds": [1], "rounds": 5, "arms": [], "verdicts": {"R1": "FAIL"}}]})
    )
    monkeypatch.setattr(report, "SUMMARY", summary)
    readme = tmp_path / "README.md"
    original = "before\n<!-- numbers:start -->\nhistorical figures\n<!-- numbers:end -->\nafter\n"
    readme.write_text(original)
    report.write_readme(readme)
    once = readme.read_text()
    report.write_readme(readme)
    assert readme.read_text() == once
    assert "historical figures\n" in once
    assert once.startswith("before\n<!-- numbers:start -->\n")
    assert once.endswith("<!-- numbers:end -->\nafter\n")
