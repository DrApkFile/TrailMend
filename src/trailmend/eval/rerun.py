import json
import shutil
import sys
from pathlib import Path

from trailmend.core.config import load_run_config
from trailmend.data import dataset
from trailmend.eval import curve, measuring, target
from trailmend.eval.evidence import now_utc
from trailmend.eval.run import ARMS, CONFIG, run_arm, run_id_for
from trailmend.eval.session import client_from_settings
from trailmend.loop.journal import RUNS_DIR
from trailmend.loop.policy import MendPolicy
from trailmend.settings import load_settings

SUPERSEDED = Path("evidence/superseded")


def arm_index_of(arm: MendPolicy) -> int:
    if arm not in ARMS:
        raise ValueError(f"{arm.value} is not one of the recorded arms: {[a.value for a in ARMS]}")
    return ARMS.index(arm)


def set_aside_rows(seed: int, arm: MendPolicy, run_id: str, reason: str, path: Path = curve.CURVE) -> tuple[int, Path]:
    kept: list[str] = []
    dropped: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("seed") == seed and row.get("arm") == arm.value and row.get("run_id") == run_id:
            dropped.append(line)
        else:
            kept.append(line)
    if not dropped:
        raise ValueError(f"{path} has no rows for seed {seed} arm {arm.value} run {run_id} to supersede")
    SUPERSEDED.mkdir(parents=True, exist_ok=True)
    out = SUPERSEDED / f"{run_id}-s{seed}-{arm.value}-curve-rows.jsonl"
    out.write_text("\n".join(dropped) + "\n", encoding="utf-8")
    (SUPERSEDED / f"{run_id}-s{seed}-{arm.value}-why.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "seed": seed,
                "arm": arm.value,
                "rows_superseded": len(dropped),
                "superseded_at": now_utc(),
                "superseded_reason": reason,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return len(dropped), out


def set_aside_run(name: str, reason: str, root: Path = RUNS_DIR) -> Path | None:
    source = root / name
    if not source.exists():
        return None
    SUPERSEDED.mkdir(parents=True, exist_ok=True)
    target = SUPERSEDED / f"{name}-run"
    if target.exists():
        raise FileExistsError(f"{target} already holds a superseded run; move it aside before another re-run")
    shutil.move(str(source), str(target))
    (target / "why.json").write_text(
        json.dumps({"run": name, "superseded_at": now_utc(), "superseded_reason": reason}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return target


def main(seed: int, arm_value: str, reason: str) -> int:
    arm = MendPolicy(arm_value)
    arm_index = arm_index_of(arm)
    run_id = run_id_for()
    run = load_run_config(CONFIG)
    name = f"{run_id}-s{seed}-{arm.value}"
    dropped, out = set_aside_rows(seed, arm, run_id, reason)
    moved = set_aside_run(name, reason)
    print(f"superseded {dropped} curve rows into {out}")
    print(f"superseded the run directory into {moved}" if moved else "no run directory to supersede")
    built = dataset.build(seed)
    print(f"re-running seed {seed} arm {arm.value} (arm index {arm_index}) for {run.rounds} rounds", flush=True)
    written = 0
    measuring.acquire(f"{run_id}-s{seed}-{arm.value}-rerun")
    try:
        where = target.describe(str(load_settings().hydra_url))
        with client_from_settings() as client:
            client.require_writable()
            for row in run_arm(client, built, arm, arm_index, run_id, run.rounds):
                curve.append(row | {"hydradb": where})
                written += 1
    finally:
        measuring.release()
    print(f"appended {written} rows to {curve.CURVE}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit("usage: python -m trailmend.eval.rerun <seed> <arm> <why it is being replaced>")
    raise SystemExit(main(int(sys.argv[1]), sys.argv[2], " ".join(sys.argv[3:])))
