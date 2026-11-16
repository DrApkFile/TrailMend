from collections.abc import Mapping, Sequence

from trailmend.data import dataset
from trailmend.data.qtemplates import template
from trailmend.eval import curve, evidence, paired
from trailmend.eval.analyse import last_round, rows_of, seeds_of
from trailmend.eval.analyse_v2 import run_id_of
from trailmend.loop.journal import RUNS_DIR
from trailmend.loop.policy import MendPolicy
from trailmend.loop.tape import Tape

WEIGHTED = MendPolicy.FULL_V2.value
UNWEIGHTED = MendPolicy.FULL_UNWEIGHTED.value
FROZEN = MendPolicy.FROZEN.value
DESIGN = (
    "The full Mend with a search that ignores cost (fewest hops) against run 2's full Mend that searches on cost, on "
    "the same seeds, data, constants and held-out questions. It was run at a later commit than run 2, so it is an "
    "extension and enters no preregistered verdict. If its frozen arm fails to reproduce run 2, the mismatch is "
    "published as provisional and no paired comparison is made. Rows of kind `paired` count every held-out question "
    "as a pair (two-sided exact McNemar). Rows of kind `by_answer_kind` split held-out accuracy by whether the "
    "question's template has one answer or a set, at round 0 and at the last round, because the two searches differ "
    "most there: with document-derived costs a set of true answers rarely ties, so the weighted search returns the "
    "cheapest member and misses the set, while the hop-count search returns every answer at the same depth."
)


def require_same_frozen(extension: Sequence[Mapping[str, object]], run_two: Sequence[Mapping[str, object]]) -> int:
    checked = 0
    for row in extension:
        if row.get("arm") != FROZEN:
            continue
        match = [
            r
            for r in run_two
            if r.get("arm") == FROZEN and r.get("seed") == row.get("seed") and r.get("round") == row.get("round")
        ]
        if len(match) != 1 or match[0]["held_out"] != row["held_out"]:
            raise ValueError(f"the extension's frozen arm does not reproduce run 2 on seed {row.get('seed')}")
        checked += 1
    if checked == 0:
        raise ValueError("the extension recorded no frozen rows to check against run 2")
    return checked


def by_kind(run_name: str, round_index: int) -> dict[str, tuple[int, int]]:
    tally: dict[str, list[int]] = {"single_answer": [0, 0], "answer_set": [0, 0]}
    for answer in Tape.for_run(run_name, RUNS_DIR).rounds():
        if answer.round_index != round_index:
            continue
        kind = "single_answer" if template(answer.template).single_answer else "answer_set"
        tally[kind][0] += answer.verdict == paired.CORRECT
        tally[kind][1] += 1
    return {kind: (right, total) for kind, (right, total) in tally.items()}


def baseline_diagnostics(
    extension: Sequence[Mapping[str, object]], run_two: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for seed in seeds_of(extension):
        built = dataset.build(seed, data_version="v2")
        keys = {(edge.src, edge.rel_type.value, edge.dst) for edge in built.graph.edges}
        for label, rows in (("run_two", run_two), ("extension", extension)):
            run_id = run_id_of(rows)
            baseline = next(r for r in rows if r["arm"] == FROZEN and r["seed"] == seed and r["round"] == 0)
            answers = [a for a in Tape.for_run(f"{run_id}-s{seed}-{FROZEN}").rounds() if a.round_index == 0]
            extra = sorted(
                {
                    (h.src, h.rel_type, h.dst)
                    for a in answers
                    for path in a.paths
                    for h in path
                    if (h.src, h.rel_type, h.dst) not in keys
                }
            )
            out.append(
                {
                    "kind": "baseline_diagnostic",
                    "seed": seed,
                    "source": label,
                    "run_id": run_id,
                    "held_out": baseline["held_out"],
                    "edges_outside_g0": extra,
                }
            )
    return out


def main() -> int:
    extension = rows_of(curve.CURVE_V2_UNWEIGHTED)
    run_two = rows_of(curve.CURVE_V2)
    extension_run, run_two_id = run_id_of(extension), run_id_of(run_two)
    try:
        checked = require_same_frozen(extension, run_two)
    except ValueError as error:
        reason = str(error)
        diagnostic: list[dict[str, object]] = [
            {"kind": "comparability", "classification": "provisional", "comparable": False, "reason": reason}
        ]
        diagnostic.extend(baseline_diagnostics(extension, run_two))
        path = evidence.write(evidence.make("paired_v2_unweighted", DESIGN, diagnostic))
        print(f"{path}: provisional; {reason}; no paired comparison published")
        return 0
    print(f"frozen reproduces run 2 on {checked} rows")
    final = last_round(extension)
    rows: list[dict[str, object]] = []
    for seed in seeds_of(extension):
        unweighted = f"{extension_run}-s{seed}-{UNWEIGHTED}"
        weighted = f"{run_two_id}-s{seed}-{WEIGHTED}"
        frozen = f"{run_two_id}-s{seed}-{FROZEN}"
        for reference, name in ((WEIGHTED, weighted), (FROZEN, frozen)):
            result = paired.compare(paired.correct_at(unweighted, final), paired.correct_at(name, final))
            rows.append(
                {
                    "kind": "paired",
                    "seed": seed,
                    "arm": UNWEIGHTED,
                    "reference": reference,
                    "round": final,
                    "n": result.n,
                    "only_arm_correct": result.only_first,
                    "only_reference_correct": result.only_second,
                    "delta_points": round(result.delta_points, 4),
                    "p_value": round(result.p_value, 6),
                }
            )
        for arm, name in ((UNWEIGHTED, unweighted), (WEIGHTED, weighted)):
            for round_index in (0, final):
                for kind, (right, total) in by_kind(name, round_index).items():
                    rows.append(
                        {
                            "kind": "by_answer_kind",
                            "seed": seed,
                            "arm": arm,
                            "round": round_index,
                            "answer_kind": kind,
                            "correct": right,
                            "n": total,
                            "accuracy": round(right / total, 4) if total else None,
                        }
                    )
    path = evidence.write(evidence.make("paired_v2_unweighted", DESIGN, rows))
    print(f"{path} sha256={evidence.digest(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
