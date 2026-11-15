import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from trailmend.eval import chart, curve, evidence, manifest, quarantine, regression
from trailmend.eval.run import ARMS
from trailmend.loop.journal import RUNS_DIR
from trailmend.loop.policy import MendPolicy, mechanisms

PLAIN = "plain_store"
H1_MARGIN_RULE = "accuracy(round N) - accuracy(round 0) > the round-0 spread across seeds, for every seed"
H2_RULE = "for each random control and each seed, accuracy(round N) - accuracy(round 0) <= the round-0 spread"
H3_RULE = "the plain-store accuracy is identical at every round, for every seed"
H4_RULE = "recall on planted wrong edges >= 0.7 for every seed, and false-quarantine rate <= 0.1 where defined"
H5_RULE = "newly_broken / correct <= 0.02 in the worst round after round 0, full arm"


def rows_of(path: Path = curve.CURVE) -> tuple[Mapping[str, object], ...]:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist; run trailmend.eval.run first")
    return tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)


def _accuracy(row: Mapping[str, object]) -> float:
    held_out = row.get("held_out")
    if not isinstance(held_out, dict):
        raise TypeError(f"row for {row.get('arm')} round {row.get('round')} has no held-out score")
    value = cast("dict[str, object]", held_out)["accuracy"]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"unreadable accuracy {value!r}")
    return float(value)


def _at(rows: Sequence[Mapping[str, object]], arm: str, seed: int, round_index: int) -> float:
    for row in rows:
        if row.get("arm") == arm and row.get("seed") == seed and row.get("round") == round_index:
            return _accuracy(row)
    raise KeyError(f"no curve row for arm {arm} seed {seed} round {round_index}")


def seeds_of(rows: Sequence[Mapping[str, object]]) -> tuple[int, ...]:
    return tuple(sorted({int(str(row["seed"])) for row in rows}))


def last_round(rows: Sequence[Mapping[str, object]]) -> int:
    return max(int(str(row["round"])) for row in rows)


def write_chart(rows: Sequence[Mapping[str, object]], directory: Path = evidence.EVIDENCE_DIR) -> Path:
    series = [
        chart.Series(arm.value, chart.mean_by_round(rows, arm.value))
        for arm in ARMS
        if chart.mean_by_round(rows, arm.value)
    ]
    plain = chart.mean_by_round(rows, PLAIN)
    if plain:
        series.append(chart.Series(PLAIN, plain))
    path = directory / "curve.svg"
    path.write_text(chart.render(series, "Held-out accuracy by round, mean of 3 seeds", low=0.0, high=1.0))
    return path


def require_tape(run_id: str, root: Path = RUNS_DIR) -> Path:
    path = root / run_id / "heldout.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"{run_id} recorded curve rows but no held-out tape at {path}")
    return path


def non_regression(rows: Sequence[Mapping[str, object]], run_id: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for seed in seeds_of(rows):
        for arm in ARMS:
            run = f"{run_id}-s{seed}-{arm.value}"
            require_tape(run)
            out.extend(regression.rows(run, seed, arm.value))
    return out


def quarantine_report(rows: Sequence[Mapping[str, object]], run_id: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for seed in seeds_of(rows):
        for arm in ARMS:
            run = f"{run_id}-s{seed}-{arm.value}"
            require_tape(run)
            out.append(quarantine.report(seed, arm.value, run))
    return out


def mechanism_table(rows: Sequence[Mapping[str, object]], final: int) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for arm in ARMS:
        parts = mechanisms(arm)
        deltas = [_at(rows, arm.value, seed, final) - _at(rows, arm.value, seed, 0) for seed in seeds_of(rows)]
        out.append(
            {
                "arm": arm.value,
                "reweight": parts.reweight,
                "quarantine": parts.quarantine,
                "promote": parts.promote,
                "gapfill": parts.gapfill,
                "round_0_mean": round(
                    sum(_at(rows, arm.value, seed, 0) for seed in seeds_of(rows)) / len(seeds_of(rows)), 4
                ),
                "round_n_mean": round(
                    sum(_at(rows, arm.value, seed, final) for seed in seeds_of(rows)) / len(seeds_of(rows)), 4
                ),
                "delta_per_seed": [round(d, 4) for d in deltas],
                "delta_mean": round(sum(deltas) / len(deltas), 4),
            }
        )
    return out


def hypotheses(
    rows: Sequence[Mapping[str, object]],
    breaks: Sequence[Mapping[str, object]],
    quarantines: Sequence[Mapping[str, object]],
    final: int,
) -> list[dict[str, object]]:
    if not breaks or not quarantines:
        raise ValueError("H4 and H5 cannot be decided without per-round break rows and quarantine reports")
    seeds = seeds_of(rows)
    baseline = [_at(rows, MendPolicy.FULL.value, seed, 0) for seed in seeds]
    spread = max(baseline) - min(baseline)
    full_deltas = {
        seed: _at(rows, MendPolicy.FULL.value, seed, final) - _at(rows, MendPolicy.FULL.value, seed, 0)
        for seed in seeds
    }
    h1 = all(delta > spread for delta in full_deltas.values())
    randoms = {
        arm.value: {seed: _at(rows, arm.value, seed, final) - _at(rows, arm.value, seed, 0) for seed in seeds}
        for arm in (MendPolicy.RANDOM_REWEIGHT, MendPolicy.RANDOM_QUARANTINE)
    }
    h2 = all(delta <= spread for arm in randoms.values() for delta in arm.values())
    plain = {seed: {r: _at(rows, PLAIN, seed, r) for r in range(final + 1)} for seed in seeds}
    h3 = all(len(set(per_round.values())) == 1 for per_round in plain.values())
    full_q = [q for q in quarantines if q["arm"] == MendPolicy.FULL.value]
    recalls = [q["recall_on_planted_wrong_edges"] for q in full_q]
    false_rates = [q["false_quarantine_rate"] for q in full_q]
    h4 = all(isinstance(r, int | float) and r >= 0.7 for r in recalls) and all(
        f is None or (isinstance(f, int | float) and f <= 0.1) for f in false_rates
    )
    full_breaks = [b for b in breaks if b["arm"] == MendPolicy.FULL.value and int(str(b["round"])) > 0]
    worst = max((int(str(b["newly_broken"])) / int(str(b["correct"] or 1)) for b in full_breaks), default=0.0)
    h5 = worst <= 0.02
    return [
        {
            "id": "H1",
            "claim": "held-out accuracy after round N exceeds round 0 by more than the seed spread, every seed",
            "rule": H1_MARGIN_RULE,
            "round_0_spread": round(spread, 4),
            "full_delta_per_seed": {str(s): round(d, 4) for s, d in full_deltas.items()},
            "verdict": "PASS" if h1 else "FAIL",
        },
        {
            "id": "H2",
            "claim": "random controls do not rise beyond seed spread",
            "rule": H2_RULE,
            "round_0_spread": round(spread, 4),
            "delta_per_arm": {arm: {str(s): round(d, 4) for s, d in per.items()} for arm, per in randoms.items()},
            "verdict": "PASS" if h2 else "FAIL",
        },
        {
            "id": "H3",
            "claim": "the plain-store arm is flat across rounds",
            "rule": H3_RULE,
            "note": "flat by construction: it is scored once per seed and cannot learn",
            "accuracy_per_seed": {str(s): round(next(iter(per.values())), 4) for s, per in plain.items()},
            "verdict": "PASS" if h3 else "FAIL",
        },
        {
            "id": "H4",
            "claim": "quarantine recall on planted wrong edges >= 0.7 with false-quarantine rate <= 0.1",
            "rule": H4_RULE,
            "recall_per_seed": recalls,
            "false_quarantine_rate_per_seed": false_rates,
            "verdict": "PASS" if h4 else "FAIL",
        },
        {
            "id": "H5",
            "claim": "net regressions on previously-correct held-out questions <= 2% per round",
            "rule": H5_RULE,
            "worst_round_break_share": round(worst, 4),
            "verdict": "PASS" if h5 else "FAIL",
        },
    ]


def main() -> int:
    rows = rows_of()
    run_id = str(rows[0]["run_id"])
    final = last_round(rows)
    seeds = seeds_of(rows)
    breaks = non_regression(rows, run_id)
    quarantines = quarantine_report(rows, run_id)
    table = mechanism_table(rows, final)
    verdicts = hypotheses(rows, breaks, quarantines, final)
    written = [
        write_chart(rows),
        evidence.write(
            evidence.make(
                "non_regression",
                "Per round, from evidence/runs/<run>/heldout.jsonl: which held-out questions turned correct and "
                "which turned away from correct, and for each break the receipts written that round that touched "
                "an edge on that question's previous correct path. A break with no such receipt means the path "
                "changed for another reason, such as a cheaper rival answer appearing.",
                breaks,
            )
        ),
        evidence.write(
            evidence.make(
                "quarantine",
                "Every quarantine receipt in a run against the planted faults for that seed. Precision counts "
                "quarantined edges that a fault introduced; recall counts planted wrong edges quarantined; the "
                "false-quarantine rate counts quarantined edges that are in the truth graph. Gap-fill is counted "
                "the same way: an ingest is spurious if the edge it added is not in the truth graph.",
                quarantines,
            )
        ),
        evidence.write(
            evidence.make(
                "mechanisms",
                "One row per arm: which mechanisms it runs and what held-out accuracy it reached from round 0 to "
                "round N, per seed and as a mean. Arms share seeds, splits, rounds and the same plan of changes; "
                "they differ only in which of those changes they apply.",
                table,
            )
        ),
        evidence.write(
            evidence.make(
                "hypotheses",
                "The five hypotheses preregistered in PRD section 3, decided from the curve, the non-regression "
                "rows and the quarantine report of this run. A failed hypothesis is published as failed.",
                verdicts,
            )
        ),
    ]
    written.append(manifest.write(seeds, run_id))
    for path in written:
        print(f"{path} sha256={evidence.digest(path)}")
    for verdict in verdicts:
        print(f"{verdict['id']} {verdict['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
