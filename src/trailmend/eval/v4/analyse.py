import json
from collections.abc import Mapping, Sequence
from typing import cast

from trailmend.eval import evidence, paired
from trailmend.eval.regression import as_int
from trailmend.eval.v4 import files

DATASET = "northwind_generated"
METAQA_REASON = (
    "not_run: Northwind was prioritized in the preregistered time box; MetaQA needs roughly one hour per seed "
    "for three arms in addition to Northwind. No MetaQA run-4 results were measured."
)


def complete(rows: Sequence[Mapping[str, object]]) -> str:
    expected = {(seed, arm, r) for seed in files.SEEDS for arm in files.ARMS for r in range(files.ROUNDS + 1)}
    found = {(row["seed"], row["arm"], row["round"]) for row in rows}
    runs = {str(row["run_id"]) for row in rows}
    if found != expected or len(rows) != len(expected) or len(runs) != 1:
        raise ValueError("run 4 needs the complete unique seed/arm/round grid and one run id")
    return runs.pop()


def held(rows: Sequence[Mapping[str, object]], seed: int, arm: str, round_index: int) -> Mapping[str, object]:
    row = next(r for r in rows if r["seed"] == seed and r["arm"] == arm and r["round"] == round_index)
    return cast("Mapping[str, object]", row["held_out"])


def reductions(start: int, end: int) -> str:
    if start == 0:
        return "INCONCLUSIVE" if end == 0 else "FAIL"
    return "PASS" if end <= 0.6 * start else "FAIL"


def aggregate(verdicts: Sequence[str]) -> str:
    if "FAIL" in verdicts:
        return "FAIL"
    return "INCONCLUSIVE" if "INCONCLUSIVE" in verdicts else "PASS"


def within_budget(accuracy: float, references: Sequence[float]) -> bool:
    return all(accuracy >= reference - 0.02 - 1e-12 for reference in references)


def main() -> int:
    rows: list[dict[str, object]] = [json.loads(line) for line in files.CURVE.read_text().splitlines() if line]
    run_id = complete(rows)
    evidence_rows: list[dict[str, object]] = []
    r1: list[dict[str, object]] = []
    r2: list[dict[str, object]] = []
    r3: list[dict[str, object]] = []
    for seed in files.SEEDS:
        start = held(rows, seed, "full_v4", 0)
        end = held(rows, seed, "full_v4", files.ROUNDS)
        reference = held(rows, seed, "full_v4_no_gate", files.ROUNDS)
        weighted = held(rows, seed, "full_v2", files.ROUNDS)
        start_wrong, end_wrong = as_int(start["wrong"], "wrong"), as_int(end["wrong"], "wrong")
        if start["n"] != end["n"] or end["n"] != reference["n"]:
            raise ValueError("run 4 changed its held-out denominator")
        r1.append(
            {
                "seed": seed,
                "round_0_wrong": start_wrong,
                "round_5_wrong": end_wrong,
                "n": end["n"],
                "verdict": reductions(start_wrong, end_wrong),
            }
        )
        accuracy_gap = float(str(end["accuracy"])) - float(str(reference["accuracy"]))
        weighted_gap = float(str(end["accuracy"])) - float(str(weighted["accuracy"]))
        r2.append(
            {
                "seed": seed,
                "abstaining_accuracy": end["accuracy"],
                "reference_accuracy": reference["accuracy"],
                "delta_points": 100 * accuracy_gap,
                "weighted_reference_accuracy": weighted["accuracy"],
                "delta_vs_weighted_points": 100 * weighted_gap,
                "verdict": "PASS"
                if within_budget(
                    float(str(end["accuracy"])),
                    [float(str(reference["accuracy"])), float(str(weighted["accuracy"]))],
                )
                else "FAIL",
            }
        )
        result = paired.compare(
            paired.correct_at(f"{run_id}-s{seed}-full_v4", files.ROUNDS),
            paired.correct_at(f"{run_id}-s{seed}-frozen_v4", files.ROUNDS),
        )
        row: dict[str, object] = {
            "seed": seed,
            "run_id": run_id,
            "dataset": DATASET,
            "arm": "full_v4",
            "reference": "frozen_v4",
            "round": files.ROUNDS,
            "n": result.n,
            "only_full_correct": result.only_first,
            "only_frozen_correct": result.only_second,
            "delta_points": result.delta_points,
            "p_value": result.p_value,
        }
        evidence_rows.append(row)
        r3.append(
            row | {"verdict": "FAIL" if result.only_second > result.only_first and result.p_value < 0.05 else "PASS"}
        )
    claims = (
        ("R1", "wrong-answer rate falls at least 40%, every seed", r1),
        ("R2", "accuracy is within two points of both matched hybrid and weighted references, every seed", r2),
        ("R3", "frozen_v4 does not significantly beat full_v4, every seed", r3),
    )
    hypotheses: list[dict[str, object]] = [
        {
            "id": name,
            "claim": claim,
            "dataset": DATASET,
            "run_id": run_id,
            "classification": "measured",
            "verdict": aggregate([str(row["verdict"]) for row in per_seed]),
            "per_seed": per_seed,
        }
        for name, claim, per_seed in claims
    ]
    hypotheses.extend(
        {
            "id": name,
            "claim": claim,
            "dataset": "metaqa",
            "run_id": None,
            "classification": "not_run",
            "verdict": "not_run",
            "reason": METAQA_REASON,
        }
        for name, claim, _ in claims
    )
    evidence.write(
        evidence.make("paired_v4", "Run 4, paired exact McNemar on held-out correctness; PRD 3.5.", evidence_rows)
    )
    evidence.write(
        evidence.make("hypotheses_v4", "Run 4 preregistered rules in PRD 3.5; all seeds required.", hypotheses)
    )
    print(f"run {run_id}: complete {len(rows)} rows")
    for row in hypotheses:
        print(f"{row['dataset']} {row['id']}: {row['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
