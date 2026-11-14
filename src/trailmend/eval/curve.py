import json
import os
from dataclasses import asdict
from pathlib import Path

from trailmend.loop.round import RoundOutcome

CURVE = Path("evidence/curve.jsonl")


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
        "receipts": len(outcome.receipt_ids),
    }


def append(payload: dict[str, object], path: Path = CURVE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path
