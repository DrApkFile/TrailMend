import json
from pathlib import Path

from fastapi import APIRouter

from trailmend.errors import ErrorCode, TrailMendError
from trailmend.eval import curve, evidence

router = APIRouter()
SERVABLE: tuple[str, ...] = (
    "round_zero",
    "plain_store",
    "plain_store_v2",
    "non_regression",
    "quarantine",
    "mechanisms",
    "changes",
    "hypotheses",
    "run_manifest",
    "load",
    "latency",
    "anatomy",
    "oracle",
    "fault_recoverability",
    "non_regression_v2",
    "quarantine_v2",
    "mechanisms_v2",
    "changes_v2",
    "hypotheses_v2",
    "paired_v2",
    "captured_share_v2",
    "oracle_v2",
    "fault_recoverability_v2",
    "run_manifest_v2",
)
CURVES: dict[str, Path] = {"curve": curve.CURVE, "curve-v2": Path("evidence/curve_v2.jsonl")}


def _curve(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"rows": [], "available": False}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {"rows": rows, "available": True, "sha256": evidence.digest(path)}


@router.get("/v1/evidence/curve")
def evidence_curve() -> dict[str, object]:
    return _curve(CURVES["curve"])


@router.get("/v1/evidence/curve-v2")
def evidence_curve_v2() -> dict[str, object]:
    return _curve(CURVES["curve-v2"])


@router.get("/v1/evidence/{name}")
def evidence_file(name: str) -> dict[str, object]:
    if name not in SERVABLE:
        raise TrailMendError(ErrorCode.INVALID_REQUEST, f"no evidence file {name}")
    path = Path(evidence.EVIDENCE_DIR) / f"{name}.json"
    if not path.exists():
        return {"name": name, "available": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {"name": name, "available": True, "sha256": evidence.digest(path), "payload": payload}


@router.get("/v1/evidence")
def evidence_index() -> dict[str, object]:
    directory = Path(evidence.EVIDENCE_DIR)
    present = (
        {p.name: evidence.digest(p) for p in sorted(directory.iterdir()) if p.is_file()} if directory.exists() else {}
    )
    return {"servable": [*CURVES, *SERVABLE], "files": present}
