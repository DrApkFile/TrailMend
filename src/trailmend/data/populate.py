from random import Random

from trailmend.data.model import Node, NodeFactory
from trailmend.data.vocab import (
    ALERT_SYMPTOMS,
    CUSTOMER_PREFIXES,
    CUSTOMER_SUFFIXES,
    FIRST_NAMES,
    LAST_NAMES,
    REPO_SUFFIXES,
    RUNBOOK_TOPICS,
    SERVICE_DOMAINS,
    SERVICE_KINDS,
    TEAM_NAMES,
)
from trailmend.graph.schema import NodeLabel


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-").replace("_", "-")


def _take[T](rng: Random, population: list[T], count: int, what: str) -> list[T]:
    if count > len(population):
        raise ValueError(f"cannot draw {count} distinct {what} from {len(population)} candidates")
    return rng.sample(population, count)


def build_teams(mint: NodeFactory, rng: Random, count: int) -> tuple[Node, ...]:
    chosen = _take(rng, list(TEAM_NAMES), count, "team names")
    return tuple(mint.node(NodeLabel.TEAM, _slug(name), name, (f"{name} squad",)) for name in chosen)


def build_people(mint: NodeFactory, rng: Random, count: int) -> tuple[Node, ...]:
    pairs = [(first, last) for first in FIRST_NAMES for last in LAST_NAMES]
    chosen = _take(rng, pairs, count, "person names")
    return tuple(mint.node(NodeLabel.PERSON, _slug(f"{first}-{last}"), f"{first} {last}") for first, last in chosen)


def build_services(mint: NodeFactory, rng: Random, count: int) -> tuple[Node, ...]:
    pairs = [(domain, kind) for domain in SERVICE_DOMAINS for kind in SERVICE_KINDS]
    chosen = _take(rng, pairs, count, "service names")
    return tuple(
        mint.node(NodeLabel.SERVICE, f"{domain}-{kind}", f"{domain}-{kind}", (f"{domain.title()}{kind.title()}",))
        for domain, kind in chosen
    )


def build_alerts(
    mint: NodeFactory, rng: Random, services: tuple[Node, ...], count: int
) -> tuple[tuple[Node, ...], dict[int, Node]]:
    pairs = [(service, symptom) for service in services for symptom in ALERT_SYMPTOMS]
    chosen = _take(rng, pairs, count, "alert names")
    alerts: list[Node] = []
    owning: dict[int, Node] = {}
    for service, symptom in chosen:
        alert = mint.node(NodeLabel.ALERT, f"{service.name}-{symptom}", f"{service.name}-{symptom}")
        alerts.append(alert)
        owning[alert.id] = service
    return tuple(alerts), owning


def build_customers(mint: NodeFactory, rng: Random, count: int) -> tuple[Node, ...]:
    pairs = [(prefix, suffix) for prefix in CUSTOMER_PREFIXES for suffix in CUSTOMER_SUFFIXES]
    chosen = _take(rng, pairs, count, "customer names")
    return tuple(mint.node(NodeLabel.CUSTOMER, _slug(f"{p}-{s}"), f"{p} {s}") for p, s in chosen)


def build_incidents(mint: NodeFactory, count: int) -> tuple[Node, ...]:
    return tuple(
        mint.node(NodeLabel.INCIDENT, f"inc-{1000 + index}", f"INC-{1000 + index}", (f"INC{1000 + index}",))
        for index in range(count)
    )


def build_runbooks(
    mint: NodeFactory, rng: Random, services: tuple[Node, ...], count: int
) -> tuple[tuple[Node, ...], dict[int, Node]]:
    pairs = [(service, topic) for service in services for topic in RUNBOOK_TOPICS]
    chosen = _take(rng, pairs, count, "runbook names")
    runbooks: list[Node] = []
    documented: dict[int, Node] = {}
    for service, topic in chosen:
        runbook = mint.node(NodeLabel.RUNBOOK, f"{service.name}-{topic}", f"runbook {service.name} {topic}")
        runbooks.append(runbook)
        documented[runbook.id] = service
    return tuple(runbooks), documented


def build_repos(
    mint: NodeFactory, rng: Random, teams: tuple[Node, ...], count: int
) -> tuple[tuple[Node, ...], dict[int, Node]]:
    pairs = [(team, suffix) for team in teams for suffix in REPO_SUFFIXES]
    chosen = _take(rng, pairs, count, "repo names")
    repos: list[Node] = []
    owning: dict[int, Node] = {}
    for team, suffix in chosen:
        slug = _slug(f"{team.name}-{suffix}")
        repo = mint.node(NodeLabel.REPO, slug, slug)
        repos.append(repo)
        owning[repo.id] = team
    return tuple(repos), owning
