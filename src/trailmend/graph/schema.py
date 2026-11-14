from collections.abc import Mapping
from enum import StrEnum

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


validate_schema()
