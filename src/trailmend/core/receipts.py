import hashlib
import json
from dataclasses import asdict, dataclass

from trailmend.core.model import Change, EdgeState, Quarantine, Restore, Reweight


@dataclass(frozen=True, slots=True)
class Receipt:
    receipt_id: str
    run_id: str
    round_index: int
    sequence: int
    kind: str
    change: Change
    before: EdgeState
    after: EdgeState
    digest: str


def _kind(change: Change) -> str:
    match change:
        case Reweight():
            return "reweight"
        case Quarantine():
            return "quarantine"
        case Restore():
            return "restore"


def _digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def make_receipt(
    run_id: str, round_index: int, sequence: int, change: Change, before: EdgeState, after: EdgeState
) -> Receipt:
    if round_index < 0 or sequence < 0:
        raise ValueError("round_index and sequence must be non-negative")
    kind = _kind(change)
    body: dict[str, object] = {
        "run_id": run_id,
        "round": round_index,
        "sequence": sequence,
        "kind": kind,
        "change": asdict(change),
        "before": asdict(before),
        "after": asdict(after),
    }
    digest = _digest(body)
    return Receipt(f"rcpt-{digest[:16]}", run_id, round_index, sequence, kind, change, before, after, digest)


def to_json(receipt: Receipt) -> str:
    payload: dict[str, object] = {
        "receipt_id": receipt.receipt_id,
        "run_id": receipt.run_id,
        "round": receipt.round_index,
        "sequence": receipt.sequence,
        "kind": receipt.kind,
        "change": asdict(receipt.change),
        "before": asdict(receipt.before),
        "after": asdict(receipt.after),
        "digest": receipt.digest,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def inverse(receipt: Receipt) -> Restore:
    return Restore(receipt.before.key, receipt.before)
