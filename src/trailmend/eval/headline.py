import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from trailmend.eval import evidence

FACTS = evidence.EVIDENCE_DIR / "benchmark_facts.json"
SUMMARY_V4 = evidence.EVIDENCE_DIR / "summary_v4.json"
START = "<!-- headline:start -->"
END = "<!-- headline:end -->"
DASH = "—"

type Facts = Mapping[str, object]


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _section(facts: object, key: str) -> Facts:
    if not isinstance(facts, dict):
        return {}
    found = cast("dict[str, object]", facts).get(key)
    return cast("Facts", found) if isinstance(found, dict) else {}


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def pct(value: object) -> str:
    found = _num(value)
    return f"{100 * found:.1f}%" if found is not None else DASH


def _arm(summary: object, name: str) -> Facts:
    if not isinstance(summary, dict):
        return {}
    rows = cast("dict[str, object]", summary).get("rows")
    if not isinstance(rows, list) or not rows:
        return {}
    first = cast("list[object]", rows)[0]
    arms = cast("dict[str, object]", first).get("arms") if isinstance(first, dict) else None
    for arm in cast("list[object]", arms) if isinstance(arms, list) else []:
        if isinstance(arm, dict) and cast("dict[str, object]", arm).get("arm") == name:
            return cast("Facts", arm)
    return {}


def _verdicts(summary: object) -> str:
    if not isinstance(summary, dict):
        return DASH
    rows = cast("dict[str, object]", summary).get("rows")
    first = cast("list[object]", rows)[0] if isinstance(rows, list) and rows else None
    found = cast("dict[str, object]", first).get("verdicts") if isinstance(first, dict) else None
    if not isinstance(found, dict) or not found:
        return DASH
    verdicts = cast("dict[str, object]", found)
    passed = [key for key, value in verdicts.items() if value == "PASS"]
    return f"preregistered {len(passed)} of {len(verdicts)} pass"


def _traced(north: Facts, meta: Facts) -> str:
    breaks = [_num(f.get("breaks")) for f in (north, meta)]
    traced = [_num(f.get("breaks_traced")) for f in (north, meta)]
    if any(b is None for b in breaks) or any(t is None for t in traced):
        return DASH
    total = int(sum(cast("list[float]", breaks)))
    found = int(sum(cast("list[float]", traced)))
    return f"{found} of {total} breaks traced to a receipt"


def _seeds(found: object, tested: object) -> str:
    a, b = _num(found), _num(tested)
    return f"{int(a)} of {int(b)} seeds" if a is not None and b is not None else DASH


def _kept(north: Facts, meta: Facts) -> str:
    parts = [_num(north.get(k)) for k in ("still_right_at_round_n", "right_at_round_0")]
    parts += [_num(meta.get(k)) for k in ("still_right_at_round_n", "right_at_round_0")]
    if any(p is None for p in parts):
        return DASH
    kept = int(cast("float", parts[0])) + int(cast("float", parts[2]))
    right = int(cast("float", parts[1])) + int(cast("float", parts[3]))
    return f"{kept:,} of {right:,}"


def rows() -> list[tuple[str, str, str, str]]:
    facts = _load(FACTS)
    clean = _section(facts, "northwind_clean_replication")
    north = _section(facts, "northwind_run_2")
    meta = _section(facts, "metaqa")
    summary = _load(SUMMARY_V4)
    v4 = _arm(summary, "full_v4")
    v4_frozen = _arm(summary, "frozen_v4")
    return [
        (
            "Company graphs, clean replication: held-out accuracy",
            pct(clean.get("full_round_0")),
            pct(clean.get("full_round_n")),
            f"frozen graph {pct(clean.get('frozen_round_n'))}; "
            f"beats it significantly on {_seeds(clean.get('full_beats_frozen_seeds'), clean.get('seeds_tested'))}",
        ),
        (
            "Company graphs, run 4 learner: held-out accuracy",
            pct(v4.get("accuracy_0")),
            pct(v4.get("accuracy_5")),
            f"frozen graph {pct(v4_frozen.get('accuracy_5'))}; refuses {pct(v4.get('refused_5'))}; "
            f"{_verdicts(summary)}",
        ),
        (
            "Company graphs, run 4 learner: wrong answers",
            pct(v4.get("wrong_0")),
            pct(v4.get("wrong_5")),
            f"frozen graph {pct(v4_frozen.get('wrong_5'))}",
        ),
        (
            "MetaQA (public, half the triples withheld): Hits@1",
            pct(meta.get("hits_round_0")),
            pct(meta.get("hits_round_n")),
            f"frozen graph {pct(meta.get('frozen_round_n'))}, random reweighting "
            f"{pct(meta.get('random_reweight_round_n'))}; beats frozen significantly on "
            f"{_seeds(meta.get('seeds_significant'), meta.get('seeds_tested'))}",
        ),
        (
            "Same questions, document store with no graph",
            pct(north.get("plain_store")),
            pct(north.get("plain_store")),
            "flat: no links for the loop to repair",
        ),
        (
            "Held-out answers right at the start, still right at the end (run 2 and MetaQA)",
            DASH,
            _kept(north, meta),
            _traced(north, meta),
        ),
    ]


def table() -> str:
    lines = ["| result | before | after learning | against |", "|---|---|---|---|"]
    lines += [f"| {what} | {before} | **{after}** | {control} |" for what, before, after, control in rows()]
    return "\n".join(lines)
