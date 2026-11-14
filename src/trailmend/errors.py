from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    NO_SEED = "no_seed"
    AMBIGUOUS_SEED = "ambiguous_seed"
    AMBIGUOUS_ANSWER = "ambiguous_answer"
    UNREACHABLE = "unreachable"
    GRAPH_UNAVAILABLE = "graph_unavailable"
    BUDGET_EXCEEDED = "budget_exceeded"
    INVALID_REQUEST = "invalid_request"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    message: str
    retryable: bool
    next_action: str
    http_status: int


ERROR_SPECS: dict[ErrorCode, ErrorSpec] = {
    ErrorCode.NO_SEED: ErrorSpec(
        "No entity in the graph matches this question.", False, "Rephrase using a known name.", 422
    ),
    ErrorCode.AMBIGUOUS_SEED: ErrorSpec(
        "More than one entity matches equally well.", False, "Name the entity more precisely.", 422
    ),
    ErrorCode.AMBIGUOUS_ANSWER: ErrorSpec(
        "Two answers are tied; nothing was guessed.", False, "Judge one of the candidates.", 409
    ),
    ErrorCode.UNREACHABLE: ErrorSpec(
        "No path reaches an answer yet. The gap was recorded.", False, "Run a Mend round.", 404
    ),
    ErrorCode.GRAPH_UNAVAILABLE: ErrorSpec(
        "The graph is unavailable. Nothing was changed.", True, "Retry shortly.", 503
    ),
    ErrorCode.BUDGET_EXCEEDED: ErrorSpec(
        "The search hit a query budget, so the result may be incomplete. Nothing was scored.",
        True,
        "Retry with a narrower question.",
        507,
    ),
    ErrorCode.INVALID_REQUEST: ErrorSpec(
        "The request is invalid. Nothing was changed.", False, "Fix the request.", 400
    ),
    ErrorCode.RATE_LIMITED: ErrorSpec("Too many requests. Nothing was changed.", True, "Wait and retry.", 429),
}


class TrailMendError(Exception):
    def __init__(self, code: ErrorCode, detail: str = "") -> None:
        super().__init__(f"{code.value}: {detail}" if detail else code.value)
        self.code = code
        self.detail = detail

    @property
    def spec(self) -> ErrorSpec:
        return ERROR_SPECS[self.code]
