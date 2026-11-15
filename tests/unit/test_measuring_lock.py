import json
import os
from pathlib import Path

import pytest

from trailmend.eval import measuring


def test_a_second_measured_run_is_refused_while_one_is_writing(tmp_path: Path) -> None:
    lock = tmp_path / "measuring.json"
    measuring.acquire("first-run", lock)
    with pytest.raises(RuntimeError, match="first-run"):
        measuring.acquire("second-run", lock)


def test_the_lock_names_the_run_the_pid_and_when_it_started(tmp_path: Path) -> None:
    lock = tmp_path / "measuring.json"
    measuring.acquire("abc1234-def56789", lock)
    claim = json.loads(lock.read_text(encoding="utf-8"))
    assert claim["run_id"] == "abc1234-def56789"
    assert claim["pid"] == os.getpid()
    assert claim["started_at"].endswith("+00:00")


def test_releasing_lets_the_next_run_start(tmp_path: Path) -> None:
    lock = tmp_path / "measuring.json"
    measuring.acquire("first-run", lock)
    measuring.release(lock)
    assert measuring.acquire("second-run", lock).exists()


def test_a_lock_left_behind_by_a_dead_process_does_not_block_anything(tmp_path: Path) -> None:
    lock = tmp_path / "measuring.json"
    lock.write_text(
        json.dumps({"run_id": "crashed-run", "pid": 2**22 - 1, "started_at": "2026-11-15T00:00:00+00:00"}),
        encoding="utf-8",
    )
    assert measuring.holder(lock) is None
    assert measuring.skip_reason(lock) is None
    assert measuring.acquire("next-run", lock).exists()


def test_tests_that_write_are_told_which_run_they_would_have_contaminated(tmp_path: Path) -> None:
    lock = tmp_path / "measuring.json"
    measuring.acquire("01f1f6f-06b10c13", lock)
    reason = measuring.skip_reason(lock)
    assert reason is not None
    assert "01f1f6f-06b10c13" in reason
    assert "contaminate" in reason


def test_no_lock_means_nothing_to_skip(tmp_path: Path) -> None:
    assert measuring.skip_reason(tmp_path / "nothing.json") is None
