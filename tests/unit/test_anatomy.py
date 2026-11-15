from trailmend.core.model import EdgeKey
from trailmend.data.questions import Question
from trailmend.errors import ErrorCode
from trailmend.eval import anatomy
from trailmend.graph.schema import NodeLabel, RelType
from trailmend.loop.evaluate import Judged, Verdict

OWNS = RelType.OWNED_BY
ON_CALL = RelType.ON_CALL


def question(gold: tuple[int, ...]) -> Question:
    return Question("q-1", "service_owner_team", "who owns 1?", 1, "one", NodeLabel.TEAM, 2, gold)


def judged(
    verdict: Verdict,
    paths: tuple[tuple[EdgeKey, ...], ...] = (),
    refusal: ErrorCode | None = None,
    gold: tuple[int, ...] = (9,),
) -> Judged:
    return Judged("q-1", "service_owner_team", 1, verdict, refusal, (), gold, paths)


def facts(**kwargs: frozenset[EdgeKey] | frozenset[int]) -> anatomy.FaultIndex:
    empty: frozenset[EdgeKey] = frozenset()
    fields: dict[str, object] = {
        "wrong_added": empty,
        "wrong_removed": empty,
        "withheld": empty,
        "alias_added": empty,
        "alias_removed": empty,
        "conflation_added": empty,
        "conflation_removed": empty,
        "duplicate_ids": frozenset[int](),
        "absorbed_ids": frozenset[int](),
    }
    fields.update(kwargs)
    return anatomy.FaultIndex(**fields)  # pyright: ignore[reportArgumentType]


def test_the_truth_path_holds_only_the_edges_that_reach_the_gold() -> None:
    links = {(1, OWNS): (2, 3), (2, ON_CALL): (9,), (3, ON_CALL): (8,)}
    edges = anatomy.truth_path_edges(question((9,)), (OWNS, ON_CALL), links)
    assert edges == frozenset({EdgeKey(1, OWNS.value, 2), EdgeKey(2, ON_CALL.value, 9)})


def test_a_question_whose_true_edge_was_replaced_is_blamed_on_the_planted_wrong_edge() -> None:
    true_edge = EdgeKey(1, OWNS.value, 2)
    found = anatomy.anatomy_of(
        judged(Verdict.WRONG, ((EdgeKey(1, OWNS.value, 5),),)),
        frozenset({true_edge}),
        facts(wrong_removed=frozenset({true_edge}), wrong_added=frozenset({EdgeKey(1, OWNS.value, 5)})),
    )
    assert found.cause == anatomy.PLANTED_WRONG_EDGE
    assert found.wrong_edge_on_chosen_path
    assert found.true_edge_replaced


def test_a_question_whose_true_edge_was_withheld_is_blamed_on_the_missing_edge() -> None:
    true_edge = EdgeKey(1, OWNS.value, 2)
    found = anatomy.anatomy_of(
        judged(Verdict.UNREACHABLE, refusal=ErrorCode.UNREACHABLE),
        frozenset({true_edge}),
        facts(withheld=frozenset({true_edge})),
    )
    assert found.cause == anatomy.MISSING_EDGE
    assert not found.true_edge_replaced


def test_a_refused_tie_with_no_planted_fault_on_the_path_is_a_tie() -> None:
    found = anatomy.anatomy_of(
        judged(Verdict.REFUSED, refusal=ErrorCode.AMBIGUOUS_ANSWER), frozenset({EdgeKey(1, OWNS.value, 2)}), facts()
    )
    assert found.cause == anatomy.TIE
    assert found.also == ()


def test_every_other_cause_that_applies_is_kept_beside_the_first() -> None:
    true_edge = EdgeKey(1, OWNS.value, 2)
    found = anatomy.anatomy_of(
        judged(Verdict.REFUSED, refusal=ErrorCode.AMBIGUOUS_ANSWER),
        frozenset({true_edge}),
        facts(withheld=frozenset({true_edge}), wrong_removed=frozenset({true_edge})),
    )
    assert found.cause == anatomy.PLANTED_WRONG_EDGE
    assert found.also == (anatomy.MISSING_EDGE, anatomy.TIE)


def test_a_failure_with_no_planted_fault_anywhere_near_it_is_other() -> None:
    found = anatomy.anatomy_of(judged(Verdict.WRONG, ((EdgeKey(1, OWNS.value, 7),),)), frozenset(), facts())
    assert found.cause == anatomy.OTHER
