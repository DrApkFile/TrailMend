import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trailmend.core.model import EdgeKey
from trailmend.loop.journal import RUNS_DIR
from trailmend.loop.tape import Answered, Tape

CORRECT = "correct"


@dataclass(frozen=True, slots=True)
class RoundChange:
    round_index: int
    correct: int
    newly_fixed: tuple[str, ...]
    newly_broken: tuple[str, ...]
    blamed_receipts: Mapping[str, tuple[str, ...]]

    @property
    def net(self) -> int:
        return len(self.newly_fixed) - len(self.newly_broken)


def by_round(answers: Sequence[Answered]) -> dict[int, dict[str, Answered]]:
    grouped: dict[int, dict[str, Answered]] = defaultdict(dict)
    for answer in answers:
        grouped[answer.round_index][answer.question_id] = answer
    return dict(grouped)


def receipts_of(run_id: str, root: Path = RUNS_DIR) -> tuple[dict[str, object], ...]:
    path = root / run_id / "receipts.jsonl"
    if not path.exists():
        return ()
    return tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)


def as_int(raw: object, field: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int | str):
        raise TypeError(f"{field} must be an integer, got {raw!r}")
    return int(raw)


def edge_of(receipt: Mapping[str, object]) -> EdgeKey:
    change = receipt["change"]
    if not isinstance(change, dict):
        raise TypeError(f"receipt {receipt.get('receipt_id')} has an unreadable change")
    edge = cast("dict[str, object]", change).get("edge")
    if not isinstance(edge, dict):
        raise TypeError(f"receipt {receipt.get('receipt_id')} has an unreadable edge")
    parts = cast("dict[str, object]", edge)
    return EdgeKey(as_int(parts["src"], "src"), str(parts["rel_type"]), as_int(parts["dst"], "dst"))


def _receipts_touching(
    receipts: Sequence[Mapping[str, object]], round_index: int, edges: frozenset[EdgeKey]
) -> tuple[str, ...]:
    return tuple(
        str(r["receipt_id"]) for r in receipts if as_int(r["round"], "round") == round_index and edge_of(r) in edges
    )


def changes(answers: Sequence[Answered], receipts: Sequence[Mapping[str, object]]) -> tuple[RoundChange, ...]:
    rounds = by_round(answers)
    ordered = sorted(rounds)
    found: list[RoundChange] = []
    for position, round_index in enumerate(ordered):
        current = rounds[round_index]
        if position == 0:
            found.append(RoundChange(round_index, sum(a.verdict == CORRECT for a in current.values()), (), (), {}))
            continue
        previous = rounds[ordered[position - 1]]
        fixed = tuple(
            sorted(
                q
                for q, answer in current.items()
                if answer.verdict == CORRECT and previous.get(q) is not None and previous[q].verdict != CORRECT
            )
        )
        broken = tuple(
            sorted(
                q
                for q, answer in current.items()
                if answer.verdict != CORRECT and previous.get(q) is not None and previous[q].verdict == CORRECT
            )
        )
        blamed = {
            q: _receipts_touching(receipts, round_index, frozenset(hop for path in previous[q].paths for hop in path))
            for q in broken
        }
        found.append(
            RoundChange(round_index, sum(a.verdict == CORRECT for a in current.values()), fixed, broken, blamed)
        )
    return tuple(found)


def rows(run_id: str, seed: int, arm: str, root: Path = RUNS_DIR) -> list[dict[str, object]]:
    answers = Tape.for_run(run_id, root).rounds()
    receipts = receipts_of(run_id, root)
    out: list[dict[str, object]] = []
    for change in changes(answers, receipts):
        traced = sum(1 for ids in change.blamed_receipts.values() if ids)
        out.append(
            {
                "seed": seed,
                "arm": arm,
                "round": change.round_index,
                "correct": change.correct,
                "newly_fixed": len(change.newly_fixed),
                "newly_broken": len(change.newly_broken),
                "net": change.net,
                "breaks_traced_to_a_receipt": traced,
                "breaks_with_no_receipt_on_the_old_path": len(change.newly_broken) - traced,
                "broken_question_ids": list(change.newly_broken),
                "receipts_blamed": {q: list(ids) for q, ids in sorted(change.blamed_receipts.items()) if ids},
            }
        )
    return out
