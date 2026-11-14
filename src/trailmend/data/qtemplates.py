from dataclasses import dataclass

from trailmend.graph.schema import NodeLabel, RelType, shortcut_type


@dataclass(frozen=True, slots=True)
class QuestionTemplate:
    name: str
    seed_label: NodeLabel
    rel_path: tuple[RelType, ...]
    answer_label: NodeLabel
    text: str
    single_answer: bool
    cap: int

    @property
    def hops(self) -> int:
        return len(self.rel_path)

    @property
    def base_types(self) -> tuple[str, ...]:
        return tuple(sorted({rel_type.value for rel_type in self.rel_path}))

    @property
    def shortcut_type(self) -> str:
        return shortcut_type(self.name)

    @property
    def search_types(self) -> tuple[str, ...]:
        return (*self.base_types, self.shortcut_type)

    def __post_init__(self) -> None:
        if not self.rel_path:
            raise ValueError(f"{self.name} must traverse at least one relationship")
        if "{seed}" not in self.text:
            raise ValueError(f"{self.name} must name its seed entity")
        if self.cap < 1:
            raise ValueError(f"{self.name} must allow at least one question")
        shortcut_type(self.name)


TEMPLATES: tuple[QuestionTemplate, ...] = (
    QuestionTemplate(
        "page_owner",
        NodeLabel.ALERT,
        (RelType.ALERTS_ON, RelType.OWNED_BY, RelType.ON_CALL),
        NodeLabel.PERSON,
        "Who do I page for {seed}?",
        True,
        150,
    ),
    QuestionTemplate(
        "incident_pager",
        NodeLabel.INCIDENT,
        (RelType.AFFECTS, RelType.OWNED_BY, RelType.ON_CALL),
        NodeLabel.PERSON,
        "Who should be paged about {seed}?",
        False,
        60,
    ),
    QuestionTemplate(
        "alert_owning_team",
        NodeLabel.ALERT,
        (RelType.ALERTS_ON, RelType.OWNED_BY),
        NodeLabel.TEAM,
        "Which team owns the service behind {seed}?",
        True,
        120,
    ),
    QuestionTemplate(
        "customer_affected_by_incident",
        NodeLabel.INCIDENT,
        (RelType.AFFECTS, RelType.SERVES),
        NodeLabel.CUSTOMER,
        "Which customers were affected by {seed}?",
        False,
        60,
    ),
    QuestionTemplate(
        "service_customers",
        NodeLabel.SERVICE,
        (RelType.SERVES,),
        NodeLabel.CUSTOMER,
        "Which customers does {seed} serve?",
        False,
        80,
    ),
    QuestionTemplate(
        "service_owner_team",
        NodeLabel.SERVICE,
        (RelType.OWNED_BY,),
        NodeLabel.TEAM,
        "Which team owns {seed}?",
        True,
        90,
    ),
    QuestionTemplate(
        "alert_service",
        NodeLabel.ALERT,
        (RelType.ALERTS_ON,),
        NodeLabel.SERVICE,
        "Which service does {seed} fire on?",
        True,
        80,
    ),
    QuestionTemplate(
        "team_on_call",
        NodeLabel.TEAM,
        (RelType.ON_CALL,),
        NodeLabel.PERSON,
        "Who is on call for the {seed} team?",
        True,
        40,
    ),
    QuestionTemplate(
        "escalation_contact",
        NodeLabel.PERSON,
        (RelType.ESCALATES_TO,),
        NodeLabel.PERSON,
        "Who covers the escalation after {seed}?",
        True,
        90,
    ),
    QuestionTemplate(
        "person_team",
        NodeLabel.PERSON,
        (RelType.MEMBER_OF,),
        NodeLabel.TEAM,
        "Which team is {seed} on?",
        True,
        90,
    ),
)

BY_NAME = {t.name: t for t in TEMPLATES}

SHORTCUT_TYPES: tuple[str, ...] = tuple(sorted({t.shortcut_type for t in TEMPLATES}))


def template(name: str) -> QuestionTemplate:
    found = BY_NAME.get(name)
    if found is None:
        raise KeyError(f"no question template named {name!r}")
    return found
