from collections.abc import Mapping, Sequence
from enum import StrEnum

from trailmend.core.model import QUARANTINE_PREFIX, SHORTCUT_PREFIX, EdgeKey
from trailmend.graph.queries import require_label, require_rel_type


class NodeLabel(StrEnum):
    PERSON = "Person"
    TEAM = "Team"
    SERVICE = "Service"
    ALERT = "Alert"
    CUSTOMER = "Customer"
    INCIDENT = "Incident"
    RUNBOOK = "Runbook"
    REPO = "Repo"


class RelType(StrEnum):
    ALERTS_ON = "ALERTS_ON"
    OWNED_BY = "OWNED_BY"
    ON_CALL = "ON_CALL"
    MEMBER_OF = "MEMBER_OF"
    DEPENDS_ON = "DEPENDS_ON"
    AFFECTS = "AFFECTS"
    SERVES = "SERVES"
    ESCALATES_TO = "ESCALATES_TO"
    MAINTAINS = "MAINTAINS"
    DOCUMENTED_BY = "DOCUMENTED_BY"


ENDPOINTS: Mapping[RelType, tuple[NodeLabel, NodeLabel]] = {
    RelType.ALERTS_ON: (NodeLabel.ALERT, NodeLabel.SERVICE),
    RelType.OWNED_BY: (NodeLabel.SERVICE, NodeLabel.TEAM),
    RelType.ON_CALL: (NodeLabel.TEAM, NodeLabel.PERSON),
    RelType.MEMBER_OF: (NodeLabel.PERSON, NodeLabel.TEAM),
    RelType.DEPENDS_ON: (NodeLabel.SERVICE, NodeLabel.SERVICE),
    RelType.AFFECTS: (NodeLabel.INCIDENT, NodeLabel.SERVICE),
    RelType.SERVES: (NodeLabel.SERVICE, NodeLabel.CUSTOMER),
    RelType.ESCALATES_TO: (NodeLabel.PERSON, NodeLabel.PERSON),
    RelType.MAINTAINS: (NodeLabel.TEAM, NodeLabel.REPO),
    RelType.DOCUMENTED_BY: (NodeLabel.SERVICE, NodeLabel.RUNBOOK),
}

NATURAL_KEY_KIND: Mapping[NodeLabel, str] = {
    NodeLabel.PERSON: "person",
    NodeLabel.TEAM: "team",
    NodeLabel.SERVICE: "service",
    NodeLabel.ALERT: "alert",
    NodeLabel.CUSTOMER: "customer",
    NodeLabel.INCIDENT: "incident",
    NodeLabel.RUNBOOK: "runbook",
    NodeLabel.REPO: "repo",
}


def shortcut_type(template_name: str) -> str:
    return require_rel_type(SHORTCUT_PREFIX + template_name.upper())


def is_shortcut(rel_type: str) -> bool:
    return rel_type.removeprefix(QUARANTINE_PREFIX).startswith(SHORTCUT_PREFIX)


def endpoints_of(rel_type: str) -> tuple[NodeLabel, NodeLabel]:
    bare = rel_type.removeprefix(QUARANTINE_PREFIX)
    if is_shortcut(bare):
        raise ValueError(f"{bare} is a shortcut, so its endpoints come from its via_path")
    return ENDPOINTS[RelType(bare)]


def shortcut_endpoints(via_path: Sequence[EdgeKey]) -> tuple[NodeLabel, NodeLabel]:
    if len(via_path) < 2:
        raise ValueError(f"a shortcut compresses at least two hops, got {len(via_path)}")
    return endpoints_of(via_path[0].rel_type)[0], endpoints_of(via_path[-1].rel_type)[1]


def labels_of(rel_type: str, via_path: Sequence[EdgeKey]) -> tuple[NodeLabel, NodeLabel]:
    return shortcut_endpoints(via_path) if is_shortcut(rel_type) else endpoints_of(rel_type)


def source_label(rel_type: RelType) -> NodeLabel:
    return ENDPOINTS[rel_type][0]


def target_label(rel_type: RelType) -> NodeLabel:
    return ENDPOINTS[rel_type][1]


def validate_schema() -> None:
    for label in NodeLabel:
        require_label(label.value)
        if label not in NATURAL_KEY_KIND:
            raise ValueError(f"{label} has no natural-key kind")
    for rel_type in RelType:
        require_rel_type(rel_type.value)
        if rel_type not in ENDPOINTS:
            raise ValueError(f"{rel_type} has no declared endpoints")
    for rel_type in RelType:
        if is_shortcut(rel_type.value):
            raise ValueError(f"{rel_type} must not use the shortcut prefix")


validate_schema()
