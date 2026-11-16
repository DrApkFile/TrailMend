from dataclasses import replace

import pytest

from trailmend.core.model import EdgeKey, SearchConfig
from trailmend.data import dataset
from trailmend.data.northwind import Sizes
from trailmend.errors import ErrorCode
from trailmend.graph.client import HydraClient
from trailmend.graph.reset import reset_to_ingested
from trailmend.graph.schema import NodeLabel, RelType
from trailmend.search.answer import AnswerFound, AnswerRefused, answer

pytestmark = pytest.mark.hydra


def test_run3_a_live_gap_link_is_refused_until_confirmed_and_the_original_search_still_answers(
    hydra: HydraClient,
) -> None:
    built = dataset.build(
        8181, Sizes(people=30, teams=5, services=10, alerts=16, customers=6, incidents=4, runbooks=6, repos=4)
    )
    pool = tuple((e.src, e.rel_type.value, e.dst) for e in built.ingested.pool)
    reset_to_ingested(hydra, built.graph, pool, built.support)
    edge = built.graph.edges_of_type(RelType.ON_CALL)[0]
    key = EdgeKey(edge.src, edge.rel_type.value, edge.dst)
    normal = SearchConfig(1, 100)
    result = answer(hydra, edge.src, ("ON_CALL",), NodeLabel.PERSON, normal)
    assert isinstance(result, AnswerFound)
    gated = answer(hydra, edge.src, ("ON_CALL",), NodeLabel.PERSON, replace(normal, gapfill_edges=frozenset({key})))
    assert isinstance(gated, AnswerRefused)
    assert gated.code is ErrorCode.LOW_CONFIDENCE
    costly = answer(
        hydra, edge.src, ("ON_CALL",), NodeLabel.PERSON, replace(normal, max_answer_cost=result.cost - 0.01)
    )
    assert isinstance(costly, AnswerRefused)
    assert costly.code is ErrorCode.LOW_CONFIDENCE
