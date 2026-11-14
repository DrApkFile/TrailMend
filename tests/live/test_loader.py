import pytest

from trailmend.data import dataset
from trailmend.data.northwind import Sizes
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.graph.loader import INITIAL_COST, count_graph, load
from trailmend.graph.schema import RelType

pytestmark = pytest.mark.hydra

SEED = 5_150
SMALL = Sizes(people=30, teams=5, services=10, alerts=16, customers=6, incidents=4, runbooks=6, repos=4)


@pytest.fixture(scope="module")
def built() -> dataset.Dataset:
    return dataset.build(SEED, SMALL)


def test_c1_loading_g0_writes_every_node_and_edge(hydra: HydraClient, built: dataset.Dataset) -> None:
    report = load(hydra, built.graph)
    assert report.nodes_written == len(built.graph.nodes)
    assert report.edges_written == len(built.graph.edges)
    assert report.batches > 0


def test_c1_a_reload_adds_nothing(hydra: HydraClient, built: dataset.Dataset) -> None:
    load(hydra, built.graph)
    before_nodes, before_edges = count_graph(hydra, built.graph)
    load(hydra, built.graph)
    after_nodes, after_edges = count_graph(hydra, built.graph)
    assert after_nodes == before_nodes
    assert after_edges == before_edges


def test_c1_every_loaded_edge_starts_at_cost_one_with_no_judgements(hydra: HydraClient, built: dataset.Dataset) -> None:
    load(hydra, built.graph)
    checked = 0
    for rel_type in (RelType.OWNED_BY, RelType.ON_CALL, RelType.ALERTS_ON):
        for edge in built.graph.edges_of_type(rel_type)[:3]:
            result = hydra.run(q.read_edge(rel_type.value), {"src": edge.src, "dst": edge.dst})
            assert result.rows == ((INITIAL_COST, 0, 0, ""),)
            checked += 1
    assert checked >= 9


def test_c1_a_batch_larger_than_the_limit_is_refused(hydra: HydraClient, built: dataset.Dataset) -> None:
    with pytest.raises(ValueError, match="batch_size must be between"):
        load(hydra, built.graph, batch_size=1001)
