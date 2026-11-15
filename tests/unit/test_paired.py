import pytest

from trailmend.eval.paired import compare, mcnemar_exact


def test_no_disagreement_at_all_cannot_be_evidence_of_a_difference() -> None:
    assert mcnemar_exact(0, 0) == 1.0


def test_a_single_disagreement_is_not_significant() -> None:
    assert mcnemar_exact(1, 0) == 1.0


def test_five_disagreements_all_one_way_is_the_hand_checkable_case() -> None:
    assert mcnemar_exact(5, 0) == 0.0625


def test_ten_disagreements_all_one_way_clears_the_preregistered_threshold() -> None:
    assert mcnemar_exact(10, 0) == 0.001953125
    assert mcnemar_exact(10, 0) < 0.05


def test_an_even_split_is_as_unremarkable_as_it_looks() -> None:
    assert mcnemar_exact(6, 6) == 1.0


def test_the_test_does_not_care_which_side_won() -> None:
    assert mcnemar_exact(9, 1) == mcnemar_exact(1, 9)


def test_eight_against_one_is_decided_by_both_tails() -> None:
    assert mcnemar_exact(8, 1) == 0.0390625


def test_a_negative_count_is_refused_rather_than_absorbed() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        mcnemar_exact(-1, 2)


def test_counting_pairs_splits_them_four_ways() -> None:
    arm = {"a": True, "b": True, "c": False, "d": False}
    reference = {"a": True, "b": False, "c": True, "d": False}
    result = compare(arm, reference)
    assert (result.both_correct, result.only_first, result.only_second, result.neither) == (1, 1, 1, 1)
    assert result.n == 4
    assert result.delta_points == 0.0


def test_a_paired_test_refuses_two_different_question_sets() -> None:
    with pytest.raises(ValueError, match="same held-out questions"):
        compare({"a": True}, {"b": True})


def test_the_delta_is_reported_in_points_of_accuracy() -> None:
    arm = {f"q{i}": i < 60 for i in range(100)}
    reference = {f"q{i}": i < 50 for i in range(100)}
    assert compare(arm, reference).delta_points == 10.0
