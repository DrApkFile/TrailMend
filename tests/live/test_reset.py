from dataclasses import replace

import pytest

from trailmend.core.model import EdgeKey
from trailmend.data import dataset
from trailmend.data.model import Edge, make_edge
from trailmend.data.northwind import Sizes
from trailmend.graph.client import HydraClient
from trailmend.graph.loader import load
from trailmend.graph.reset import reset_to_ingested
from trailmend.graph.schema import NORTHWIND_REL_TYPES, NodeLabel, RelType
from trailmend.graph.state import list_edge_keys, read_state

pytestmark = pytest.mark.hydra

SEED = 5_151
SMALL = Sizes(people=30, teams=5, services=10, alerts=16, customers=6, incidents=4, runbooks=6, repos=4)


@pytest.fixture(scope="module")
def built() -> dataset.Dataset:
    return dataset.build(SEED, SMALL)


def _edge_g0_does_not_have(built: dataset.Dataset) -> Edge:
    graph = built.graph
    member_of = graph.edges_of_type(RelType.MEMBER_OF)[0]
    present = {(e.src, e.rel_type, e.dst) for e in graph.edges}
    for team in graph.nodes_with_label(NodeLabel.TEAM):
        candidate = make_edge(graph.node(member_of.src), RelType.MEMBER_OF, team)
        if (candidate.src, candidate.rel_type, candidate.dst) not in present:
            return candidate
    raise AssertionError("this graph connects one person to every team, so nothing can be added")


def test_a_reset_removes_an_edge_the_ingested_graph_does_not_have(hydra: HydraClient, built: dataset.Dataset) -> None:
    extra = _edge_g0_does_not_have(built)
    load(hydra, replace(built.graph, edges=(*built.graph.edges, extra)), built.support)
    key = EdgeKey(extra.src, extra.rel_type.value, extra.dst)
    assert read_state(hydra, key) is not None
    wanted = {EdgeKey(edge.src, edge.rel_type.value, edge.dst) for edge in built.graph.edges}
    before = {edge for rel_type in NORTHWIND_REL_TYPES for edge in list_edge_keys(hydra, rel_type.value)}

    report = reset_to_ingested(hydra, built.graph, (), built.support)

    assert report.edges_pruned == len(before - wanted)
    assert read_state(hydra, key) is None


def test_a_reset_leaves_only_edges_the_ingested_graph_has(hydra: HydraClient, built: dataset.Dataset) -> None:
    load(hydra, replace(built.graph, edges=(*built.graph.edges, _edge_g0_does_not_have(built))), built.support)

    reset_to_ingested(hydra, built.graph, (), built.support)

    wanted = {(edge.src, edge.rel_type.value, edge.dst) for edge in built.graph.edges}
    found = {
        (key.src, rel_type.value, key.dst)
        for rel_type in NORTHWIND_REL_TYPES
        for key in list_edge_keys(hydra, rel_type.value)
    }
    assert found == wanted
