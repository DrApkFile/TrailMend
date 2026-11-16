from dataclasses import replace

import pytest

from trailmend.core.model import SearchConfig
from trailmend.data import dataset
from trailmend.graph.client import HydraClient
from trailmend.graph.reset import reset_to_ingested
from trailmend.graph.schema import NodeLabel, RelType
from trailmend.search.answer import AnswerFound, answer

pytestmark = pytest.mark.hydra


def test_run4_live_set_answer_keeps_both_members_when_their_document_costs_differ(hydra: HydraClient) -> None:
    built = dataset.build(9191, data_version="v2")
    edges = built.graph.edges_of_type(RelType.SERVES)
    first = next(edge for edge in edges if sum(other.src == edge.src for other in edges) >= 2)
    second = next(edge for edge in edges if edge.src == first.src and edge.dst != first.dst)
    ids = {first.src, first.dst, second.dst}
    graph = replace(
        built.graph, nodes=tuple(node for node in built.graph.nodes if node.id in ids), edges=(first, second)
    )
    reset_to_ingested(hydra, graph, (), {first.id: 3, second.id: 1})
    weighted = answer(hydra, first.src, ("SERVES",), NodeLabel.CUSTOMER, SearchConfig(1, 100), multi_answer=True)
    hybrid = answer(
        hydra, first.src, ("SERVES",), NodeLabel.CUSTOMER, SearchConfig(1, 100, unweighted_sets=True), multi_answer=True
    )
    assert isinstance(weighted, AnswerFound)
    assert set(weighted.answer_ids) == {first.dst}
    assert isinstance(hybrid, AnswerFound)
    assert set(hybrid.answer_ids) == {first.dst, second.dst}
