import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from trailmend.eval import curve, evidence
from trailmend.loop.policy import MendPolicy

FULL = MendPolicy.FULL_V2.value
FROZEN = MendPolicy.FROZEN.value
UNWEIGHTED = MendPolicy.FULL_UNWEIGHTED.value
CLAIM = "replication_v2_clean"
ALPHA = 0.05

type Rows = Sequence[Mapping[str, object]]


def _rows(path: Path) -> Rows:
    if not path.exists():
        return ()
    if path.suffix == ".jsonl":
        return tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    rows = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8"))).get("rows")
    return tuple(cast("list[Mapping[str, object]]", rows)) if isinstance(rows, list) else ()


def _num(raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float | str):
        raise TypeError(f"expected a number, got {raw!r}")
    return float(raw)


def _mean(rows: Rows, arm: str, round_index: int) -> float | None:
    found = [
        _num(cast("dict[str, object]", row["held_out"])["accuracy"])
        for row in rows
        if row.get("arm") == arm and row.get("round") == round_index
    ]
    return sum(found) / len(found) if found else None


def _paired(rows: Rows, arm: str, reference: str) -> tuple[int, int, int]:
    found = [r for r in rows if r.get("kind") == "paired" and r.get("arm") == arm and r.get("reference") == reference]
    higher = sum(_num(r["p_value"]) < ALPHA and _num(r["delta_points"]) > 0 for r in found)
    lower = sum(_num(r["p_value"]) < ALPHA and _num(r["delta_points"]) < 0 for r in found)
    return higher, lower, len(found)


def facts() -> dict[str, object]:
    analysed = _rows(evidence.EVIDENCE_DIR / f"{CLAIM}.json")
    clean = _rows(curve.CURVE_V2_CLEAN)
    if not analysed or not clean:
        return {}
    final = max(int(_num(row["round"])) for row in clean)
    full_higher, _, tested = _paired(analysed, FULL, FROZEN)
    unweighted_higher, unweighted_lower, unweighted_tested = _paired(analysed, UNWEIGHTED, FULL)
    outside = [r for r in analysed if r.get("kind") == "outside_g0"]
    runs = next(r for r in analysed if r.get("kind") == "runs")
    return {
        "run_id": runs["clean_run_id"],
        "rounds": final,
        "full_round_0": _mean(clean, FULL, 0),
        "full_round_n": _mean(clean, FULL, final),
        "frozen_round_n": _mean(clean, FROZEN, final),
        "unweighted_round_0": _mean(clean, UNWEIGHTED, 0),
        "unweighted_round_n": _mean(clean, UNWEIGHTED, final),
        "full_beats_frozen_seeds": full_higher,
        "seeds_tested": tested,
        "unweighted_higher_seeds": unweighted_higher,
        "unweighted_lower_seeds": unweighted_lower,
        "unweighted_seeds_tested": unweighted_tested,
        "frozen_edges_outside_g0": sum(len(cast("list[object]", r["edges_outside_g0"])) for r in outside),
    }


def _pct(value: object) -> str:
    return f"{100 * _num(value):.1f}%" if value is not None else "—"


def _int(value: object) -> int:
    return int(_num(value)) if value is not None else 0


def comparability(clean: Mapping[str, object]) -> str:
    beat, tested = _int(clean.get("full_beats_frozen_seeds")), _int(clean.get("seeds_tested"))
    outcome = (
        "reproduced the gain"
        if tested and beat == tested
        else f"reproduced a significant gain over the frozen graph on {beat} of {tested} seeds"
    )
    return (
        "Run 2's shared graph carried stray edges from earlier runs, so it was replicated on an emptied HydraDB "
        f"(run {clean.get('run_id')}): the full loop went from {_pct(clean.get('full_round_0'))} to "
        f"{_pct(clean.get('full_round_n'))} against {_pct(clean.get('frozen_round_n'))} for the frozen graph, which "
        f"{outcome}; run 2's own numbers below stay as recorded."
    )


def unweighted_clause(clean: Mapping[str, object]) -> str | None:
    unweighted, weighted = clean.get("unweighted_round_n"), clean.get("full_round_n")
    if unweighted is None or weighted is None:
        return None
    gap = 100 * (_num(weighted) - _num(unweighted))
    side = "below" if gap > 0 else "above"
    return (
        f"on the clean replication, the same loop with unweighted search goes from "
        f"{_pct(clean.get('unweighted_round_0'))} to {_pct(unweighted)}, {abs(gap):.1f} points {side} the loop that "
        f"searches on cost on the same graph (significantly higher on {_int(clean.get('unweighted_higher_seeds'))} "
        f"of {_int(clean.get('unweighted_seeds_tested'))} seeds, significantly lower on "
        f"{_int(clean.get('unweighted_lower_seeds'))})"
    )
