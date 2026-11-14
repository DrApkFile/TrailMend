import hashlib
import os
import subprocess
import sys
from collections import Counter, defaultdict

import pytest

from trailmend.data.model import TruthGraph, to_json
from trailmend.data.northwind import Sizes, generate, label_counts
from trailmend.graph.schema import ENDPOINTS, NodeLabel, RelType

SEED = 7
SMALL = Sizes(people=40, teams=6, services=12, alerts=20, customers=8, incidents=5, runbooks=7, repos=5)


@pytest.fixture(scope="module")
def graph() -> TruthGraph:
    return generate(SEED)


def _digest(graph: TruthGraph) -> str:
    return hashlib.sha256(to_json(graph).encode()).hexdigest()


def test_b1_the_same_seed_produces_byte_identical_json(graph: TruthGraph) -> None:
    assert to_json(generate(SEED)) == to_json(graph)


def test_b1_the_json_digest_survives_a_fresh_interpreter_with_a_different_hash_seed(graph: TruthGraph) -> None:
    script = (
        "import hashlib;"
        "from trailmend.data.northwind import generate;"
        "from trailmend.data.model import to_json;"
        f"print(hashlib.sha256(to_json(generate({SEED})).encode()).hexdigest())"
    )
    env = {**os.environ, "PYTHONHASHSEED": "12345"}
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True, env=env)
    assert out.stdout.strip() == _digest(graph)


def test_b1_different_seeds_produce_different_graphs(graph: TruthGraph) -> None:
    assert _digest(generate(SEED + 1)) != _digest(graph)


def test_b1_the_truth_graph_has_the_sizes_the_plan_asks_for(graph: TruthGraph) -> None:
    assert label_counts(graph) == {
        NodeLabel.PERSON.value: 400,
        NodeLabel.TEAM.value: 40,
        NodeLabel.SERVICE.value: 120,
        NodeLabel.ALERT.value: 300,
        NodeLabel.CUSTOMER.value: 80,
        NodeLabel.INCIDENT.value: 60,
        NodeLabel.RUNBOOK.value: 90,
        NodeLabel.REPO.value: 70,
    }


def test_b1_every_edge_joins_two_known_nodes_with_the_labels_its_type_declares(graph: TruthGraph) -> None:
    by_id = graph.by_id
    for edge in graph.edges:
        source, target = ENDPOINTS[edge.rel_type]
        assert by_id[edge.src].label is source
        assert by_id[edge.dst].label is target


def test_b1_every_alert_reaches_a_person_within_three_hops(graph: TruthGraph) -> None:
    out = graph.out_edges()

    def step(node_id: int, rel_type: RelType) -> list[int]:
        return [e.dst for e in out.get(node_id, ()) if e.rel_type is rel_type]

    for alert in graph.nodes_with_label(NodeLabel.ALERT):
        services = step(alert.id, RelType.ALERTS_ON)
        teams = [t for s in services for t in step(s, RelType.OWNED_BY)]
        people = [p for t in teams for p in step(t, RelType.ON_CALL)]
        assert len(people) == 1, f"{alert.name} pages {len(people)} people"
        assert graph.node(people[0]).label is NodeLabel.PERSON


def test_b1_each_alert_service_and_team_has_exactly_one_outgoing_routing_edge(graph: TruthGraph) -> None:
    for rel_type, label in (
        (RelType.ALERTS_ON, NodeLabel.ALERT),
        (RelType.OWNED_BY, NodeLabel.SERVICE),
        (RelType.ON_CALL, NodeLabel.TEAM),
        (RelType.MEMBER_OF, NodeLabel.PERSON),
    ):
        counts = Counter(e.src for e in graph.edges_of_type(rel_type))
        assert set(counts) == {n.id for n in graph.nodes_with_label(label)}
        assert set(counts.values()) == {1}, f"{rel_type} is not single-valued"


def test_b1_names_and_aliases_are_unique_so_a_question_can_name_one_entity(graph: TruthGraph) -> None:
    labels = [n.name for n in graph.nodes] + [a for n in graph.nodes for a in n.aliases]
    assert len(set(labels)) == len(labels)


def test_b1_the_on_call_person_is_a_member_of_the_team_that_pages_them(graph: TruthGraph) -> None:
    team_of = {e.src: e.dst for e in graph.edges_of_type(RelType.MEMBER_OF)}
    for edge in graph.edges_of_type(RelType.ON_CALL):
        assert team_of[edge.dst] == edge.src


def test_b1_service_dependencies_never_form_a_cycle(graph: TruthGraph) -> None:
    downstream: dict[int, list[int]] = defaultdict(list)
    for edge in graph.edges_of_type(RelType.DEPENDS_ON):
        downstream[edge.src].append(edge.dst)
    colour: dict[int, int] = {}

    def visit(node_id: int) -> None:
        colour[node_id] = 1
        for nxt in downstream[node_id]:
            assert colour.get(nxt) != 1, "DEPENDS_ON contains a cycle"
            if nxt not in colour:
                visit(nxt)
        colour[node_id] = 2

    for service in graph.nodes_with_label(NodeLabel.SERVICE):
        if service.id not in colour:
            visit(service.id)


def test_b1_every_team_has_members_and_every_customer_is_served(graph: TruthGraph) -> None:
    with_members = {e.dst for e in graph.edges_of_type(RelType.MEMBER_OF)}
    assert with_members == {n.id for n in graph.nodes_with_label(NodeLabel.TEAM)}
    served = {e.dst for e in graph.edges_of_type(RelType.SERVES)}
    assert served == {n.id for n in graph.nodes_with_label(NodeLabel.CUSTOMER)}


def test_b1_a_smaller_plan_still_satisfies_every_structural_rule() -> None:
    small = generate(SEED, SMALL)
    assert label_counts(small)[NodeLabel.PERSON.value] == SMALL.people
    assert {e.src for e in small.edges_of_type(RelType.ON_CALL)} == {
        n.id for n in small.nodes_with_label(NodeLabel.TEAM)
    }


def test_b1_a_plan_with_more_teams_than_people_is_refused() -> None:
    with pytest.raises(ValueError, match="people must be >= teams"):
        Sizes(people=3, teams=9)
