import json
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from trailmend.eval import evidence

RUN2 = "26b5469-580ae8dc"
RUNS = Path("evidence/runs")
EXAMPLES_PER_ROUND = 6
EXAMPLE_ORDER = ("quarantine", "gapfill", "promote", "reweight")


def path_for(dataset: str, seed: int) -> Path:
    return evidence.EVIDENCE_DIR / f"replay_{dataset}_s{seed}.json"


def _lines(path: Path) -> Iterator[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _accuracy(heldout: Path) -> dict[int, dict[str, object]]:
    by_round: dict[int, Counter[str]] = {}
    verdicts: dict[int, dict[str, str]] = {}
    for row in _lines(heldout):
        index = int(str(row["round"]))
        by_round.setdefault(index, Counter())[str(row["verdict"])] += 1
        verdicts.setdefault(index, {})[str(row["question_id"])] = str(row["verdict"])
    rounds: dict[int, dict[str, object]] = {}
    for index, counts in sorted(by_round.items()):
        before = verdicts.get(index - 1, {})
        now = verdicts[index]
        fixed = sum(1 for q, v in now.items() if v == "correct" and before.get(q, "correct") != "correct")
        broke = sum(1 for q, v in now.items() if v != "correct" and before.get(q, v) == "correct")
        rounds[index] = {
            "n": sum(counts.values()),
            "correct": counts["correct"],
            "fixed": fixed if index else 0,
            "broke": broke if index else 0,
        }
    return rounds


def _edge(key: object) -> dict[str, object]:
    assert isinstance(key, dict)
    return {"src": key["src"], "rel_type": key["rel_type"], "dst": key["dst"]}  # pyright: ignore[reportUnknownVariableType]


def _receipts(path: Path) -> tuple[dict[int, Counter[str]], dict[int, list[dict[str, object]]]]:
    counts: dict[int, Counter[str]] = {}
    pools: dict[int, dict[str, list[dict[str, object]]]] = {}
    for row in _lines(path):
        index = int(str(row["round"]))
        kind = str(row["kind"])
        counts.setdefault(index, Counter())[kind] += 1
        before = row["before"]
        after = row["after"]
        assert isinstance(before, dict)
        assert isinstance(after, dict)
        example: dict[str, object] = {
            "receipt_id": row["receipt_id"],
            "kind": kind,
            "edge": _edge(after["key"]),  # pyright: ignore[reportUnknownArgumentType]
            "before": {"cost": before["cost"], "status": before["status"]},
            "after": {"cost": after["cost"], "status": after["status"]},
        }
        pools.setdefault(index, {}).setdefault(kind, []).append(example)
    examples: dict[int, list[dict[str, object]]] = {}
    for index, by_kind in pools.items():
        queues = [sorted(by_kind.get(kind, []), key=_swing, reverse=True) for kind in EXAMPLE_ORDER]
        chosen: list[dict[str, object]] = []
        while len(chosen) < EXAMPLES_PER_ROUND and any(queues):
            for queue in queues:
                if queue and len(chosen) < EXAMPLES_PER_ROUND:
                    chosen.append(queue.pop(0))
        examples[index] = chosen
    return counts, examples


def _swing(example: dict[str, object]) -> float:
    before = example["before"]
    after = example["after"]
    assert isinstance(before, dict)
    assert isinstance(after, dict)
    return abs(float(after["cost"]) - float(before["cost"]))  # pyright: ignore[reportUnknownArgumentType]


def build(seed: int, run_id: str = RUN2) -> dict[str, object]:
    mended = RUNS / f"{run_id}-s{seed}-full_v2"
    frozen = RUNS / f"{run_id}-s{seed}-frozen"
    full = _accuracy(mended / "heldout.jsonl")
    still = _accuracy(frozen / "heldout.jsonl")
    counts, examples = _receipts(mended / "receipts.jsonl")
    rounds = [
        {
            "round": index,
            "full_v2": full[index],
            "frozen": still[index],
            "reweights": counts.get(index, Counter())["reweight"],
            "quarantines": counts.get(index, Counter())["quarantine"],
            "gapfills": counts.get(index, Counter())["gapfill"],
            "promotions": counts.get(index, Counter())["promote"],
            "examples": examples.get(index, []),
        }
        for index in sorted(full)
    ]
    return {
        "dataset": "northwind",
        "seed": seed,
        "run_id": run_id,
        "arms": ["full_v2", "frozen"],
        "sources": {
            "full_v2": {p.name: evidence.digest(p) for p in sorted(mended.iterdir()) if p.suffix == ".jsonl"},
            "frozen": {"heldout.jsonl": evidence.digest(frozen / "heldout.jsonl")},
        },
        "rounds": rounds,
    }


def main(seeds: tuple[int, ...]) -> int:
    for seed in seeds:
        out = path_for("northwind", seed)
        out.write_text(json.dumps(build(seed), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(tuple(int(a) for a in sys.argv[1:] if a.isdigit()) or (1,)))
