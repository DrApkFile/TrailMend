from pydantic import BaseModel, ConfigDict, Field

from trailmend.loop.evaluate import Verdict


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Example(Strict):
    question: str
    template: str
    hops: int


class AskRequest(Strict):
    question: str = Field(min_length=3, max_length=300)


class Hop(Strict):
    src: int
    src_name: str
    rel_type: str
    dst: int
    dst_name: str
    cost: float


class AskResponse(Strict):
    question: str
    seed_entity_id: int
    seed_entity_name: str
    matched_how: str
    answer_ids: tuple[int, ...]
    answer_names: tuple[str, ...]
    cost: float
    paths: tuple[tuple[Hop, ...], ...]
    template: str | None
    changed_anything: bool = False


class JudgeRequest(Strict):
    question: str = Field(min_length=3, max_length=300)
    verdict: Verdict
    correct_answer_ids: tuple[int, ...] = ()


class ReceiptSummary(Strict):
    receipt_id: str
    run_id: str
    round: int
    sequence: int
    kind: str
    edge: Hop | None
    digest: str


class JudgeResponse(Strict):
    question: str
    verdict: Verdict
    confirmed: tuple[int, ...]
    blamed: tuple[int, ...]
    receipts: tuple[str, ...]
    changed_anything: bool


class RoundRequest(Strict):
    rounds: int = Field(default=1, ge=1, le=5)


class RoundResponse(Strict):
    run_id: str
    rounds_run: int
    reweights: int
    quarantines: int
    promoted: int
    retired: int
    ingested: int
    held_out_accuracy: float
    receipts: tuple[str, ...]
    changed_anything: bool


class RollbackResponse(Strict):
    receipt_id: str
    undone_by: str
    edge: Hop
    changed_anything: bool


class Neighbour(Strict):
    rel_type: str
    other_id: int
    other_name: str
    direction: str
    cost: float
    status: str


class NeighbourhoodResponse(Strict):
    entity_id: int
    name: str
    label: str
    neighbours: tuple[Neighbour, ...]
