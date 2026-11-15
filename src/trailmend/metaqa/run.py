import hashlib
import json
import os
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from random import Random

from trailmend.core.config import load_mend_config
from trailmend.core.model import EdgeKey
from trailmend.eval import evidence, measuring, target
from trailmend.eval.run import commit
from trailmend.eval.session import client_from_settings
from trailmend.graph.client import HydraClient
from trailmend.loop.journal import Journal
from trailmend.loop.policy import MendPolicy, rules
from trailmend.metaqa import files
from trailmend.metaqa.answer import judge_all, score
from trailmend.metaqa.config import MEND_CONFIG, MetaqaConfig, config_digest, load_metaqa_config
from trailmend.metaqa.gapfill import LiveGraph
from trailmend.metaqa.kb import KnowledgeBase, read_kb
from trailmend.metaqa.ladder import LADDER_DESIGN, ladder
from trailmend.metaqa.loop import record_tape, restore, row_of, run_round
from trailmend.metaqa.sample import Workload, build_workload
from trailmend.metaqa.store import load_world
from trailmend.metaqa.world import World, build_world, faults_json
from trailmend.settings import load_settings

DATASET = "metaqa"
CURVE = Path("evidence/curve_metaqa.jsonl")
OUT_DIR = Path("evidence/metaqa")
ARMS: tuple[MendPolicy, ...] = (MendPolicy.FROZEN, MendPolicy.FULL_V2, MendPolicy.RANDOM_REWEIGHT)
SEEDS: tuple[int, ...] = (1, 7, 42)


def run_id_for() -> str:
    return f"{commit()}-{config_digest()[:8]}"


def append(row: dict[str, object], path: Path = CURVE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def describe(world: World, workload: Workload, faults_path: Path) -> dict[str, object]:
    return {
        "dataset": DATASET,
        "seed": world.seed,
        "kb_lines": world.kb_lines,
        "kb_distinct_triples": world.kb_triples,
        "nodes": sum(len(names) for names in world.names.values()),
        "g0_triples": len(world.ingested),
        "g0_edges": 2 * len(world.ingested),
        "pool_triples": len(world.pool),
        "faults": dict(Counter(f.kind.value for f in world.faults)),
        "faults_file": str(faults_path),
        "faults_sha256": hashlib.sha256(faults_path.read_bytes()).hexdigest(),
        "region_start_movie": workload.region.start,
        "region_movies": len(workload.region.movies),
        "region_people": len(workload.region.people),
        "eligible_dev_questions": workload.eligible_train,
        "eligible_test_questions": workload.eligible_held_out,
        "test_questions_dropped_for_sharing_topic_and_qtype_with_train": workload.dropped_shared_pairs,
        "train": len(workload.train),
        "held_out": len(workload.held_out),
        "train_by_hop": dict(sorted(Counter(q.hop for q in workload.train).items())),
        "held_out_by_hop": dict(sorted(Counter(q.hop for q in workload.held_out).items())),
        "train_qtypes": len({q.qtype for q in workload.train}),
        "held_out_qtypes": len({q.qtype for q in workload.held_out}),
        "question_ids_sha256": hashlib.sha256(
            json.dumps([[q.id for q in workload.train], [q.id for q in workload.held_out]]).encode()
        ).hexdigest(),
    }


def candidates_of(live: LiveGraph, workload: Workload) -> tuple[EdgeKey, ...]:
    found: set[EdgeKey] = set()
    for question in workload.train:
        found.update(live.path_edges(question))
    return tuple(sorted(found))


def run_arm(
    client: HydraClient,
    world: World,
    workload: Workload,
    arm: MendPolicy,
    arm_index: int,
    run_id: str,
    config: MetaqaConfig,
    stamp: dict[str, object],
) -> list[dict[str, object]]:
    mend = load_mend_config(MEND_CONFIG, rules(arm).update)
    name = f"{run_id}-s{world.seed}-{arm.value}"
    journal = Journal.for_run(name)
    live = LiveGraph.of(world)
    candidates = candidates_of(live, workload)
    rng = Random(world.seed * 1_000 + arm_index)
    base = stamp | {"arm": arm.value, "arm_run": name, "random_candidates": len(candidates)}
    at_zero = judge_all(client, workload.held_out, config.result_limit)
    record_tape(name, 0, at_zero)
    zero = score(at_zero)
    rows: list[dict[str, object]] = [base | {"round": 0, "held_out": asdict(zero), "train": None}]
    print(f"  {arm.value} round 0: hits@1 {zero.hits}/{zero.n} = {zero.hits_at_1:.4f}", flush=True)
    for round_index in range(1, config.rounds + 1):
        outcome = run_round(
            client,
            journal,
            name,
            round_index,
            arm,
            live,
            workload.train,
            workload.held_out,
            candidates,
            rng,
            mend,
            config.result_limit,
        )
        rows.append(base | row_of(outcome))
        print(
            f"  {arm.value} round {round_index}: hits@1 {outcome.held_out.hits_at_1:.4f} "
            f"exact {outcome.held_out.exact_set:.4f} wrong {outcome.held_out.wrong_rate:.4f} "
            f"train {outcome.train.hits_at_1:.4f} reweights {outcome.applied.reweights} "
            f"quarantines {outcome.applied.quarantines} filled {outcome.filled_facts}",
            flush=True,
        )
    restored = restore(client, live)
    print(f"  {arm.value}: {restored} touched edges put back to G0", flush=True)
    return rows


def run_seed(
    client: HydraClient, kb: KnowledgeBase, seed: int, run_id: str, config: MetaqaConfig
) -> list[dict[str, object]]:
    where = target.describe(str(load_settings().hydra_url))
    world = build_world(kb, seed)
    workload = build_workload(kb, world, config.sample)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    faults_path = OUT_DIR / f"faults_s{seed}.json"
    faults_path.write_text(faults_json(world) + "\n", encoding="utf-8")
    described = describe(world, workload, faults_path)
    started = time.monotonic()
    loaded = load_world(client, world)
    described |= {
        "loaded_nodes": loaded.nodes,
        "loaded_edges": loaded.edges,
        "load_seconds": round(time.monotonic() - started, 1),
    }
    (OUT_DIR / f"dataset_s{seed}.json").write_text(
        json.dumps(described, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"seed {seed}: loaded {loaded.nodes} nodes, {loaded.edges} edges in {described['load_seconds']}s", flush=True)
    stamp: dict[str, object] = {"dataset": DATASET, "seed": seed, "run_id": run_id, "hydradb": where}
    for arm_index, arm in enumerate(ARMS):
        for row in run_arm(client, world, workload, arm, arm_index, run_id, config, stamp):
            append(row)
    return [row | {"run_id": run_id} for row in ladder(client, world, workload.held_out, config.result_limit)]


def main(seeds: tuple[int, ...] = SEEDS) -> int:
    files.verify()
    config = load_metaqa_config()
    run_id = run_id_for()
    kb = read_kb()
    print(f"metaqa run {run_id}: {len(seeds)} seeds x {len(ARMS)} graph arms x {config.rounds} rounds", flush=True)
    ladder_rows: list[dict[str, object]] = []
    measuring.acquire(run_id)
    try:
        with client_from_settings() as client:
            client.require_writable()
            for seed in seeds:
                ladder_rows.extend(run_seed(client, kb, seed, run_id, config))
                path = OUT_DIR / f"ladder_{run_id}.partial.json"
                path.write_text(json.dumps(ladder_rows, indent=1) + "\n", encoding="utf-8")
    finally:
        measuring.release()
    where = target.describe(str(load_settings().hydra_url))
    written = evidence.write(evidence.make("oracle_metaqa", LADDER_DESIGN, ladder_rows, measured_on=where))
    print(f"{written} sha256={evidence.digest(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(tuple(int(a) for a in sys.argv[1:]) or SEEDS))
