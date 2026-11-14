from dataclasses import dataclass
from random import Random

from trailmend.data.model import Edge, Node, TruthGraph, make_edge, make_node
from trailmend.data.populate import (
    build_alerts,
    build_customers,
    build_incidents,
    build_people,
    build_repos,
    build_runbooks,
    build_services,
    build_teams,
)
from trailmend.data.relate import (
    relate_alerts,
    relate_customers,
    relate_dependencies,
    relate_incidents,
    relate_membership,
    relate_ownership,
    relate_repos,
    relate_runbooks,
)
from trailmend.data.vocab import COMPANY_NAMES
from trailmend.graph.schema import NodeLabel


@dataclass(frozen=True, slots=True)
class Sizes:
    people: int = 400
    teams: int = 40
    services: int = 120
    alerts: int = 300
    customers: int = 80
    incidents: int = 60
    runbooks: int = 90
    repos: int = 70

    def __post_init__(self) -> None:
        for field_name in ("people", "teams", "services", "alerts", "customers", "incidents", "runbooks", "repos"):
            if getattr(self, field_name) < 1:
                raise ValueError(f"{field_name} must be at least 1")
        if self.people < self.teams:
            raise ValueError("every team needs at least one person, so people must be >= teams")


def _company_name(rng: Random) -> str:
    return f"{rng.choice(COMPANY_NAMES)} Logistics"


def _require_unique(nodes: tuple[Node, ...], edges: tuple[Edge, ...]) -> None:
    node_ids = [n.id for n in nodes]
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("node ids collided")
    edge_ids = [e.id for e in edges]
    if len(set(edge_ids)) != len(edge_ids):
        raise ValueError("edge ids collided")
    labels: list[str] = [n.name for n in nodes] + [a for n in nodes for a in n.aliases]
    if len(set(labels)) != len(labels):
        raise ValueError("node names and aliases must be unique across the truth graph")
    known = {n.id for n in nodes}
    for edge in edges:
        if edge.src not in known or edge.dst not in known:
            raise ValueError(f"edge {edge.rel_type} points outside the graph")


def generate(seed: int, sizes: Sizes | None = None) -> TruthGraph:
    plan = sizes or Sizes()
    rng = Random(seed)
    company = _company_name(rng)

    teams = build_teams(rng, plan.teams)
    people = build_people(rng, plan.people)
    services = build_services(rng, plan.services)
    alerts, alert_service = build_alerts(rng, services, plan.alerts)
    customers = build_customers(rng, plan.customers)
    incidents = build_incidents(plan.incidents)
    runbooks, runbook_service = build_runbooks(rng, services, plan.runbooks)
    repos, repo_team = build_repos(rng, teams, plan.repos)

    members = relate_membership(rng, people, teams)
    edges: list[Edge] = []
    edges.extend(members.edges)
    edges.extend(members.on_call_edges)
    edges.extend(members.escalation_edges)
    edges.extend(relate_ownership(rng, services, teams))
    edges.extend(relate_alerts(alerts, alert_service))
    edges.extend(relate_dependencies(rng, services))
    edges.extend(relate_incidents(rng, incidents, services))
    edges.extend(relate_customers(rng, customers, services))
    edges.extend(relate_runbooks(runbooks, runbook_service))
    edges.extend(relate_repos(repos, repo_team))

    nodes = (*teams, *people, *services, *alerts, *customers, *incidents, *runbooks, *repos)
    graph = TruthGraph(seed, company, nodes, tuple(edges))
    _require_unique(graph.nodes, graph.edges)
    return graph


def label_counts(graph: TruthGraph) -> dict[str, int]:
    return {label.value: len(graph.nodes_with_label(label)) for label in NodeLabel}


__all__ = ["Sizes", "generate", "label_counts", "make_edge", "make_node"]
