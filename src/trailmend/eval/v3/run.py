import json
import tomllib
from dataclasses import replace
from typing import cast
from urllib.parse import urlsplit

from trailmend.core.config import load_search_config
from trailmend.core.model import EdgeKey
from trailmend.data import dataset
from trailmend.eval import evidence, measuring, target
from trailmend.eval.run import commit, run_arm
from trailmend.eval.session import client_from_settings
from trailmend.eval.v3 import files
from trailmend.eval.v3.calibration import fit
from trailmend.graph.reset import reset_to_ingested
from trailmend.graph.schema import NORTHWIND_REL_TYPES
from trailmend.graph.state import list_edge_keys
from trailmend.loop.journal import RUNS_DIR
from trailmend.loop.policy import MendPolicy
from trailmend.search.seed import build_index
from trailmend.settings import load_settings

DESIGN = (
    "Run 3: thresholds calibrated only on correct training answers on G0, separately per seed and template, "
    "using the preregistered nearest-rank quantile. Held-out answers are not read by calibration. Thresholds stay "
    "fixed across arms and rounds. Empty strata explicitly receive zero. PRD section 3.4."
)


def refusal_counts(run_id: str, seed: int, arm: str) -> dict[int, int]:
    path = RUNS_DIR / f"{run_id}-s{seed}-{arm}" / "heldout.jsonl"
    counts = dict.fromkeys(range(files.ROUNDS + 1), 0)
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row.get("refusal") == "low_confidence":
            counts[int(row["round"])] += 1
    return counts


def main() -> int:
    address = urlsplit(str(load_settings().hydra_url))
    if address.hostname != "127.0.0.1" or address.port != 8444:
        raise ValueError("run 3 requires its isolated HydraDB at 127.0.0.1:8444")
    if files.CURVE.exists():
        raise FileExistsError(f"{files.CURVE} already exists; never overwrite a recorded run")
    config = tomllib.loads(files.CONFIG.read_text())
    if tuple(config["seeds"]) != files.SEEDS or config["rounds"] != files.ROUNDS:
        raise ValueError("run 3 config does not match its preregistration")
    quantile = float(config["quantile"])
    run_id = f"v3-{commit()}-{files.digest()[:8]}"
    measuring.acquire(run_id)
    calibrations: list[dict[str, object]] = []
    where = target.describe(str(load_settings().hydra_url))
    print(f"run {run_id}: isolated Northwind v2, {files.ARMS}, seeds {files.SEEDS}", flush=True)
    try:
        with client_from_settings() as client:
            client.require_writable()
            for seed in files.SEEDS:
                built = dataset.build(seed, data_version="v2")
                pool = frozenset(EdgeKey(e.src, e.rel_type.value, e.dst) for e in built.ingested.pool)
                reset_to_ingested(client, built.graph, tuple((e.src, e.rel_type, e.dst) for e in pool), built.support)
                wanted = {EdgeKey(e.src, e.rel_type.value, e.dst) for e in built.graph.edges}
                present = {key for kind in NORTHWIND_REL_TYPES for key in list_edge_keys(client, kind.value)}
                if present != wanted:
                    raise ValueError("run 3 calibration graph does not exactly match G0")
                search = load_search_config(files.MEND)
                thresholds, calibrated = fit(
                    client, build_index(built.graph.nodes), built.split.train, search, quantile
                )
                calibrations.extend(row | {"seed": seed, "run_id": run_id} for row in calibrated)
                evidence.write(evidence.make("calibration_v3", DESIGN, calibrations, measured_on=where))
                gated = replace(search, confidence_thresholds=thresholds, gapfill_edges=pool)
                print(f"seed {seed}: calibration frozen from training only", flush=True)
                for arm_index, arm in enumerate(files.ARMS):
                    override = search if arm == "full_v2" else gated
                    rows = run_arm(client, built, MendPolicy(arm), arm_index, run_id, files.ROUNDS, override)
                    refused = refusal_counts(run_id, seed, arm)
                    for row in rows:
                        held = row["held_out"]
                        if not isinstance(held, dict):
                            raise TypeError("held-out score missing")
                        held = cast("dict[str, object]", held)
                        count = int(str(held["n"]))
                        files.append(
                            row
                            | {
                                "hydradb": where,
                                "config_sha256": files.digest(),
                                "classification": "measured",
                                "thresholds": dict(thresholds) if arm != "full_v2" else None,
                                "low_confidence": refused[int(str(row["round"]))],
                                "wrong_rate": int(str(held["wrong"])) / count,
                                "refused_rate": int(str(held["refused"])) / count,
                                "coverage": (int(str(held["correct"])) + int(str(held["wrong"]))) / count,
                            }
                        )
    finally:
        measuring.release()
    files.write_manifest(run_id)
    print(f"wrote {len(files.SEEDS) * len(files.ARMS) * (files.ROUNDS + 1)} rows to {files.CURVE}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
