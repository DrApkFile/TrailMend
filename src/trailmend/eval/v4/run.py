import tomllib
from dataclasses import replace
from typing import cast
from urllib.parse import urlsplit

from trailmend.core.config import load_search_config
from trailmend.core.model import EdgeKey, SearchConfig
from trailmend.data import dataset
from trailmend.eval import evidence, measuring, target
from trailmend.eval.run import commit, run_arm
from trailmend.eval.session import client_from_settings
from trailmend.eval.v3.calibration import fit
from trailmend.eval.v4 import files
from trailmend.eval.v4.observe import ObserveGate, refusal_counts
from trailmend.graph.client import HydraClient
from trailmend.graph.reset import reset_to_ingested
from trailmend.graph.schema import NORTHWIND_REL_TYPES
from trailmend.graph.state import list_edge_keys
from trailmend.loop.policy import MendPolicy
from trailmend.loop.tape import Tape
from trailmend.search.seed import EntityIndex, build_index
from trailmend.settings import load_settings

DESIGN = (
    "Run 4: training-only nearest-rank calibration through weighted single-answer and base-only hop-count "
    "set-answer search. Feedback audits ungated training candidates; held-out gating contributes no credit. "
    "full_v4 and full_v4_no_gate share the exact learner trajectory and receipts; "
    "their evaluations have separate tapes."
)


def write_rows(rows: list[dict[str, object]], where: dict[str, object]) -> None:
    for row in rows:
        held = cast("dict[str, object]", row["held_out"])
        n = int(str(held["n"]))
        files.append(
            row
            | {
                "hydradb": where,
                "config_sha256": files.digest(),
                "classification": "measured",
                "training_feedback": "ungated_internal_audit",
                "wrong_rate": int(str(held["wrong"])) / n,
                "refused_rate": int(str(held["refused"])) / n,
                "coverage": (int(str(held["correct"])) + int(str(held["wrong"]))) / n,
            }
        )


def prepare(
    client: HydraClient, built: dataset.Dataset, quantile: float
) -> tuple[EntityIndex, SearchConfig, SearchConfig, SearchConfig, list[dict[str, object]]]:
    pool = frozenset(EdgeKey(e.src, e.rel_type.value, e.dst) for e in built.ingested.pool)
    reset_to_ingested(client, built.graph, tuple((e.src, e.rel_type, e.dst) for e in pool), built.support)
    wanted = {EdgeKey(e.src, e.rel_type.value, e.dst) for e in built.graph.edges}
    present = {key for kind in NORTHWIND_REL_TYPES for key in list_edge_keys(client, kind.value)}
    if wanted != present:
        raise ValueError("run 4 calibration graph does not exactly match G0")
    reference = load_search_config(files.MEND)
    teacher = replace(reference, unweighted_sets=True)
    index = build_index(built.graph.nodes)
    thresholds, samples = fit(client, index, built.split.train, teacher, quantile)
    gated = replace(teacher, confidence_thresholds=thresholds, gapfill_edges=pool)
    return index, teacher, reference, gated, samples


def main() -> int:
    address = urlsplit(str(load_settings().hydra_url))
    if address.hostname != "127.0.0.1" or address.port != 8444:
        raise ValueError("run 4 requires isolated HydraDB at 127.0.0.1:8444")
    if files.CURVE.exists():
        raise FileExistsError(f"{files.CURVE} exists; never overwrite a recorded run")
    config = tomllib.loads(files.CONFIG.read_text())
    if tuple(config["seeds"]) != files.SEEDS or config["rounds"] != files.ROUNDS:
        raise ValueError("run 4 config differs from its preregistration")
    run_id = f"v4-{commit()}-{files.digest()[:8]}"
    measuring.acquire(run_id)
    calibrated: list[dict[str, object]] = []
    where = target.describe(str(load_settings().hydra_url))
    print(f"run {run_id}: four outputs, three graph trajectories, seeds {files.SEEDS}", flush=True)
    try:
        with client_from_settings() as client:
            client.require_writable()
            for seed in files.SEEDS:
                built = dataset.build(seed, data_version="v2")
                index, teacher, reference, gated, samples = prepare(client, built, float(config["quantile"]))
                calibrated.extend(row | {"seed": seed, "run_id": run_id} for row in samples)
                evidence.write(evidence.make("calibration_v4", DESIGN, calibrated, measured_on=where))
                print(f"seed {seed}: hybrid training calibration frozen", flush=True)
                frozen = run_arm(client, built, MendPolicy.FROZEN_V4, 0, run_id, files.ROUNDS, gated, teacher)
                frozen_refusals = refusal_counts(f"{run_id}-s{seed}-frozen_v4")
                for row in frozen:
                    row["low_confidence"] = frozen_refusals.get(int(str(row["round"])), 0)
                    row["answer_search"] = "weighted_single_unweighted_set"
                write_rows(frozen, where)
                name = f"{run_id}-s{seed}-full_v4"
                observer = ObserveGate(client, index, built.split.held_out, gated, Tape.for_run(name))
                raw = run_arm(
                    client, built, MendPolicy.FULL_V4_NO_GATE, 1, run_id, files.ROUNDS, teacher, teacher, observer
                )
                if set(observer.scores) != set(range(files.ROUNDS + 1)):
                    raise ValueError("run 4 did not observe every matched graph state")
                guarded: list[dict[str, object]] = []
                for row in raw:
                    r = int(str(row["round"]))
                    row["low_confidence"] = 0
                    row["answer_search"] = "weighted_single_unweighted_set"
                    guarded.append(
                        row
                        | {
                            "arm": "full_v4",
                            "arm_run": name,
                            "held_out": observer.scores[r],
                            "low_confidence": observer.refusals[r],
                            "shared_graph_arm": "full_v4_no_gate",
                            "receipt_run": f"{run_id}-s{seed}-full_v4_no_gate",
                        }
                    )
                write_rows(raw, where)
                write_rows(guarded, where)
                weighted = run_arm(client, built, MendPolicy.FULL_V2, 2, run_id, files.ROUNDS, reference)
                for row in weighted:
                    row["low_confidence"] = 0
                    row["answer_search"] = "weighted"
                write_rows(weighted, where)
    finally:
        measuring.release()
    files.write_manifest(run_id)
    print(f"wrote {len(files.SEEDS) * len(files.ARMS) * (files.ROUNDS + 1)} rows", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
