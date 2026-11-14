from dataclasses import dataclass
from itertools import pairwise
from random import Random

from trailmend.data.model import Edge, Node, make_edge
from trailmend.graph.schema import RelType


@dataclass(frozen=True, slots=True)
class Membership:
    edges: tuple[Edge, ...]
    on_call_edges: tuple[Edge, ...]
    escalation_edges: tuple[Edge, ...]
    by_team: dict[int, tuple[Node, ...]]


def relate_membership(rng: Random, people: tuple[Node, ...], teams: tuple[Node, ...]) -> Membership:
    assigned: dict[int, list[Node]] = {team.id: [] for team in teams}
    member_edges: list[Edge] = []
    for index, person in enumerate(people):
        team = teams[index] if index < len(teams) else rng.choice(teams)
        assigned[team.id].append(person)
        member_edges.append(make_edge(person, RelType.MEMBER_OF, team))

    on_call: list[Edge] = []
    escalation: list[Edge] = []
    for team in teams:
        members = assigned[team.id]
        on_call.append(make_edge(team, RelType.ON_CALL, rng.choice(members)))
        for earlier, later in pairwise(members):
            escalation.append(make_edge(earlier, RelType.ESCALATES_TO, later))
    by_team = {team_id: tuple(members) for team_id, members in assigned.items()}
    return Membership(tuple(member_edges), tuple(on_call), tuple(escalation), by_team)


def relate_ownership(rng: Random, services: tuple[Node, ...], teams: tuple[Node, ...]) -> tuple[Edge, ...]:
    return tuple(make_edge(service, RelType.OWNED_BY, rng.choice(teams)) for service in services)


def relate_alerts(alerts: tuple[Node, ...], alert_service: dict[int, Node]) -> tuple[Edge, ...]:
    return tuple(make_edge(alert, RelType.ALERTS_ON, alert_service[alert.id]) for alert in alerts)


def relate_dependencies(rng: Random, services: tuple[Node, ...]) -> tuple[Edge, ...]:
    edges: list[Edge] = []
    for index, service in enumerate(services):
        downstream = services[index + 1 :]
        if not downstream:
            continue
        count = min(rng.choice((0, 1, 1, 2)), len(downstream))
        for target in rng.sample(list(downstream), count):
            edges.append(make_edge(service, RelType.DEPENDS_ON, target))
    return tuple(edges)


def relate_incidents(rng: Random, incidents: tuple[Node, ...], services: tuple[Node, ...]) -> tuple[Edge, ...]:
    edges: list[Edge] = []
    for incident in incidents:
        count = min(rng.choice((1, 1, 2, 3)), len(services))
        for service in rng.sample(list(services), count):
            edges.append(make_edge(incident, RelType.AFFECTS, service))
    return tuple(edges)


def relate_customers(rng: Random, customers: tuple[Node, ...], services: tuple[Node, ...]) -> tuple[Edge, ...]:
    edges: list[Edge] = []
    for customer in customers:
        count = min(rng.choice((1, 2, 2, 3)), len(services))
        for service in rng.sample(list(services), count):
            edges.append(make_edge(service, RelType.SERVES, customer))
    return tuple(edges)


def relate_runbooks(runbooks: tuple[Node, ...], runbook_service: dict[int, Node]) -> tuple[Edge, ...]:
    return tuple(make_edge(runbook_service[book.id], RelType.DOCUMENTED_BY, book) for book in runbooks)


def relate_repos(repos: tuple[Node, ...], repo_team: dict[int, Node]) -> tuple[Edge, ...]:
    return tuple(make_edge(repo_team[repo.id], RelType.MAINTAINS, repo) for repo in repos)
