import json
from collections.abc import Mapping, Sequence
from itertools import pairwise
from pathlib import Path
from typing import cast

from trailmend.eval import evidence, paired
from trailmend.eval.regression import as_int, by_round, edge_of, receipts_of
from trailmend.loop.journal import RUNS_DIR
from trailmend.loop.policy import MendPolicy
from trailmend.loop.tape import Tape
from trailmend.metaqa.ladder import REACHABLE_RUNG
from trailmend.metaqa.run import CURVE

HEADLINE = MendPolicy.FULL_V2.value
REFERENCE = MendPolicy.FROZEN.value
CONTROL = MendPolicy.RANDOM_REWEIGHT.value
PLAIN = "plain_store"
ALPHA = 0.05
CORRECT = "correct"
M1_RULE = (
    "full_v2 beats frozen on the same held-out questions at round 5 under a two-sided exact McNemar test at "
    "p < 0.05, with a gain of at least 2.0 points of Hits@1, on all 3 seeds"
)
M2_RULE = "random_reweight does not beat frozen under the same paired test on any seed"
M3_RULE = "the plain-store Hits@1 is identical at every round, for every seed"
M4_RULE = "the held-out wrong-answer rate of full_v2 falls by at least 40% from round 0 to round 5, every seed"
M5_RULE = "at most 2% of the held-out hits after one round are not hits after the next, every round and seed, full_v2"


def rows_of(path: Path = CURVE) -> tuple[Mapping[str, object], ...]:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist; run trailmend.metaqa.run first")
    return tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)


def run_id_of(rows: Sequence[Mapping[str, object]]) -> str:
    found = {str(row["run_id"]) for row in rows}
    if len(found) != 1:
        raise ValueError(f"{CURVE} mixes runs {sorted(found)}; an analysis decides one run")
    return found.pop()


def held(rows: Sequence[Mapping[str, object]], arm: str, seed: int, round_index: int) -> Mapping[str, object]:
    for row in rows:
        if row.get("arm") == arm and row.get("seed") == seed and row.get("round") == round_index:
            score = row.get("held_out")
            if not isinstance(score, dict):
                raise TypeError(f"{arm} seed {seed} round {round_index} has no held-out score")
            return cast("dict[str, object]", score)
    raise KeyError(f"no MetaQA row for arm {arm} seed {seed} round {round_index}")


def metric(rows: Sequence[Mapping[str, object]], arm: str, seed: int, round_index: int, name: str) -> float:
    value = held(rows, arm, seed, round_index)[name]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"unreadable {name} {value!r}")
    return float(value)


def check_inv6(rows: Sequence[Mapping[str, object]]) -> int:
    checked = 0
    for row in rows:
        if row.get("arm") != CONTROL or as_int(row["round"], "round") == 0:
            continue
        planned, applied = as_int(row["planned_reweights"], "planned"), as_int(row["applied_reweights"], "applied")
        if planned != applied or as_int(row["applied_quarantines"], "quarantines") != 0:
            raise ValueError(f"INV6 broken on seed {row.get('seed')} round {row.get('round')}: {planned} != {applied}")
        if as_int(row["gapfill_facts"], "gapfill_facts") != 0:
            raise ValueError(f"the random control ingested documents on seed {row.get('seed')}")
        checked += 1
    if checked == 0:
        raise ValueError("no random-control round was recorded, so INV6 cannot be checked")
    return checked


def breaks(run_id: str, seed: int, root: Path = RUNS_DIR) -> list[dict[str, object]]:
    name = f"{run_id}-s{seed}-{HEADLINE}"
    rounds = by_round(Tape.for_run(name, root).rounds())
    receipts = receipts_of(name, root)
    if not rounds or not receipts:
        raise ValueError(f"{name} has no held-out tape or no receipts, so its breaks cannot be traced")
    out: list[dict[str, object]] = []
    ordered = sorted(rounds)
    for previous_index, round_index in pairwise(ordered):
        before, after = rounds[previous_index], rounds[round_index]
        were_hits = sorted(q for q, a in before.items() if a.verdict == CORRECT)
        broken = [q for q in were_hits if after[q].verdict != CORRECT]
        fixed = sorted(q for q, a in after.items() if a.verdict == CORRECT and before[q].verdict != CORRECT)
        touched_now = {edge_of(r): str(r["receipt_id"]) for r in receipts if as_int(r["round"], "round") == round_index}
        traced: dict[str, list[str]] = {}
        for question in broken:
            edges = {hop for answer in (before[question], after[question]) for path in answer.paths for hop in path}
            found = sorted(touched_now[edge] for edge in edges if edge in touched_now)
            if found:
                traced[question] = found
        out.append(
            {
                "seed": seed,
                "arm": HEADLINE,
                "round": round_index,
                "hits_before": len(were_hits),
                "stayed_hits": len(were_hits) - len(broken),
                "newly_broken": len(broken),
                "newly_fixed": len(fixed),
                "breaks_traced_to_a_receipt": len(traced),
                "breaks_untraced": len(broken) - len(traced),
                "broken_question_ids": broken,
                "receipts_blamed": traced,
            }
        )
    return out


def ladder_rows(path: Path = evidence.EVIDENCE_DIR / "oracle_metaqa.json") -> tuple[Mapping[str, object], ...]:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist; the ladder runs at the end of trailmend.metaqa.run")
    rows = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8"))).get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path} records no ladder rows")
    return tuple(cast("list[Mapping[str, object]]", rows))


def _rung(ladder: Sequence[Mapping[str, object]], seed: int, rung: str) -> float:
    for row in ladder:
        if row["seed"] == seed and row["rung"] == rung:
            return float(str(cast("dict[str, object]", row["held_out"])["hits_at_1"]))
    raise KeyError(f"the MetaQA ladder has no {rung} rung for seed {seed}")


def captured(
    rows: Sequence[Mapping[str, object]], ladder: Sequence[Mapping[str, object]], seeds: Sequence[int], final: int
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for seed in seeds:
        start = metric(rows, HEADLINE, seed, 0, "hits_at_1")
        end = metric(rows, HEADLINE, seed, final, "hits_at_1")
        reachable = _rung(ladder, seed, REACHABLE_RUNG) - _rung(ladder, seed, "g0")
        if reachable <= 0:
            raise ValueError(f"seed {seed}: the ladder leaves no reachable gain to capture")
        out.append(
            {
                "seed": seed,
                "arm": HEADLINE,
                "round_0": round(start, 4),
                "round_n": round(end, 4),
                "gained_points": round(100 * (end - start), 2),
                "reachable_points": round(100 * reachable, 2),
                "captured_share": round((end - start) / reachable, 4),
            }
        )
    return out


def _beats(row: Mapping[str, object], points: float = 0.0) -> bool:
    return float(str(row["p_value"])) < ALPHA and float(str(row["delta_points"])) >= points


def hypotheses(
    rows: Sequence[Mapping[str, object]],
    pairs: Sequence[Mapping[str, object]],
    broken: Sequence[Mapping[str, object]],
    seeds: Sequence[int],
    final: int,
) -> list[dict[str, object]]:
    if not pairs or not broken:
        raise ValueError("M1 to M5 cannot be decided without paired rows and break rows")
    head = [row for row in pairs if row["arm"] == HEADLINE]
    control = [row for row in pairs if row["arm"] == CONTROL]
    if len(head) != len(seeds) or len(control) != len(seeds):
        raise ValueError("every seed needs a paired row for full_v2 and for random_reweight")
    plain = {seed: {metric(rows, PLAIN, seed, r, "hits_at_1") for r in range(final + 1)} for seed in seeds}
    wrong = {
        seed: (metric(rows, HEADLINE, seed, 0, "wrong_rate"), metric(rows, HEADLINE, seed, final, "wrong_rate"))
        for seed in seeds
    }
    worst = max(as_int(b["newly_broken"], "newly_broken") / max(1, as_int(b["hits_before"], "hits")) for b in broken)

    def per_seed(found: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
        return [{"seed": r["seed"], "delta_points": r["delta_points"], "p_value": r["p_value"]} for r in found]

    return [
        {
            "id": "M1",
            "claim": "on MetaQA the full Mend beats the frozen graph on the same held-out questions, every seed",
            "rule": M1_RULE,
            "per_seed": per_seed(head),
            "verdict": "PASS" if all(_beats(row, 2.0) for row in head) else "FAIL",
        },
        {
            "id": "M2",
            "claim": "random reweighting does not beat the frozen graph",
            "rule": M2_RULE,
            "per_seed": per_seed(control),
            "verdict": "PASS" if all(not _beats(row) for row in control) else "FAIL",
        },
        {
            "id": "M3",
            "claim": "the plain-store arm is flat across rounds",
            "rule": M3_RULE,
            "note": "flat by construction: it is scored once per seed and cannot learn",
            "hits_at_1_per_seed": {str(seed): round(min(values), 4) for seed, values in plain.items()},
            "verdict": "PASS" if all(len(values) == 1 for values in plain.values()) else "FAIL",
        },
        {
            "id": "M4",
            "claim": "the held-out wrong-answer rate falls by at least 40%",
            "rule": M4_RULE,
            "per_seed": {str(s): {"round_0": round(a, 4), "round_n": round(b, 4)} for s, (a, b) in wrong.items()},
            "verdict": "PASS" if all(end <= 0.6 * start for start, end in wrong.values()) else "FAIL",
        },
        {
            "id": "M5",
            "claim": "at most 2% of held-out hits are lost from one round to the next",
            "rule": M5_RULE,
            "worst_round_break_share": round(worst, 4),
            "verdict": "PASS" if worst <= 0.02 else "FAIL",
        },
    ]


PAIRED_DESIGN = (
    "MetaQA: every held-out question answered by two arms on the same seed at the last round, counted as a pair on "
    "Hits@1. The p-value is a two-sided exact McNemar test on the discordant pairs."
)
CAPTURED_DESIGN = (
    "MetaQA: what full_v2 gained in held-out Hits@1 from round 0 to the last round, over what the oracle ladder says "
    "was reachable on the same seed (every withheld triple ingested and every contradicted and recoverable fault "
    "repaired, minus round 0)."
)
BREAKS_DESIGN = (
    "MetaQA, full_v2, per round from the held-out tape: how many hits stayed hits, which broke, and for each break "
    "the receipts written that round on an edge of the answer path before or after it."
)
HYPOTHESES_DESIGN = (
    "The five MetaQA hypotheses preregistered in PRD section 3.3 before any MetaQA question was answered through "
    "HydraDB, decided from this run's rows, paired held-out verdicts and break rows. A failed one stays published."
)


def main() -> int:
    rows = rows_of()
    run_id = run_id_of(rows)
    seeds = tuple(sorted({as_int(row["seed"], "seed") for row in rows}))
    final = max(as_int(row["round"], "round") for row in rows)
    print(f"metaqa run {run_id}: INV6 holds for {check_inv6(rows)} recorded control rounds")
    pairs = [paired.row(run_id, seed, arm, REFERENCE, final) for seed in seeds for arm in (HEADLINE, CONTROL)]
    broken = [row for seed in seeds for row in breaks(run_id, seed)]
    shares = captured(rows, ladder_rows(), seeds, final)
    verdicts = hypotheses(rows, pairs, broken, seeds, final)
    for claim, design, payload in (
        ("paired_metaqa", PAIRED_DESIGN, pairs),
        ("captured_share_metaqa", CAPTURED_DESIGN, shares),
        ("non_regression_metaqa", BREAKS_DESIGN, broken),
        ("hypotheses_metaqa", HYPOTHESES_DESIGN, verdicts),
    ):
        path = evidence.write(evidence.make(claim, design, payload))
        print(f"{path} sha256={evidence.digest(path)}")
    for verdict in verdicts:
        print(f"{verdict['id']} {verdict['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
