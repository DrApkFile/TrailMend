import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from trailmend.core.config import load_search_config
from trailmend.core.model import EdgeKey, SearchConfig
from trailmend.data import dataset
from trailmend.data.qtemplates import template
from trailmend.data.questions import Question, adjacency
from trailmend.eval import anatomy, evidence, measuring, oracle, target
from trailmend.eval.session import client_from_settings
from trailmend.graph.client import HydraClient
from trailmend.graph.ids import edge_id
from trailmend.graph.reset import reset_to_ingested
from trailmend.graph.state import state_from_row, write_state
from trailmend.loop.evaluate import Judged, judge_all, score
from trailmend.search.seed import build_index
from trailmend.settings import load_settings

CONFIG = Path("config/mend.toml")
RUNS = Path("evidence/runs")
SEEDS: tuple[int, ...] = (1, 7, 42)
ARM = "full"

ANATOMY_DESIGN = (
    "Every train question the full arm did not answer correctly, at round 0 and after the last recorded round, "
    "classified by what broke the path that should have carried the gold answer. The round-5 graph is reached by "
    "replaying the arm's own receipts onto a freshly loaded G0, so no judging and no new randomness is involved. "
    "Causes are decided in one order - planted wrong edge, missing edge, alias duplicate, conflated entity, tie, "
    "other - and every other cause that also applied to the same question is counted in overlaps."
)
ORACLE_DESIGN = (
    "A ladder of perfect repairs read straight from faults.json, each stage applied on top of the last, scored on "
    "held-out questions. It answers one question: what could any repair mechanism reach on this data? The first two "
    "rungs are the whole vocabulary this build has (quarantine, gap-fill); the last two are repairs no mechanism in "
    "this build can make, and the final rung is the truth graph itself."
)
RECOVERY_DESIGN = (
    "For each planted wrong edge, whether the edge it replaced is still reachable at all: present in G0, or in the "
    "withheld pool that gap-fill reads, or nowhere. Plus how many train questions walk each planted wrong edge at "
    "round 0, which is what blame concentration has to work with."
)


def replay(client: HydraClient, run_name: str) -> dict[str, int]:
    kinds: Counter[str] = Counter()
    for line in (RUNS / run_name / "receipts.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = cast("dict[str, Mapping[str, object]]", json.loads(line))
        before = state_from_row(row["before"])
        after = state_from_row(row["after"])
        write_state(client, before, after, edge_id(after.key.rel_type, after.key.src, after.key.dst))
        kinds[str(row["kind"])] += 1
    return dict(sorted(kinds.items()))


def _chosen(judged: Judged) -> set[EdgeKey]:
    return {edge for path in judged.paths for edge in path}


def anatomies(
    judged: Sequence[Judged], built: dataset.Dataset, facts: anatomy.FaultIndex
) -> tuple[anatomy.Anatomy, ...]:
    by_id: dict[str, Question] = {q.id: q for q in built.questions.questions}
    links = adjacency(built.truth)
    out: list[anatomy.Anatomy] = []
    for one in anatomy.failing(judged):
        question = by_id[one.question_id]
        truth_edges = anatomy.truth_path_edges(question, template(one.template).rel_path, links)
        out.append(anatomy.anatomy_of(one, truth_edges, facts))
    return tuple(out)


def anatomy_row(seed: int, point: str, judged: Sequence[Judged], found: Sequence[anatomy.Anatomy]) -> dict[str, object]:
    scored = score(judged)
    causes: Counter[str] = Counter(a.cause for a in found)
    overlaps: Counter[str] = Counter(also for a in found for also in a.also)
    return {
        "seed": seed,
        "point": point,
        "train_questions": scored.n,
        "correct": scored.correct,
        "accuracy": round(scored.accuracy, 4),
        "wrong": scored.wrong,
        "unreachable": scored.unreachable,
        "refused": scored.refused,
        "causes": {cause: causes.get(cause, 0) for cause in anatomy.CAUSES},
        "also_applied": dict(sorted(overlaps.items())),
        "wrong_edge_on_the_chosen_path": sum(a.wrong_edge_on_chosen_path for a in found),
        "true_edge_was_replaced": sum(a.true_edge_replaced for a in found),
        "by_template": dict(sorted(Counter(a.template for a in found).items())),
    }


def recovery_row(seed: int, built: dataset.Dataset, judged: Sequence[Judged]) -> dict[str, object]:
    in_g0 = {EdgeKey(e.src, e.rel_type.value, e.dst) for e in built.graph.edges}
    in_pool = {EdgeKey(e.src, e.rel_type.value, e.dst) for e in built.ingested.pool}
    wrong = built.ingested.faults.wrong_edges
    true_keys = [EdgeKey(f.src, f.rel_type.value, f.true_dst) for f in wrong]
    facts = anatomy.index_of(built.ingested.faults)
    touched: Counter[EdgeKey] = Counter()
    for one in judged:
        for key in _chosen(one) & facts.wrong_added:
            touched[key] += 1
    counts = sorted(touched.get(EdgeKey(f.src, f.rel_type.value, f.wrong_dst), 0) for f in wrong)
    by_kind: dict[str, dict[str, int]] = {}
    for fault in wrong:
        key = EdgeKey(fault.src, fault.rel_type.value, fault.true_dst)
        seen = by_kind.setdefault(
            fault.kind.value,
            {"planted": 0, "true_edge_still_in_g0": 0, "true_edge_in_the_gapfill_pool": 0, "true_edge_nowhere": 0},
        )
        seen["planted"] += 1
        if key in in_g0:
            seen["true_edge_still_in_g0"] += 1
        elif key in in_pool:
            seen["true_edge_in_the_gapfill_pool"] += 1
        else:
            seen["true_edge_nowhere"] += 1
    return {
        "seed": seed,
        "data_version": built.data_version,
        "planted_wrong_edges": len(wrong),
        "by_kind": dict(sorted(by_kind.items())),
        "true_edge_still_in_g0": sum(key in in_g0 for key in true_keys),
        "true_edge_in_the_gapfill_pool": sum(key in in_pool for key in true_keys),
        "true_edge_nowhere": sum(key not in in_g0 and key not in in_pool for key in true_keys),
        "train_questions_walking_a_planted_wrong_edge_at_round_0": sum(counts),
        "questions_per_planted_wrong_edge": counts,
        "planted_wrong_edges_walked_by_no_train_question": sum(c == 0 for c in counts),
    }


def ladder(client: HydraClient, built: dataset.Dataset, search: SearchConfig) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for stage in oracle.LADDER:
        repaired = stage.repair(client, built) if stage.repair is not None else {}
        index = build_index(oracle.nodes_for(stage, built))
        scored = score(judge_all(client, index, [h.question for h in built.split.held_out], search))
        rows.append(
            {
                "seed": built.seed,
                "stage": stage.name,
                "claim": stage.claim,
                "held_out_n": scored.n,
                "held_out_correct": scored.correct,
                "held_out_accuracy": round(scored.accuracy, 4),
                "unreachable": scored.unreachable,
                "refused": scored.refused,
                "wrong": scored.wrong,
                "repaired": repaired,
            }
        )
        print(f"  {stage.name}: {scored.correct}/{scored.n} = {scored.accuracy:.4f}", flush=True)
    return rows


def main(seeds: tuple[int, ...] = SEEDS) -> int:
    search = load_search_config(CONFIG)
    where = target.describe(str(load_settings().hydra_url))
    measuring.acquire("run1-diagnosis")
    anatomy_rows: list[dict[str, object]] = []
    oracle_rows: list[dict[str, object]] = []
    recovery_rows: list[dict[str, object]] = []
    try:
        with client_from_settings() as client:
            client.require_writable()
            for seed in seeds:
                built = dataset.build(seed)
                facts = anatomy.index_of(built.ingested.faults)
                pool = tuple((e.src, e.rel_type.value, e.dst) for e in built.ingested.pool)
                train = [t.question for t in built.split.train]
                print(f"seed {seed}", flush=True)

                reset_to_ingested(client, built.graph, pool, built.support)
                index = build_index(built.graph.nodes)
                at_zero = judge_all(client, index, train, search)
                anatomy_rows.append(anatomy_row(seed, "round_0", at_zero, anatomies(at_zero, built, facts)))
                recovery_rows.append(recovery_row(seed, built, at_zero))
                print(f"  round 0 train: {score(at_zero).correct}/{len(train)}", flush=True)

                kinds = replay(client, f"{run_name(seed)}")
                at_last = judge_all(client, index, train, search)
                row = anatomy_row(seed, "last_round", at_last, anatomies(at_last, built, facts))
                anatomy_rows.append(row | {"receipts_replayed": kinds})
                print(f"  last round train: {score(at_last).correct}/{len(train)}  replayed {kinds}", flush=True)

                reset_to_ingested(client, built.graph, pool, built.support)
                oracle_rows.extend(ladder(client, built, search))
    finally:
        measuring.release()

    for claim, design, rows in (
        ("anatomy", ANATOMY_DESIGN, anatomy_rows),
        ("oracle", ORACLE_DESIGN, oracle_rows),
        ("fault_recoverability", RECOVERY_DESIGN, recovery_rows),
    ):
        path = evidence.write(evidence.make(claim, design, rows, measured_on=where))
        print(f"{path} sha256={evidence.digest(path)}")
    return 0


def run_name(seed: int) -> str:
    rows = [json.loads(line) for line in Path("evidence/curve.jsonl").read_text(encoding="utf-8").splitlines() if line]
    names = {str(r["arm_run"]) for r in rows if r["seed"] == seed and r["arm"] == ARM and "arm_run" in r}
    if len(names) != 1:
        raise ValueError(f"the curve names {sorted(names)} for seed {seed} arm {ARM}, not one run")
    return names.pop()


if __name__ == "__main__":
    raise SystemExit(main())
