from collections.abc import Mapping, Sequence

from trailmend.data import dataset
from trailmend.data.faultmodel import V2
from trailmend.eval import curve, evidence, paired
from trailmend.eval.analyse import last_round, rows_of, seeds_of
from trailmend.eval.analyse_unweighted import by_kind
from trailmend.eval.analyse_v2 import run_id_of
from trailmend.loop.policy import MendPolicy
from trailmend.loop.tape import Tape

CLAIM = "replication_v2_clean"
FULL = MendPolicy.FULL_V2.value
FROZEN = MendPolicy.FROZEN.value
UNWEIGHTED = MendPolicy.FULL_UNWEIGHTED.value
COMPLETE_ROWS = 144
DESIGN = (
    "A clean replication of run 2: the same Mend config digest, data version, seeds and arms, plus `full_unweighted` "
    "and `plain_store`, on a HydraDB emptied before the run, written to its own curve file. Run 2 stays published "
    "unchanged; this file decides nothing preregistered. Rows of kind `against_run_two` compare held-out results per "
    "seed at round 0 and the last round with run 2's recorded rows. Rows of kind `outside_g0` list edges on the clean "
    "frozen arm's round-0 answer paths that are not in the seed's ingested graph (run 2's had some; a clean graph "
    "should have none). Rows of kind `paired` count every held-out question as a pair at the last round (two-sided "
    "exact McNemar): `full_v2` against `frozen`, and `full_unweighted` against `full_v2` on the same clean graph, "
    "which replaces the provisional unweighted comparison. Rows of kind `by_answer_kind` split held-out accuracy by "
    "single answer or answer set for the two searches."
)


def _row(rows: Sequence[Mapping[str, object]], arm: str, seed: int, round_index: int) -> Mapping[str, object]:
    found = [r for r in rows if r["arm"] == arm and r["seed"] == seed and r["round"] == round_index]
    if len(found) != 1:
        raise ValueError(f"expected one {arm} row for seed {seed} round {round_index}, found {len(found)}")
    return found[0]


def _held(row: Mapping[str, object]) -> Mapping[str, object]:
    held = row["held_out"]
    assert isinstance(held, Mapping)
    return held  # pyright: ignore[reportUnknownVariableType]


def against_run_two(
    clean: Sequence[Mapping[str, object]], run_two: Sequence[Mapping[str, object]], final: int
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for seed in seeds_of(clean):
        for arm in (FROZEN, FULL):
            for round_index in (0, final):
                mine = _held(_row(clean, arm, seed, round_index))
                theirs = _held(_row(run_two, arm, seed, round_index))
                out.append(
                    {
                        "kind": "against_run_two",
                        "seed": seed,
                        "arm": arm,
                        "round": round_index,
                        "clean_correct": mine["correct"],
                        "run_two_correct": theirs["correct"],
                        "n": mine["n"],
                        "clean_minus_run_two": int(str(mine["correct"])) - int(str(theirs["correct"])),
                    }
                )
    return out


def outside_g0(run_id: str, seeds: Sequence[int]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for seed in seeds:
        built = dataset.build(seed, data_version=V2)
        keys = {(edge.src, edge.rel_type.value, edge.dst) for edge in built.graph.edges}
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
        out.append({"kind": "outside_g0", "seed": seed, "run_id": run_id, "edges_outside_g0": extra})
    return out


def paired_rows(run_id: str, seeds: Sequence[int], final: int) -> list[dict[str, object]]:
    return [
        {"kind": "paired"} | paired.row(run_id, seed, arm, reference, final)
        for seed in seeds
        for arm, reference in ((FULL, FROZEN), (UNWEIGHTED, FULL))
    ]


def kind_rows(run_id: str, seeds: Sequence[int], final: int) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for seed in seeds:
        for arm in (UNWEIGHTED, FULL):
            for round_index in (0, final):
                for kind, (right, total) in by_kind(f"{run_id}-s{seed}-{arm}", round_index).items():
                    out.append(
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
    return out


def main() -> int:
    clean = rows_of(curve.CURVE_V2_CLEAN)
    if len(clean) != COMPLETE_ROWS:
        raise SystemExit(f"{curve.CURVE_V2_CLEAN} has {len(clean)} rows, a complete replication has {COMPLETE_ROWS}")
    run_two = rows_of(curve.CURVE_V2)
    run_id = run_id_of(clean)
    seeds = seeds_of(clean)
    final = last_round(clean)
    rows = [
        {"kind": "runs", "clean_run_id": run_id, "run_two_id": run_id_of(run_two), "rounds": final, "seeds": seeds},
        *against_run_two(clean, run_two, final),
        *outside_g0(run_id, seeds),
        *paired_rows(run_id, seeds, final),
        *kind_rows(run_id, seeds, final),
    ]
    path = evidence.write(evidence.make(CLAIM, DESIGN, rows))
    print(f"{path} sha256={evidence.digest(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
