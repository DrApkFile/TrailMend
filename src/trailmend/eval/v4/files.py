import hashlib
import json
import os
import subprocess
from pathlib import Path

from trailmend.eval import evidence, manifest, target

CURVE = Path("evidence/curve_v4_northwind.jsonl")
CONFIG = Path("config/run4.toml")
MEND = Path("config/mend.toml")
ARMS = ("frozen_v4", "full_v4", "full_v4_no_gate", "full_v2")
SEEDS = (1, 7, 42)
ROUNDS = 5


def digest() -> str:
    return hashlib.sha256(MEND.read_bytes() + b"\n" + CONFIG.read_bytes()).hexdigest()


def append(row: dict[str, object]) -> None:
    if not str(row["run_id"]).startswith("v4-"):
        raise ValueError("run 4 only writes its own run ids")
    CURVE.parent.mkdir(exist_ok=True)
    with CURVE.open("a") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_manifest(run_id: str) -> None:
    paths = [CURVE, Path("evidence/calibration_v4.json")]
    paths.extend(
        Path("evidence") / name
        for name in ("hypotheses_v4.json", "paired_v4.json", "summary_v4.json")
        if (Path("evidence") / name).exists()
    )
    paths.extend(sorted(Path("evidence/runs").glob(f"{run_id}-*/**/*.jsonl")))
    payload = {
        "run_id": run_id,
        "code_commit": subprocess.check_output(["git", "rev-parse", run_id.split("-")[1]], text=True).strip(),
        "preregistration_commit": "d6a300c",
        "eligibility_clarification_commit": "0c630b0",
        "shared_trajectory": {"full_v4": "full_v4_no_gate"},
        "config_sha256": digest(),
        "config": CONFIG.read_text(),
        "mend_config": MEND.read_text(),
        "hydradb": target.describe("http://127.0.0.1:8444"),
        "hydra_url": "http://127.0.0.1:8444",
        "data_version": "v2",
        "dataset": "northwind_generated",
        "classification": "measured",
        "seeds": {str(seed): manifest.dataset_digests(seed, "v2") for seed in SEEDS},
        "evidence_sha256": {str(path.relative_to("evidence")): evidence.digest(path) for path in paths},
        "expected_rows": len(SEEDS) * len(ARMS) * (ROUNDS + 1),
    }
    Path("evidence/run_manifest_v4.json").write_text(json.dumps(payload, indent=2) + "\n")
