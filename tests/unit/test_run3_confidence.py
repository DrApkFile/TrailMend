from collections.abc import Sequence
from typing import cast

import pytest

from trailmend.core.model import EdgeKey, EdgeState, SearchConfig
from trailmend.errors import ErrorCode
from trailmend.eval.v3.analyse import aggregate, complete, reductions
from trailmend.eval.v3.calibration import cutoff
from trailmend.eval.v3.files import ARMS, ROUNDS, SEEDS
from trailmend.graph.client import HydraClient, Params, QueryResult
from trailmend.graph.queries import NamedQuery
from trailmend.graph.schema import NodeLabel
from trailmend.graph.values import PathRel, PathValue
from trailmend.search.answer import AnswerFound, AnswerRefused, answer
from trailmend.search.confidence import uses_unconfirmed


@pytest.mark.parametrize(("cost", "limit", "refused"), [(1.0, 1.0, False), (1.01, 1.0, True), (0.99, 1.0, False)])
def test_run3_cost_gate_accepts_equality_and_refuses_only_above_the_fixed_cutoff(
    monkeypatch: pytest.MonkeyPatch, cost: float, limit: float, refused: bool
) -> None:
    path = PathValue((1, 2), (PathRel("ON_CALL", 1, 2, {}),))

    def run(_self: HydraClient, _query: NamedQuery, _params: Params) -> QueryResult:
        return QueryResult("test", "test", ("path", "weight"), ((path, cost),))

    monkeypatch.setattr(HydraClient, "run", run)
    with HydraClient("http://127.0.0.1:1", "test-token", "default", "cell-0", 1.0) as client:
        result = answer(client, 1, ("ON_CALL",), NodeLabel.PERSON, SearchConfig(1, 10, max_answer_cost=limit))
    if refused:
        assert isinstance(result, AnswerRefused)
        assert result.code is ErrorCode.LOW_CONFIDENCE
    else:
        assert isinstance(result, AnswerFound)


@pytest.mark.parametrize("shortcut", [False, True])
@pytest.mark.parametrize("confirms", [0, 1])
def test_run3_gap_filled_edges_require_confirmation_even_inside_a_shortcut(
    monkeypatch: pytest.MonkeyPatch, shortcut: bool, confirms: int
) -> None:
    pool = EdgeKey(1, "OWNED_BY", 2)
    compressed = EdgeKey(1, "SC_service_owner_team", 2)
    states = {pool: EdgeState(pool, 1.0, confirms=confirms), compressed: EdgeState(compressed, 1.0, via_path=(pool,))}

    def read(_client: HydraClient, keys: Sequence[EdgeKey]) -> dict[EdgeKey, EdgeState]:
        return {key: states[key] for key in keys}

    monkeypatch.setattr("trailmend.search.confidence.read_states", read)
    client = cast("HydraClient", object())
    assert uses_unconfirmed(client, ((compressed if shortcut else pool,),), frozenset({pool})) is (confirms == 0)


def test_run3_training_quantile_is_nearest_rank_without_interpolation_or_a_hidden_empty_fallback() -> None:
    assert cutoff([3.0, 1.0, 2.0], 0.95) == 3.0
    assert cutoff([3.0, 1.0, 2.0], 0.5) == 2.0
    assert cutoff([], 0.95) == 0.0
    with pytest.raises(ValueError, match="quantile"):
        cutoff([1.0], 0.0)


def test_run3_a_partial_or_duplicated_grid_cannot_produce_hypothesis_verdicts() -> None:
    rows = [
        dict[str, object](seed=s, arm=a, round=r, run_id="v3-test")
        for s in SEEDS
        for a in ARMS
        for r in range(ROUNDS + 1)
    ]
    assert complete(rows) == "v3-test"
    with pytest.raises(ValueError, match="complete unique"):
        complete(rows[:-1])
    with pytest.raises(ValueError, match="complete unique"):
        complete([*rows[:-1], rows[0]])


def test_run3_zero_wrong_baselines_do_not_turn_into_claimed_reductions() -> None:
    assert reductions(0, 0) == "INCONCLUSIVE"
    assert reductions(0, 1) == "FAIL"
    assert reductions(10, 6) == "PASS"
    assert reductions(10, 7) == "FAIL"
    assert aggregate(["PASS", "INCONCLUSIVE"]) == "INCONCLUSIVE"
    assert aggregate(["FAIL", "INCONCLUSIVE"]) == "FAIL"
