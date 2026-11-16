import json
import os
from dataclasses import asdict
from pathlib import Path

from trailmend.data.faultmodel import V1, V2
from trailmend.loop.round import RoundOutcome

CURVE = Path("evidence/curve.jsonl")
CURVE_V2 = Path("evidence/curve_v2.jsonl")
CURVE_V2_UNWEIGHTED = Path("evidence/curve_v2_unweighted.jsonl")
CURVE_V2_CLEAN = Path("evidence/curve_v2_clean.jsonl")
BY_VERSION: dict[str, Path] = {V1: CURVE, V2: CURVE_V2}
EXTENSIONS: dict[str, tuple[Path, ...]] = {V1: (), V2: (CURVE_V2_UNWEIGHTED, CURVE_V2_CLEAN)}


def path_for(data_version: str) -> Path:
    if data_version not in BY_VERSION:
        raise ValueError(f"no curve file for data version {data_version}")
    return BY_VERSION[data_version]


def row(dataset: str, seed: int, outcome: RoundOutcome) -> dict[str, object]:
    return {
        "dataset": dataset,
        "seed": seed,
        "arm": outcome.policy.value,
        "round": outcome.round_index,
        "run_id": outcome.run_id,
        "train": asdict(outcome.train),
        "held_out": asdict(outcome.held_out),
        "planned_reweights": outcome.planned.reweights,
        "planned_quarantines": outcome.planned.quarantines,
        "applied_reweights": outcome.applied.reweights,
        "applied_quarantines": outcome.applied.quarantines,
        "quarantined": len(outcome.quarantined),
        "promoted": len(outcome.promoted),
        "retired": len(outcome.retired),
        "gaps": outcome.gaps,
        "ingested": len(outcome.ingested),
        "gapfill_reached_this_round": len(outcome.reached),
        "receipts": len(outcome.receipt_ids),
    }


def append(payload: dict[str, object], path: Path = CURVE) -> Path:
    version = str(payload.get("data_version", V1))
    if path_for(version) != path and path not in EXTENSIONS[version]:
        raise ValueError(f"a {version} row belongs in {path_for(version)}, not {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path
