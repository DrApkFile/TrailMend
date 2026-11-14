import pytest

from trailmend.data.faultmodel import Ingested, replay, to_json
from trailmend.data.faults import SWAPPABLE, FaultPlan, inject
from trailmend.data.model import require_consistent
from trailmend.data.northwind import Sizes, generate
from trailmend.graph.schema import NodeLabel, RelType

SEED = 7


@pytest.fixture(scope="module")
def ingested() -> Ingested:
    return inject(generate(SEED))


def test_b2_g0_is_exactly_the_truth_graph_with_the_declared_faults_replayed(ingested: Ingested) -> None:
    truth = generate(SEED)
    assert set(ingested.graph.edges) == set(replay(truth, ingested.faults))


def test_b2_every_edge_that_differs_from_the_truth_graph_is_declared_by_a_fault(ingested: Ingested) -> None:
    truth = generate(SEED)
    assert set(truth.edges) - set(ingested.graph.edges) == set(ingested.faults.removed_edges())
    assert set(ingested.graph.edges) - set(truth.edges) == set(ingested.faults.added_edges())


def test_b2_no_edge_carries_more_than_one_fault(ingested: Ingested) -> None:
    removed = [(e.src, e.rel_type, e.dst) for e in ingested.faults.removed_edges()]
    added = [(e.src, e.rel_type, e.dst) for e in ingested.faults.added_edges()]
    assert len(set(removed)) == len(removed)
    assert len(set(added)) == len(added)
    assert not set(removed) & set(added)


def test_b2_the_withheld_pool_is_exactly_the_declared_missing_edges(ingested: Ingested) -> None:
    declared = {(f.src, f.rel_type, f.dst) for f in ingested.faults.missing_edges}
    assert {(e.src, e.rel_type, e.dst) for e in ingested.pool} == declared
    assert not declared & {(e.src, e.rel_type, e.dst) for e in ingested.graph.edges}


def test_b2_a_wrong_edge_keeps_its_source_and_points_at_a_plausible_wrong_target(ingested: Ingested) -> None:
    truth = generate(SEED)
    by_id = truth.by_id
    assert ingested.faults.wrong_edges
    for fault in ingested.faults.wrong_edges:
        assert fault.rel_type in SWAPPABLE
        assert fault.wrong_dst != fault.true_dst
        assert by_id[fault.wrong_dst].label is by_id[fault.true_dst].label
        assert (fault.src, fault.rel_type, fault.wrong_dst) in {
            (e.src, e.rel_type, e.dst) for e in ingested.graph.edges
        }


def test_b2_the_planted_shares_match_the_plan(ingested: Ingested) -> None:
    truth = generate(SEED)
    swappable = [e for e in truth.edges if e.rel_type in SWAPPABLE]
    plan = FaultPlan()
    assert len(ingested.faults.wrong_edges) == round(len(swappable) * plan.wrong_edge_share)
    withholdable = len(truth.edges) - len(ingested.faults.wrong_edges)
    assert len(ingested.faults.missing_edges) == round(withholdable * plan.missing_edge_share)
    services = truth.nodes_with_label(NodeLabel.SERVICE)
    assert len(ingested.faults.alias_duplicates) == round(len(services) * plan.alias_duplicate_share)
    assert len(ingested.faults.conflations) == plan.conflated_people


def test_b2_each_alias_duplicate_is_a_second_service_node_that_steals_some_alerts(ingested: Ingested) -> None:
    by_id = ingested.graph.by_id
    assert ingested.faults.alias_duplicates
    for fault in ingested.faults.alias_duplicates:
        duplicate = by_id[fault.duplicate_id]
        assert duplicate.label is NodeLabel.SERVICE
        assert duplicate.name == fault.duplicate_name
        assert by_id[fault.original_id].label is NodeLabel.SERVICE
        for edge in fault.delta.added:
            assert edge.rel_type is RelType.ALERTS_ON
            assert edge.dst == fault.duplicate_id


def test_b2_the_conflated_person_keeps_one_node_carrying_both_names(ingested: Ingested) -> None:
    truth = generate(SEED)
    assert len(ingested.faults.conflations) == 1
    fault = ingested.faults.conflations[0]
    assert fault.absorbed_id not in ingested.graph.by_id
    assert fault.absorbed_id in truth.by_id
    kept = ingested.graph.node(fault.kept_id)
    assert kept.name == fault.kept_name
    assert fault.absorbed_name in kept.aliases
    for edge in fault.delta.added:
        assert fault.absorbed_id not in (edge.src, edge.dst)


def test_b2_g0_stays_internally_consistent(ingested: Ingested) -> None:
    require_consistent(ingested.graph.nodes, ingested.graph.edges)


def test_b2_the_same_seed_plants_the_same_faults(ingested: Ingested) -> None:
    assert to_json(inject(generate(SEED)).faults) == to_json(ingested.faults)


def test_b2_a_different_seed_plants_different_faults(ingested: Ingested) -> None:
    assert to_json(inject(generate(SEED + 1)).faults) != to_json(ingested.faults)


def test_b2_planting_nothing_leaves_the_graph_untouched() -> None:
    truth = generate(
        SEED, Sizes(people=40, teams=6, services=12, alerts=20, customers=8, incidents=5, runbooks=7, repos=5)
    )
    quiet = inject(truth, FaultPlan(0.0, 0.0, 0.0, 0))
    assert set(quiet.graph.edges) == set(truth.edges)
    assert quiet.graph.nodes == truth.nodes
    assert quiet.pool == ()


def test_b2_an_impossible_share_is_refused() -> None:
    with pytest.raises(ValueError, match="wrong_edge_share must be in"):
        FaultPlan(wrong_edge_share=0.9)
