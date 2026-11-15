import json
from pathlib import Path

import pytest

from trailmend.eval import rerun
from trailmend.loop.policy import MendPolicy

RUN = "abc1234-def56789"


def _curve(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"run_id": RUN, "seed": 1, "arm": "reweight_only", "round": index, "held_out": {"accuracy": 0.5}}
        for index in range(3)
    ] + [
        {"run_id": RUN, "seed": 1, "arm": "full", "round": 0, "held_out": {"accuracy": 0.8}},
        {"run_id": RUN, "seed": 7, "arm": "reweight_only", "round": 0, "held_out": {"accuracy": 0.7}},
    ]
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def test_superseding_a_seed_arm_keeps_its_rows_on_record_and_leaves_the_others_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "evidence" / "curve.jsonl"
    _curve(path)

    dropped, out = rerun.set_aside_rows(1, MendPolicy.REWEIGHT_ONLY, RUN, "the API tests wrote to the same graph", path)

    assert dropped == 3
    assert len(out.read_text(encoding="utf-8").splitlines()) == 3
    left = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert [(row["seed"], row["arm"]) for row in left] == [(1, "full"), (7, "reweight_only")]
    why = json.loads((rerun.SUPERSEDED / f"{RUN}-s1-reweight_only-why.json").read_text(encoding="utf-8"))
    assert why["rows_superseded"] == 3
    assert why["superseded_reason"] == "the API tests wrote to the same graph"


def test_superseding_rows_that_are_not_there_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "evidence" / "curve.jsonl"
    _curve(path)
    with pytest.raises(ValueError, match="no rows for seed 42"):
        rerun.set_aside_rows(42, MendPolicy.REWEIGHT_ONLY, RUN, "a reason", path)


def test_an_arm_name_the_run_never_recorded_is_refused() -> None:
    with pytest.raises(ValueError, match="plain_store"):
        MendPolicy("plain_store")


def test_the_arm_index_is_the_one_the_sweep_used_so_the_rng_stream_is_the_same() -> None:
    assert rerun.arm_index_of(MendPolicy.REWEIGHT_ONLY) == 2
    assert rerun.arm_index_of(MendPolicy.FULL) == 0


def test_a_run_directory_is_moved_aside_with_the_reason_and_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runs = tmp_path / "runs"
    (runs / "r1").mkdir(parents=True)
    (runs / "r1" / "heldout.jsonl").write_text("{}\n", encoding="utf-8")

    target = rerun.set_aside_run("r1", "contaminated by a concurrent writer", runs)

    assert target is not None
    assert (target / "heldout.jsonl").exists()
    assert not (runs / "r1").exists()
    assert json.loads((target / "why.json").read_text(encoding="utf-8"))["superseded_reason"] == (
        "contaminated by a concurrent writer"
    )

    (runs / "r1").mkdir(parents=True)
    with pytest.raises(FileExistsError, match="already holds a superseded run"):
        rerun.set_aside_run("r1", "again", runs)


def test_a_run_directory_that_was_never_written_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert rerun.set_aside_run("never-ran", "a reason", tmp_path / "runs") is None
