from dataclasses import dataclass, field
from enum import StrEnum


class Signal(StrEnum):
    CONFIRM = "confirm"
    BLAME = "blame"


class EdgeStatus(StrEnum):
    ACTIVE = "active"
    QUARANTINED = "quarantined"


@dataclass(frozen=True, slots=True, order=True)
class EdgeKey:
    src: int
    rel_type: str
    dst: int


@dataclass(frozen=True, slots=True)
class EdgeState:
    key: EdgeKey
    cost: float
    status: EdgeStatus = EdgeStatus.ACTIVE
    confirms: int = 0
    blames: int = 0
    recent: tuple[Signal, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class MendConfig:
    eta: float
    cost_floor: float
    cost_ceiling: float
    window: int
    quarantine_min_blames: int
    quarantine_blame_share: float
    quarantine_confirm_ceiling: int
    promote_min_questions: int

    def __post_init__(self) -> None:
        if not 0 < self.eta <= 2:
            raise ValueError("eta must be in (0, 2]")
        if not 0 < self.cost_floor < 1 < self.cost_ceiling:
            raise ValueError("need 0 < cost_floor < 1 < cost_ceiling")
        if self.window < self.quarantine_min_blames or self.quarantine_min_blames < 2:
            raise ValueError("need 2 <= quarantine_min_blames <= window")
        if not 0.5 < self.quarantine_blame_share <= 1:
            raise ValueError("quarantine_blame_share must be in (0.5, 1]")
        if self.quarantine_confirm_ceiling < 0 or self.promote_min_questions < 2:
            raise ValueError("invalid quarantine_confirm_ceiling or promote_min_questions")


@dataclass(frozen=True, slots=True)
class SearchConfig:
    max_len: int
    result_limit: int

    def __post_init__(self) -> None:
        if not 1 <= self.max_len <= 4:
            raise ValueError("max_len must be between 1 and 4")
        if not 1 <= self.result_limit <= 500:
            raise ValueError("result_limit must be between 1 and 500")


@dataclass(frozen=True, slots=True)
class Credit:
    edge: EdgeKey
    signal: Signal
    question_id: str


@dataclass(frozen=True, slots=True)
class Reweight:
    edge: EdgeKey
    signals: tuple[Signal, ...]
    question_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Quarantine:
    edge: EdgeKey
    question_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Restore:
    edge: EdgeKey
    state: EdgeState


type Change = Reweight | Quarantine | Restore
