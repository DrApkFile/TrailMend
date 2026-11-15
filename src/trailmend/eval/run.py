import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from random import Random

from trailmend.core.config import (
    config_digest,
    load_gapfill_rule,
    load_mend_config,
    load_run_config,
    load_search_config,
)
from trailmend.core.model import EdgeKey, GapfillRule
from trailmend.data import dataset
from trailmend.data.faultmodel import V1, V2
from trailmend.eval import curve, measuring, target
from trailmend.eval.plain_store import build_store, judge_all_plain
from trailmend.eval.session import client_from_settings
from trailmend.graph.client import HydraClient
from trailmend.graph.reset import reset_to_ingested
from trailmend.loop.evaluate import judge_all, score
from trailmend.loop.gapfill import NARROW
from trailmend.loop.journal import Journal
from trailmend.loop.ledger import Ledger
from trailmend.loop.policy import GAPFILL_WIDE, MendPolicy, rules, searches_on_cost
from trailmend.loop.round import run_round
from trailmend.loop.tape import Tape
from trailmend.search.seed import build_index
from trailmend.settings import load_settings

CONFIG = Path("config/mend.toml")
ARMS: tuple[MendPolicy, ...] = (
    MendPolicy.FULL,
    MendPolicy.FROZEN,
    MendPolicy.REWEIGHT_ONLY,
    MendPolicy.QUARANTINE_ONLY,
    MendPolicy.PROMOTE_ONLY,
    MendPolicy.GAPFILL_ONLY,
    MendPolicy.RANDOM_REWEIGHT,
    MendPolicy.RANDOM_QUARANTINE,
)
RUN2_ARMS: tuple[MendPolicy, ...] = (
    MendPolicy.FULL_V2,
    MendPolicy.FROZEN,
    MendPolicy.FULL_V1_RULE,
    MendPolicy.GAPFILL_WIDE_ONLY,
    MendPolicy.RANDOM_REWEIGHT,
    MendPolicy.RANDOM_QUARANTINE,
)
DATASET = "northwind_generated"


def gapfill_rule_for(arm: MendPolicy) -> GapfillRule:
    return load_gapfill_rule(CONFIG) if rules(arm).gapfill == GAPFILL_WIDE else NARROW


def commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def run_id_for(config: Path = CONFIG) -> str:
    return f"{commit()}-{config_digest(config)[:8]}"


def plain_rows(run_id: str, built: dataset.Dataset, rounds: int, top_k: int) -> list[dict[str, object]]:
    store = build_store(built.documents.ingested, built.graph.nodes)
    result = score(judge_all_plain(store, [h.question for h in built.split.held_out], top_k))
    return [
        {
            "dataset": DATASET,
            "seed": built.seed,
            "arm": "plain_store",
            "round": index,
            "run_id": run_id,
            "data_version": built.data_version,
            "held_out": {
                "n": result.n,
                "correct": result.correct,
                "accuracy": result.accuracy,
                "set_f1": result.set_f1,
                "unreachable": result.unreachable,
                "refused": result.refused,
                "wrong": result.wrong,
            },
            "train": None,
            "documents": store.size,
            "top_k": top_k,
        }
        for index in range(rounds + 1)
    ]


def run_arm(
    client: HydraClient, built: dataset.Dataset, arm: MendPolicy, arm_index: int, run_id: str, rounds: int
) -> list[dict[str, object]]:
    arm_rules = rules(arm)
    mend = load_mend_config(CONFIG, arm_rules.update)
    gapfill = gapfill_rule_for(arm)
    search = replace(load_search_config(CONFIG), weighted=searches_on_cost(arm))
    stamp: dict[str, object] = {
        "run_id": run_id,
        "arm_run": "",
        "data_version": built.data_version,
        "rules": {"update": arm_rules.update, "gapfill": arm_rules.gapfill}
        | ({} if search.weighted else {"search": "unweighted"}),
    }
    pool = tuple((e.src, e.rel_type.value, e.dst) for e in built.ingested.pool)
    reset_to_ingested(client, built.graph, pool, built.support)
    index = build_index(built.graph.nodes)
    name = f"{run_id}-s{built.seed}-{arm.value}"
    stamp["arm_run"] = name
    journal = Journal.for_run(name)
    ledger = Ledger.for_run(name)
    tape = Tape.for_run(name)
    candidates: tuple[EdgeKey, ...] = tuple(EdgeKey(e.src, e.rel_type.value, e.dst) for e in built.graph.edges)
    rng = Random(built.seed * 1_000 + arm_index)
    judged_baseline = judge_all(client, index, [h.question for h in built.split.held_out], search)
    tape.record(0, judged_baseline)
    baseline = score(judged_baseline)
    rows: list[dict[str, object]] = [
        {
            "dataset": DATASET,
            "seed": built.seed,
            "arm": arm.value,
            "round": 0,
            "held_out": {
                "n": baseline.n,
                "correct": baseline.correct,
                "accuracy": baseline.accuracy,
                "set_f1": baseline.set_f1,
                "unreachable": baseline.unreachable,
                "refused": baseline.refused,
                "wrong": baseline.wrong,
            },
            "train": None,
            "gapfill_reached": 0,
            "gapfill_ingested": 0,
        }
        | stamp
    ]
    reached: set[EdgeKey] = set()
    ingested: set[EdgeKey] = set()
    print(f"  {arm.value} round 0: held-out {baseline.correct}/{baseline.n} = {baseline.accuracy:.4f}", flush=True)
    for round_index in range(1, rounds + 1):
        outcome = run_round(
            client,
            journal,
            ledger,
            tape,
            name,
            round_index,
            arm,
            index,
            built.split.train,
            built.split.held_out,
            candidates,
            rng,
            mend,
            search,
            built.documents,
            built.ingested.pool,
            gapfill,
        )
        reached.update(outcome.reached)
        ingested.update(outcome.ingested)
        rows.append(
            curve.row(DATASET, built.seed, outcome)
            | stamp
            | {"gapfill_reached": len(reached), "gapfill_ingested": len(ingested)}
        )
        print(
            f"  {arm.value} round {round_index}: held-out {outcome.held_out.correct}/{outcome.held_out.n} = "
            f"{outcome.held_out.accuracy:.4f}  train {outcome.train.accuracy:.4f}  "
            f"reweights {outcome.applied.reweights} quarantines {outcome.applied.quarantines} "
            f"promoted {len(outcome.promoted)} retired {len(outcome.retired)} ingested {len(outcome.ingested)}",
            flush=True,
        )
    return rows


UNWEIGHTED_ARMS: tuple[MendPolicy, ...] = (MendPolicy.FROZEN, MendPolicy.FULL_UNWEIGHTED)


def main(
    seeds: tuple[int, ...], arms: tuple[MendPolicy, ...] = ARMS, data_version: str = V1, out: Path | None = None
) -> int:
    run = load_run_config(CONFIG)
    run_id = run_id_for()
    print(
        f"run {run_id} on data {data_version}: {len(seeds)} seeds x {len(arms)} arms x {run.rounds} rounds", flush=True
    )
    measuring.acquire(run_id)
    try:
        written = _sweep(seeds, arms, run_id, run.rounds, run.plain_store_top_k, data_version, out)
    finally:
        measuring.release()
    print(f"wrote {written} rows to {out or curve.path_for(data_version)}")
    return 0


def _sweep(
    seeds: tuple[int, ...],
    arms: tuple[MendPolicy, ...],
    run_id: str,
    rounds: int,
    plain_store_top_k: int,
    data_version: str,
    extension: Path | None = None,
) -> int:
    written = 0
    out = extension or curve.path_for(data_version)
    where = target.describe(str(load_settings().hydra_url))
    with client_from_settings() as client:
        client.require_writable()
        for seed in seeds:
            built = dataset.build(seed, data_version=data_version)
            print(f"seed {seed}", flush=True)
            for row in plain_rows(run_id, built, rounds, plain_store_top_k) if extension is None else ():
                curve.append(row | {"hydradb": where}, out)
                written += 1
            for arm_index, arm in enumerate(arms):
                for row in run_arm(client, built, arm, arm_index, run_id, rounds):
                    curve.append(row | {"hydradb": where}, out)
                    written += 1
    return written


if __name__ == "__main__":
    _args = sys.argv[1:]
    _run2 = "--v2" in _args
    _seeds = tuple(int(a) for a in _args if a.isdigit()) or (1, 7, 42)
    if "--unweighted" in _args:
        raise SystemExit(main(_seeds, UNWEIGHTED_ARMS, V2, curve.CURVE_V2_UNWEIGHTED))
    raise SystemExit(main(_seeds, RUN2_ARMS if _run2 else ARMS, V2 if _run2 else V1))
