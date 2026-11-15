from pathlib import Path

import pytest

from trailmend.eval.analyse_v2 import (
    captured_share,
    hypotheses,
    oracle_rows,
    require_v2,
    run_id_of,
    wrong_rate,
)

SEED = 1
FINAL = 2


def _curve_row(arm: str, round_index: int, accuracy: float, wrong: int) -> dict[str, object]:
    return {
        "arm": arm,
        "seed": SEED,
        "round": round_index,
        "run_id": "r2",
        "data_version": "v2",
        "held_out": {"n": 100, "correct": int(accuracy * 100), "accuracy": accuracy, "wrong": wrong},
        "gapfill_reached": 10,
        "gapfill_ingested": 9,
    }


def _rows(final_accuracy: float = 0.9, final_wrong: int = 5) -> list[dict[str, object]]:
    rows = [_curve_row("full_v2", 0, 0.8, 20), _curve_row("full_v2", 1, 0.85, 12)]
    rows.append(_curve_row("full_v2", FINAL, final_accuracy, final_wrong))
    rows += [_curve_row("plain_store", r, 0.25, 40) for r in range(FINAL + 1)]
    return rows


def _pair(arm: str, reference: str, delta: float, p_value: float) -> dict[str, object]:
    return {"seed": SEED, "arm": arm, "reference": reference, "delta_points": delta, "p_value": p_value}


def _pairs(delta: float = 5.0, p_value: float = 0.001) -> list[dict[str, object]]:
    return [
        _pair("full_v2", "frozen", delta, p_value),
        _pair("full_v2", "full_v1_rule", 3.0, 0.01),
        _pair("random_reweight", "frozen", -4.0, 0.9),
        _pair("random_quarantine", "frozen", -2.0, 0.5),
    ]


def _quarantines() -> list[dict[str, object]]:
    return [
        {
            "seed": SEED,
            "arm": "full_v2",
            "recall_on_planted_wrong_edges": 0.8,
            "false_quarantine_rate": 0.05,
        }
    ]


def _breaks() -> list[dict[str, object]]:
    return [{"seed": SEED, "arm": "full_v2", "round": 1, "newly_broken": 1, "correct": 100}]


def _verdict(rows: list[dict[str, object]], pairs: list[dict[str, object]], which: str) -> str:
    decided = hypotheses(rows, _breaks(), _quarantines(), pairs, FINAL)
    return str(next(v["verdict"] for v in decided if v["id"] == which))


def test_a_significant_two_point_gain_passes_h1() -> None:
    assert _verdict(_rows(), _pairs(), "H1'") == "PASS"


def test_a_gain_that_is_significant_but_under_two_points_fails_h1() -> None:
    assert _verdict(_rows(), _pairs(delta=1.5), "H1'") == "FAIL"


def test_a_two_point_gain_that_could_be_chance_fails_h1() -> None:
    assert _verdict(_rows(), _pairs(p_value=0.2), "H1'") == "FAIL"


def test_a_random_control_that_beats_frozen_fails_h2() -> None:
    pairs = _pairs()
    pairs[2] = _pair("random_reweight", "frozen", 3.0, 0.001)
    assert _verdict(_rows(), pairs, "H2'") == "FAIL"


def test_the_wrong_answer_rate_has_to_fall_by_forty_percent_for_h6() -> None:
    assert _verdict(_rows(final_wrong=12), _pairs(), "H6'") == "PASS"
    assert _verdict(_rows(final_wrong=13), _pairs(), "H6'") == "FAIL"


def test_no_hypothesis_is_decided_from_an_empty_input() -> None:
    for breaks, quarantines, pairs in (
        ([], _quarantines(), _pairs()),
        (_breaks(), [], _pairs()),
        (_breaks(), _quarantines(), []),
    ):
        with pytest.raises(ValueError, match="cannot be decided"):
            hypotheses(_rows(), breaks, quarantines, pairs, FINAL)


def test_a_curve_that_mixes_runs_is_refused() -> None:
    rows = _rows()
    rows[0] = dict(rows[0]) | {"run_id": "other"}
    with pytest.raises(ValueError, match="mixes runs"):
        run_id_of(rows)


def test_run_one_data_is_refused_by_the_run_two_analysis() -> None:
    rows = [dict(row) | {"data_version": "v1"} for row in _rows()]
    with pytest.raises(ValueError, match="data versions"):
        require_v2(rows)


def test_a_missing_oracle_ladder_stops_the_analysis_rather_than_defaulting() -> None:
    with pytest.raises(FileNotFoundError, match="oracle ladder on data v2"):
        oracle_rows(Path("evidence/oracle_that_was_never_run.json"))


def test_a_ladder_with_no_reachable_gain_is_refused_rather_than_divided_by() -> None:
    ladder = [
        {"seed": SEED, "stage": "g0", "held_out_accuracy": 0.8},
        {"seed": SEED, "stage": "and_ingest_withheld_edges", "held_out_accuracy": 0.8},
    ]
    with pytest.raises(ValueError, match="no reachable gain"):
        captured_share(_rows(), ladder, [SEED], FINAL)


def test_the_captured_share_is_what_was_gained_over_what_was_reachable() -> None:
    ladder = [
        {"seed": SEED, "stage": "g0", "held_out_accuracy": 0.8},
        {"seed": SEED, "stage": "and_ingest_withheld_edges", "held_out_accuracy": 0.9},
    ]
    row = captured_share(_rows(final_accuracy=0.85), ladder, [SEED], FINAL)[0]
    assert row["captured_share"] == 0.5
    assert row["reachable_points"] == 10.0


def test_the_wrong_answer_rate_is_read_from_the_curve() -> None:
    assert wrong_rate(_rows(), "full_v2", SEED, 0) == 0.2
