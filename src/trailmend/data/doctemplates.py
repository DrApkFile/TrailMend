from collections.abc import Mapping
from dataclasses import dataclass

from trailmend.graph.schema import RelType


@dataclass(frozen=True, slots=True)
class Template:
    kind: str
    text: str


TICKET = "ticket"
RUNBOOK = "runbook"
CHAT = "chat"

TEMPLATES: Mapping[RelType, tuple[Template, ...]] = {
    RelType.ALERTS_ON: (
        Template(TICKET, "Alert {src} fired again overnight. It is wired to the {dst} service."),
        Template(CHAT, "{src} is paging. That one watches {dst}."),
        Template(RUNBOOK, "{src}: raised by the {dst} service. Check {dst} before anything else."),
    ),
    RelType.OWNED_BY: (
        Template(TICKET, "Ownership review: the {src} service is operated by the {dst} team."),
        Template(CHAT, "who owns {src} these days? - {dst} does."),
        Template(RUNBOOK, "{src} is owned by {dst}. Route operational work there."),
    ),
    RelType.ON_CALL: (
        Template(CHAT, "{dst} is on call for {src} this week."),
        Template(TICKET, "Paging rota for the {src} team: {dst} is the current responder."),
        Template(RUNBOOK, "Page {dst} for anything the {src} team owns."),
    ),
    RelType.MEMBER_OF: (
        Template(CHAT, "welcome {src} to the {dst} team."),
        Template(TICKET, "Access request: {src} needs the {dst} team's permissions."),
        Template(RUNBOOK, "{src} is a member of {dst}."),
    ),
    RelType.DEPENDS_ON: (
        Template(TICKET, "Dependency audit: {src} calls {dst} on every request."),
        Template(CHAT, "careful, {src} will not start without {dst}."),
        Template(RUNBOOK, "{src} depends on {dst}. Drain {dst} last."),
    ),
    RelType.AFFECTS: (
        Template(TICKET, "{src} degraded the {dst} service for most of the window."),
        Template(CHAT, "{src} is hitting {dst} hard."),
        Template(RUNBOOK, "{src} impact: {dst}."),
    ),
    RelType.SERVES: (
        Template(TICKET, "Customer impact: {dst} is served by the {src} service."),
        Template(CHAT, "{dst} sits on {src}, so this one matters to them."),
        Template(RUNBOOK, "{src} serves {dst}."),
    ),
    RelType.ESCALATES_TO: (
        Template(RUNBOOK, "If {src} does not answer within ten minutes, escalate to {dst}."),
        Template(CHAT, "{src} is out today, {dst} is covering the escalation."),
        Template(TICKET, "Escalation path recorded: {src} then {dst}."),
    ),
    RelType.MAINTAINS: (
        Template(TICKET, "The {src} team maintains {dst}."),
        Template(CHAT, "{dst} changes go through {src}."),
        Template(RUNBOOK, "{dst} is maintained by {src}."),
    ),
    RelType.DOCUMENTED_BY: (
        Template(RUNBOOK, "For the {src} service see {dst}."),
        Template(TICKET, "Documentation gap closed: {src} is covered by {dst}."),
        Template(CHAT, "{dst} covers {src} if you need the steps."),
    ),
}


def templates_for(rel_type: RelType) -> tuple[Template, ...]:
    found = TEMPLATES.get(rel_type)
    if not found:
        raise KeyError(f"no document template for {rel_type}")
    return found
