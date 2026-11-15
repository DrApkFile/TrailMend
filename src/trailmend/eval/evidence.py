import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

EVIDENCE_DIR = Path("evidence")

type Row = Mapping[str, object]


@dataclass(frozen=True, slots=True)
class Evidence:
    claim: str
    design: str
    measured_at: str
    rows: tuple[Row, ...]
    measured_on: Mapping[str, object] | None = None

    def to_json(self) -> str:
        payload = {
            "claim": self.claim,
            "design": self.design,
            "measured_at": self.measured_at,
            "measured_on": dict(self.measured_on) if self.measured_on is not None else None,
            "rows": list(self.rows),
        }
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def make(
    claim: str,
    design: str,
    rows: Sequence[Row],
    measured_at: str | None = None,
    measured_on: Mapping[str, object] | None = None,
) -> Evidence:
    if not claim or not design:
        raise ValueError("evidence needs a claim and a design string")
    return Evidence(claim, design, measured_at or now_utc(), tuple(rows), measured_on)


def write(evidence: Evidence, directory: Path = EVIDENCE_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{evidence.claim}.json"
    path.write_text(evidence.to_json())
    return path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
