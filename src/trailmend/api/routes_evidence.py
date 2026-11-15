import json
from pathlib import Path

from fastapi import APIRouter

from trailmend.errors import ErrorCode, TrailMendError
from trailmend.eval import curve, evidence

router = APIRouter()
SERVABLE: tuple[str, ...] = (
    "round_zero",
    "plain_store",
    "non_regression",
    "quarantine",
    "mechanisms",
    "hypotheses",
    "run_manifest",
    "load",
    "latency",
)


@router.get("/v1/evidence/curve")
def evidence_curve() -> dict[str, object]:
    path = curve.CURVE
    if not path.exists():
        return {"rows": [], "available": False}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {"rows": rows, "available": True, "sha256": evidence.digest(path)}


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
    return {"servable": list(SERVABLE), "files": present}
