import json
from pathlib import Path

import pytest

from trailmend.eval import analyse


def _curve(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            json.dumps(
                {
                    "arm": arm,
                    "seed": 1,
                    "round": round_index,
                    "held_out": {"accuracy": 0.5, "correct": 1, "n": 2},
                    "train": None,
                }
            )
            for arm in (policy.value for policy in analyse.ARMS)
            for round_index in (0, 1)
        ),
        encoding="utf-8",
    )


def test_a_run_with_no_held_out_tape_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no held-out tape"):
        analyse.require_tape("01f1f6f-s1-full", tmp_path)


def test_non_regression_will_not_report_zero_breaks_for_a_run_it_cannot_find(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _curve(tmp_path / "evidence" / "curve.jsonl")
    rows = analyse.rows_of(tmp_path / "evidence" / "curve.jsonl")
    with pytest.raises(FileNotFoundError, match="recorded curve rows but no held-out tape"):
        analyse.non_regression(rows, "missing-run")


def test_the_quarantine_report_will_not_score_a_run_it_cannot_find(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _curve(tmp_path / "evidence" / "curve.jsonl")
    rows = analyse.rows_of(tmp_path / "evidence" / "curve.jsonl")
    with pytest.raises(FileNotFoundError, match="recorded curve rows but no held-out tape"):
        analyse.quarantine_report(rows, "missing-run")


def test_every_hypothesis_carries_the_rule_it_was_decided_by(tmp_path: Path) -> None:
    rows = [
        {
            "arm": arm.value,
            "seed": 1,
            "round": round_index,
            "held_out": {"accuracy": 0.5, "correct": 1, "n": 2},
        }
        for arm in analyse.ARMS
        for round_index in (0, 1)
    ] + [
        {"arm": analyse.PLAIN, "seed": 1, "round": round_index, "held_out": {"accuracy": 0.2}} for round_index in (0, 1)
    ]
    breaks = [{"arm": "full", "round": 1, "correct": 100, "newly_broken": 1}]
    quarantines = [{"arm": "full", "recall_on_planted_wrong_edges": 1.0, "false_quarantine_rate": 0.0}]
    decided = analyse.hypotheses(rows, breaks, quarantines, 1)
    assert [row["id"] for row in decided] == ["H1", "H2", "H3", "H4", "H5"]
    assert all(str(row["rule"]).strip() for row in decided)


def test_no_hypothesis_is_decided_from_an_empty_set_of_breaks_or_quarantines() -> None:
    rows = [
        {"arm": arm.value, "seed": 1, "round": r, "held_out": {"accuracy": 0.5}} for arm in analyse.ARMS for r in (0, 1)
    ]
    with pytest.raises(ValueError, match="cannot be decided without"):
        analyse.hypotheses(rows, (), (), 1)


def _control_row(arm: str, planned_rw: int, planned_qu: int, applied_rw: int, applied_qu: int) -> dict[str, object]:
    return {
        "arm": arm,
        "seed": 1,
        "round": 1,
        "planned_reweights": planned_rw,
        "planned_quarantines": planned_qu,
        "applied_reweights": applied_rw,
        "applied_quarantines": applied_qu,
    }


def test_inv6_holds_when_each_control_mirrors_only_its_own_mechanism() -> None:
    rows = [
        _control_row("random_reweight", 572, 6, 572, 0),
        _control_row("random_quarantine", 571, 5, 0, 5),
        {"arm": "full", "seed": 1, "round": 1, "applied_reweights": 587, "applied_quarantines": 8},
    ]
    assert analyse.check_inv6(rows) == 2


def test_inv6_fails_when_a_control_makes_fewer_changes_than_the_mend_planned() -> None:
    with pytest.raises(ValueError, match="INV6 fails at random_reweight"):
        analyse.check_inv6([_control_row("random_reweight", 572, 6, 400, 0)])


def test_inv6_fails_when_a_control_also_makes_the_other_mechanisms_changes() -> None:
    with pytest.raises(ValueError, match="INV6 fails at random_quarantine"):
        analyse.check_inv6([_control_row("random_quarantine", 571, 5, 571, 5)])


def test_a_run_with_no_control_rounds_cannot_claim_inv6() -> None:
    with pytest.raises(ValueError, match="INV6 cannot be checked"):
        analyse.check_inv6([{"arm": "full", "seed": 1, "round": 1}])


def test_round_zero_is_not_an_inv6_round_because_nothing_was_applied() -> None:
    with pytest.raises(ValueError, match="INV6 cannot be checked"):
        analyse.check_inv6([_control_row("random_reweight", 0, 0, 0, 0) | {"round": 0}])
