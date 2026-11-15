import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from trailmend.data.faultmodel import V2
from trailmend.eval import evidence, manifest, paired
from trailmend.eval.analyse import (
    PLAIN,
    accuracy_at,
    change_counts,
    check_inv6,
    last_round,
    mechanism_table,
    non_regression,
    quarantine_report,
    rows_of,
    seeds_of,
    write_chart,
)
from trailmend.eval.run import RUN2_ARMS
from trailmend.loop.policy import MendPolicy

CURVE_V2 = Path("evidence/curve_v2.jsonl")
ORACLE_V2 = Path("evidence/oracle_v2.json")
REACHABLE_STAGE = "and_ingest_withheld_edges"
ALPHA = 0.05
H1_RULE = (
    "full_v2 beats frozen on the same held-out questions at the last round under a two-sided exact McNemar test at "
    "p < 0.05, with a gain of at least 2.0 points, on all 3 of 3 seeds"
)
H2_RULE = "neither random control beats frozen under the same paired test on any seed"
H3_RULE = "the plain-store accuracy is identical at every round, for every seed"
H4_RULE = "recall on planted wrong edges >= 0.7 for every seed, and false-quarantine rate <= 0.1 where defined"
H5_RULE = "newly_broken / correct <= 0.02 in the worst round after round 0, full_v2"
H6_RULE = "the held-out wrong-answer rate falls by at least 40% from round 0 to the last round, every seed"
H7_RULE = "full_v2 ingests at least 60% of the withheld edges its own gap-fill rule reached, every seed"
H8_RULE = "full_v2 beats full_v1_rule under the same paired test on at least 2 of the 3 seeds"
NON_REGRESSION_DESIGN = (
    "Per round, from evidence/runs/<run>/heldout.jsonl: which held-out questions turned correct and which turned "
    "away from correct, and for each break the receipts written that round that touched an edge on that question's "
    "previous correct path."
)
QUARANTINE_DESIGN = (
    "Every quarantine receipt in a run against the planted faults for that seed on data v2. Precision counts "
    "quarantined edges that a fault introduced; recall counts planted wrong edges quarantined; the "
    "false-quarantine rate counts quarantined edges that are in the truth graph. An ingest is spurious if the edge "
    "it added is not in the truth graph."
)
MECHANISMS_DESIGN = (
    "One row per arm: which mechanisms it runs and what held-out accuracy it reached from round 0 to round N, per "
    "seed and as a mean. Arms share seeds, splits, rounds and questions; they differ in which changes they apply "
    "and under which update and gap-fill rule, which every curve row records."
)
HEADLINE = MendPolicy.FULL_V2
REFERENCE = MendPolicy.FROZEN


def run_id_of(rows: Sequence[Mapping[str, object]]) -> str:
    found = {str(row["run_id"]) for row in rows}
    if len(found) != 1:
        raise ValueError(f"{CURVE_V2} mixes runs {sorted(found)}; an analysis decides one run")
    return found.pop()


def require_v2(rows: Sequence[Mapping[str, object]]) -> None:
    versions = {str(row.get("data_version")) for row in rows}
    if versions != {V2}:
        raise ValueError(f"{CURVE_V2} carries data versions {sorted(versions)}, not just {V2}")


def _held_out(row: Mapping[str, object]) -> Mapping[str, object]:
    held = row.get("held_out")
    if not isinstance(held, dict):
        raise TypeError(f"row for {row.get('arm')} round {row.get('round')} has no held-out score")
    return cast("dict[str, object]", held)


def wrong_rate(rows: Sequence[Mapping[str, object]], arm: str, seed: int, round_index: int) -> float:
    for row in rows:
        if row.get("arm") == arm and row.get("seed") == seed and row.get("round") == round_index:
            held = _held_out(row)
            total = int(str(held["n"]))
            if total == 0:
                raise ValueError(f"{arm} seed {seed} round {round_index} scored no held-out questions")
            return int(str(held["wrong"])) / total
    raise KeyError(f"no curve row for arm {arm} seed {seed} round {round_index}")


def paired_rows(run_id: str, seeds: Sequence[int], final: int) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for seed in seeds:
        out.append(paired.row(run_id, seed, HEADLINE.value, REFERENCE.value, final))
        out.append(paired.row(run_id, seed, HEADLINE.value, MendPolicy.FULL_V1_RULE.value, final))
        for arm in (MendPolicy.RANDOM_REWEIGHT, MendPolicy.RANDOM_QUARANTINE, MendPolicy.GAPFILL_WIDE_ONLY):
            out.append(paired.row(run_id, seed, arm.value, REFERENCE.value, final))
    return out


def _pick(rows: Sequence[Mapping[str, object]], arm: str, reference: str, seed: int) -> Mapping[str, object]:
    for row in rows:
        if row["arm"] == arm and row["reference"] == reference and row["seed"] == seed:
            return row
    raise KeyError(f"no paired row for {arm} against {reference} on seed {seed}")


def _beats(row: Mapping[str, object], points: float = 0.0) -> bool:
    return float(str(row["p_value"])) < ALPHA and float(str(row["delta_points"])) >= points


def oracle_rows(path: Path = ORACLE_V2) -> tuple[Mapping[str, object], ...]:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist; run the oracle ladder on data v2 before deciding the run")
    payload = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path} records no oracle rows")
    return tuple(cast("list[Mapping[str, object]]", rows))


def _stage(rows: Sequence[Mapping[str, object]], seed: int, stage: str) -> float:
    for row in rows:
        if row["seed"] == seed and row["stage"] == stage:
            return float(str(row["held_out_accuracy"]))
    raise KeyError(f"the oracle ladder has no {stage} rung for seed {seed}")


def captured_share(
    rows: Sequence[Mapping[str, object]], ladder: Sequence[Mapping[str, object]], seeds: Sequence[int], final: int
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for seed in seeds:
        start = accuracy_at(rows, HEADLINE.value, seed, 0)
        reachable = _stage(ladder, seed, REACHABLE_STAGE) - _stage(ladder, seed, "g0")
        gained = accuracy_at(rows, HEADLINE.value, seed, final) - start
        if reachable <= 0:
            raise ValueError(f"seed {seed}: the oracle ladder leaves no reachable gain to capture")
        out.append(
            {
                "seed": seed,
                "arm": HEADLINE.value,
                "round_0": round(start, 4),
                "round_n": round(accuracy_at(rows, HEADLINE.value, seed, final), 4),
                "gained_points": round(100 * gained, 2),
                "reachable_points": round(100 * reachable, 2),
                "captured_share": round(gained / reachable, 4),
            }
        )
    return out


def gapfill_reach(rows: Sequence[Mapping[str, object]], seed: int, final: int) -> tuple[int, int]:
    for row in rows:
        if row.get("arm") == HEADLINE.value and row.get("seed") == seed and row.get("round") == final:
            reached = row.get("gapfill_reached")
            ingested = row.get("gapfill_ingested")
            if not isinstance(reached, int) or not isinstance(ingested, int):
                raise TypeError(f"seed {seed} round {final} did not record what gap-fill reached and ingested")
            return reached, ingested
    raise KeyError(f"no curve row for {HEADLINE.value} seed {seed} round {final}")


def hypotheses(
    rows: Sequence[Mapping[str, object]],
    breaks: Sequence[Mapping[str, object]],
    quarantines: Sequence[Mapping[str, object]],
    pairs: Sequence[Mapping[str, object]],
    final: int,
) -> list[dict[str, object]]:
    if not breaks or not quarantines or not pairs:
        raise ValueError("H1' to H8' cannot be decided without break rows, quarantine reports and paired rows")
    seeds = seeds_of(rows)
    head = [_pick(pairs, HEADLINE.value, REFERENCE.value, seed) for seed in seeds]
    h1 = all(_beats(row, 2.0) for row in head)
    controls = {
        arm.value: [_pick(pairs, arm.value, REFERENCE.value, seed) for seed in seeds]
        for arm in (MendPolicy.RANDOM_REWEIGHT, MendPolicy.RANDOM_QUARANTINE)
    }
    h2 = all(not _beats(row) for per_arm in controls.values() for row in per_arm)
    plain = {seed: {r: accuracy_at(rows, PLAIN, seed, r) for r in range(final + 1)} for seed in seeds}
    h3 = all(len(set(per_round.values())) == 1 for per_round in plain.values())
    head_q = [q for q in quarantines if q["arm"] == HEADLINE.value]
    if not head_q:
        raise ValueError(f"no quarantine report for {HEADLINE.value}")
    recalls = [q["recall_on_planted_wrong_edges"] for q in head_q]
    false_rates = [q["false_quarantine_rate"] for q in head_q]
    h4 = all(isinstance(r, int | float) and r >= 0.7 for r in recalls) and all(
        f is None or (isinstance(f, int | float) and f <= 0.1) for f in false_rates
    )
    head_breaks = [b for b in breaks if b["arm"] == HEADLINE.value and int(str(b["round"])) > 0]
    if not head_breaks:
        raise ValueError(f"no per-round break rows for {HEADLINE.value}")
    worst = max(int(str(b["newly_broken"])) / int(str(b["correct"] or 1)) for b in head_breaks)
    h5 = worst <= 0.02
    wrong = {
        seed: (wrong_rate(rows, HEADLINE.value, seed, 0), wrong_rate(rows, HEADLINE.value, seed, final))
        for seed in seeds
    }
    h6 = all(end <= 0.6 * start for start, end in wrong.values())
    reach = {seed: gapfill_reach(rows, seed, final) for seed in seeds}
    h7 = all(reached > 0 and ingested / reached >= 0.6 for reached, ingested in reach.values())
    against_v1 = [_pick(pairs, HEADLINE.value, MendPolicy.FULL_V1_RULE.value, seed) for seed in seeds]
    h8 = sum(_beats(row) for row in against_v1) >= 2
    return [
        {
            "id": "H1'",
            "claim": "the full Mend beats the frozen graph on the same held-out questions, every seed",
            "rule": H1_RULE,
            "per_seed": [
                {"seed": s, "delta_points": r["delta_points"], "p_value": r["p_value"]}
                for s, r in zip(seeds, head, strict=True)
            ],
            "verdict": "PASS" if h1 else "FAIL",
        },
        {
            "id": "H2'",
            "claim": "neither random control beats the frozen graph",
            "rule": H2_RULE,
            "per_arm": {
                arm: [
                    {"seed": s, "delta_points": r["delta_points"], "p_value": r["p_value"]}
                    for s, r in zip(seeds, per_arm, strict=True)
                ]
                for arm, per_arm in controls.items()
            },
            "verdict": "PASS" if h2 else "FAIL",
        },
        {
            "id": "H3'",
            "claim": "the plain-store arm is flat across rounds",
            "rule": H3_RULE,
            "note": "flat by construction: it is scored once per seed and cannot learn",
            "accuracy_per_seed": {str(s): round(next(iter(per.values())), 4) for s, per in plain.items()},
            "verdict": "PASS" if h3 else "FAIL",
        },
        {
            "id": "H4'",
            "claim": "quarantine recall on planted wrong edges >= 0.7 with false-quarantine rate <= 0.1",
            "rule": H4_RULE,
            "recall_per_seed": recalls,
            "false_quarantine_rate_per_seed": false_rates,
            "verdict": "PASS" if h4 else "FAIL",
        },
        {
            "id": "H5'",
            "claim": "net regressions on previously-correct held-out questions <= 2% per round",
            "rule": H5_RULE,
            "worst_round_break_share": round(worst, 4),
            "verdict": "PASS" if h5 else "FAIL",
        },
        {
            "id": "H6'",
            "claim": "the held-out wrong-answer rate falls by at least 40%",
            "rule": H6_RULE,
            "per_seed": {
                str(s): {"round_0": round(start, 4), "round_n": round(end, 4)} for s, (start, end) in wrong.items()
            },
            "verdict": "PASS" if h6 else "FAIL",
        },
        {
            "id": "H7'",
            "claim": "gap-fill ingests most of what its own rule reaches",
            "rule": H7_RULE,
            "per_seed": {
                str(s): {"reached": reached, "ingested": ingested} for s, (reached, ingested) in reach.items()
            },
            "verdict": "PASS" if h7 else "FAIL",
        },
        {
            "id": "H8'",
            "claim": "the run-2 update and gap-fill rules beat the run-1 rules on the same data",
            "rule": H8_RULE,
            "per_seed": [
                {"seed": s, "delta_points": r["delta_points"], "p_value": r["p_value"]}
                for s, r in zip(seeds, against_v1, strict=True)
            ],
            "verdict": "PASS" if h8 else "FAIL",
        },
    ]


CHANGES_DESIGN_V2 = (
    "One row per seed and round, with the change counts of every run-2 arm side by side: what the Mend planned "
    "that round from that arm's own graph, what the arm applied, and what it promoted, retired or ingested. Each "
    "random control plans under the same update rule as full_v2 and applies exactly as many changes as the Mend "
    "planned in that same round of that same arm, of the one mechanism it controls and no other (INV6, checked "
    "before any of these files is written)."
)
PAIRED_DESIGN = (
    "Every held-out question answered by two arms on the same seed at the last round, counted as a pair: both "
    "correct, one correct, or neither. The p-value is a two-sided exact McNemar test on the discordant pairs. This "
    "replaces run 1's test, which compared a per-seed delta against the spread between seeds at round 0."
)
CAPTURED_DESIGN = (
    "How much of the repairable damage the full arm repaired. The denominator is the oracle ladder on the same "
    "data: the held-out accuracy of a graph with every planted wrong edge quarantined and every withheld edge "
    "ingested, minus round 0. The numerator is what full_v2 actually gained. Run 1 captured 4% of its reachable "
    "gain and nothing on the page said so."
)
HYPOTHESES_DESIGN = (
    "The eight hypotheses preregistered in PRD section 3.2 before any of run 2 was built, decided from this run's "
    "curve, paired held-out verdicts, non-regression rows and quarantine report. A failed hypothesis is published "
    "as failed, beside run 1's."
)


def main() -> int:
    rows = rows_of(CURVE_V2)
    require_v2(rows)
    run_id = run_id_of(rows)
    print(f"run {run_id} on data {V2}: INV6 holds for {check_inv6(rows)} recorded control rounds")
    final = last_round(rows)
    seeds = seeds_of(rows)
    breaks = non_regression(rows, run_id, RUN2_ARMS)
    quarantines = quarantine_report(rows, run_id, RUN2_ARMS, V2)
    pairs = paired_rows(run_id, seeds, final)
    captured = captured_share(rows, oracle_rows(), seeds, final)
    verdicts = hypotheses(rows, breaks, quarantines, pairs, final)
    written = [
        write_chart(rows, arms=RUN2_ARMS, name="curve_v2.svg"),
        evidence.write(evidence.make("non_regression_v2", NON_REGRESSION_DESIGN, breaks)),
        evidence.write(evidence.make("quarantine_v2", QUARANTINE_DESIGN, quarantines)),
        evidence.write(evidence.make("mechanisms_v2", MECHANISMS_DESIGN, mechanism_table(rows, final, RUN2_ARMS))),
        evidence.write(evidence.make("changes_v2", CHANGES_DESIGN_V2, change_counts(rows, RUN2_ARMS))),
        evidence.write(evidence.make("paired_v2", PAIRED_DESIGN, pairs)),
        evidence.write(evidence.make("captured_share_v2", CAPTURED_DESIGN, captured)),
        evidence.write(evidence.make("hypotheses_v2", HYPOTHESES_DESIGN, verdicts)),
    ]
    written.append(manifest.write(tuple(seeds), run_id, name="run_manifest_v2.json", data_version=V2))
    for path in written:
        print(f"{path} sha256={evidence.digest(path)}")
    for row in captured:
        print(f"seed {row['seed']}: captured {row['captured_share']} of {row['reachable_points']} reachable points")
    for verdict in verdicts:
        print(f"{verdict['id']} {verdict['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
