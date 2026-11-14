import pytest

from trailmend.core.model import EdgeKey, SearchConfig
from trailmend.errors import ErrorCode
from trailmend.graph.schema import NodeLabel, RelType
from trailmend.graph.values import PathRel, PathValue
from trailmend.search.answer import AnswerFound, AnswerRefused, pick_answer, score_paths


def _path(*hops: tuple[int, RelType, int]) -> PathValue:
    nodes = (hops[0][0], *[hop[2] for hop in hops])
    rels = tuple(PathRel(rel.value, src, dst, {}) for src, rel, dst in hops)
    return PathValue(nodes, rels)


def _row(cost: float, *hops: tuple[int, RelType, int]) -> tuple[object, object]:
    return (_path(*hops), cost)


ALERT, SERVICE, TEAM, ALICE, BOB = 1, 2, 3, 4, 5


def test_c3_the_terminal_label_comes_from_the_last_relationship_type() -> None:
    scored = score_paths([_row(2.0, (ALERT, RelType.ALERTS_ON, SERVICE), (SERVICE, RelType.OWNED_BY, TEAM))])
    assert len(scored) == 1
    assert scored[0].terminal == TEAM
    assert scored[0].terminal_label is NodeLabel.TEAM
    assert scored[0].cost == 2.0


def test_c3_the_cheapest_node_of_the_expected_label_is_the_answer() -> None:
    rows = [
        _row(1.0, (ALERT, RelType.ALERTS_ON, SERVICE)),
        _row(2.0, (ALERT, RelType.ALERTS_ON, SERVICE), (SERVICE, RelType.OWNED_BY, TEAM)),
        _row(5.0, (TEAM, RelType.ON_CALL, ALICE)),
        _row(3.0, (TEAM, RelType.ON_CALL, BOB)),
    ]
    outcome = pick_answer(score_paths(rows), NodeLabel.PERSON)
    assert isinstance(outcome, AnswerFound)
    assert outcome.answer_ids == (BOB,)
    assert outcome.cost == 3.0
    assert outcome.paths == ((EdgeKey(TEAM, RelType.ON_CALL.value, BOB),),)


def test_c3_two_different_nodes_tied_on_cost_refuse_rather_than_guess() -> None:
    rows = [_row(3.0, (TEAM, RelType.ON_CALL, ALICE)), _row(3.0, (TEAM, RelType.ON_CALL, BOB))]
    outcome = pick_answer(score_paths(rows), NodeLabel.PERSON)
    assert isinstance(outcome, AnswerRefused)
    assert outcome.code is ErrorCode.AMBIGUOUS_ANSWER
    assert outcome.candidates == (ALICE, BOB)


def test_c3_one_node_reached_twice_at_the_same_cost_is_still_one_answer() -> None:
    rows = [_row(3.0, (TEAM, RelType.ON_CALL, ALICE)), _row(3.0, (TEAM, RelType.ON_CALL, ALICE))]
    outcome = pick_answer(score_paths(rows), NodeLabel.PERSON)
    assert isinstance(outcome, AnswerFound)
    assert outcome.answer_ids == (ALICE,)


def test_c3_nothing_of_the_expected_label_is_unreachable() -> None:
    outcome = pick_answer(score_paths([_row(1.0, (ALERT, RelType.ALERTS_ON, SERVICE))]), NodeLabel.PERSON)
    assert isinstance(outcome, AnswerRefused)
    assert outcome.code is ErrorCode.UNREACHABLE


def test_c3_a_row_that_is_not_a_path_is_refused_loudly() -> None:
    with pytest.raises(TypeError, match="expected a path"):
        score_paths([("not a path", 1.0)])


def test_c3_a_weight_that_is_not_a_number_is_refused_loudly() -> None:
    with pytest.raises(TypeError, match="pathWeight must be a number"):
        score_paths([_row("heavy", (TEAM, RelType.ON_CALL, ALICE))])  # pyright: ignore[reportArgumentType]


def test_c3_a_search_config_outside_the_supported_range_is_refused() -> None:
    with pytest.raises(ValueError, match="max_len must be between 1 and 4"):
        SearchConfig(max_len=9, result_limit=10)
    with pytest.raises(ValueError, match="result_limit must be between 1 and 500"):
        SearchConfig(max_len=3, result_limit=0)


def test_c3a_a_multi_answer_template_returns_every_entity_tied_at_the_lowest_cost() -> None:
    rows = [
        _row(3.0, (TEAM, RelType.ON_CALL, ALICE)),
        _row(3.0, (TEAM, RelType.ON_CALL, BOB)),
        _row(9.0, (TEAM, RelType.ON_CALL, 6)),
    ]
    outcome = pick_answer(score_paths(rows), NodeLabel.PERSON, multi_answer=True)
    assert isinstance(outcome, AnswerFound)
    assert outcome.answer_ids == (ALICE, BOB)
    assert outcome.cost == 3.0
    assert len(outcome.paths) == 2


def test_c3a_costs_that_differ_below_one_part_in_a_billion_count_as_tied() -> None:
    rows = [_row(3.0, (TEAM, RelType.ON_CALL, ALICE)), _row(3.0 + 1e-12, (TEAM, RelType.ON_CALL, BOB))]
    outcome = pick_answer(score_paths(rows), NodeLabel.PERSON, multi_answer=True)
    assert isinstance(outcome, AnswerFound)
    assert outcome.answer_ids == (ALICE, BOB)


def test_c3a_costs_that_differ_above_one_part_in_a_billion_are_not_tied() -> None:
    rows = [_row(3.0, (TEAM, RelType.ON_CALL, ALICE)), _row(3.0 + 1e-6, (TEAM, RelType.ON_CALL, BOB))]
    outcome = pick_answer(score_paths(rows), NodeLabel.PERSON, multi_answer=True)
    assert isinstance(outcome, AnswerFound)
    assert outcome.answer_ids == (ALICE,)


def test_c3a_a_single_answer_template_still_refuses_a_tie() -> None:
    rows = [_row(3.0, (TEAM, RelType.ON_CALL, ALICE)), _row(3.0, (TEAM, RelType.ON_CALL, BOB))]
    outcome = pick_answer(score_paths(rows), NodeLabel.PERSON, multi_answer=False)
    assert isinstance(outcome, AnswerRefused)
    assert outcome.code is ErrorCode.AMBIGUOUS_ANSWER


def test_c3a_asking_a_set_answer_for_its_single_entity_is_refused_loudly() -> None:
    rows = [_row(3.0, (TEAM, RelType.ON_CALL, ALICE)), _row(3.0, (TEAM, RelType.ON_CALL, BOB))]
    outcome = pick_answer(score_paths(rows), NodeLabel.PERSON, multi_answer=True)
    assert isinstance(outcome, AnswerFound)
    with pytest.raises(ValueError, match="holds 2 entities, not one"):
        _ = outcome.answer_id
