import json
from typing import cast

from fastapi import APIRouter, Header, Request

from trailmend.api.auth import require_admin
from trailmend.api.models import (
    Hop,
    Neighbour,
    NeighbourhoodResponse,
    ReceiptSummary,
    RollbackResponse,
    RoundRequest,
    RoundResponse,
)
from trailmend.api.paths import hop_of
from trailmend.api.state import Live
from trailmend.core.model import EdgeKey, EdgeState
from trailmend.errors import ErrorCode, TrailMendError
from trailmend.graph.state import read_states, state_from_row
from trailmend.loop.apply import rollback_to
from trailmend.loop.policy import MendPolicy
from trailmend.loop.round import run_round
from trailmend.loop.shortcuts import live_shortcuts
from trailmend.random_arm import arm_rng

router = APIRouter()


def _live(request: Request) -> Live:
    live: Live = request.app.state.live
    return live


def _lines(live: Live) -> tuple[dict[str, object], ...]:
    return tuple(json.loads(line) for line in live.journal.lines())


def _summary(live: Live, row: dict[str, object]) -> ReceiptSummary:
    change = row.get("change")
    edge: Hop | None = None
    if isinstance(change, dict):
        raw = cast("dict[str, object]", change).get("edge")
        if isinstance(raw, dict):
            parts = cast("dict[str, object]", raw)
            after = row.get("after")
            cost = cast("dict[str, object]", after).get("cost", 0.0) if isinstance(after, dict) else 0.0
            edge = hop_of(
                live,
                EdgeKey(int(str(parts["src"])), str(parts["rel_type"]), int(str(parts["dst"]))),
                float(str(cost)),
            )
    return ReceiptSummary(
        receipt_id=str(row["receipt_id"]),
        run_id=str(row["run_id"]),
        round=int(str(row["round"])),
        sequence=int(str(row["sequence"])),
        kind=str(row["kind"]),
        edge=edge,
        digest=str(row["digest"]),
    )


@router.get("/v1/receipts", response_model=tuple[ReceiptSummary, ...])
def receipts(request: Request, limit: int = 50) -> tuple[ReceiptSummary, ...]:
    live = _live(request)
    if not 1 <= limit <= 500:
        raise TrailMendError(ErrorCode.INVALID_REQUEST, "limit must be between 1 and 500")
    rows = _lines(live)
    return tuple(_summary(live, row) for row in rows[-limit:][::-1])


@router.get("/v1/receipts/{receipt_id}", response_model=ReceiptSummary)
def receipt(receipt_id: str, request: Request) -> ReceiptSummary:
    live = _live(request)
    for row in _lines(live):
        if row["receipt_id"] == receipt_id:
            return _summary(live, row)
    raise TrailMendError(ErrorCode.INVALID_REQUEST, f"no receipt {receipt_id}")


def _before_state(live: Live, receipt_id: str) -> tuple[dict[str, object], EdgeState]:
    for row in _lines(live):
        if row["receipt_id"] != receipt_id:
            continue
        before = row["before"]
        if not isinstance(before, dict):
            raise TrailMendError(ErrorCode.INVALID_REQUEST, f"receipt {receipt_id} has no before state")
        return row, state_from_row(cast("dict[str, object]", before))
    raise TrailMendError(ErrorCode.INVALID_REQUEST, f"no receipt {receipt_id}")


@router.post("/v1/rollback/{receipt_id}", response_model=RollbackResponse)
def rollback_receipt(
    receipt_id: str, request: Request, x_admin_token: str | None = Header(default=None)
) -> RollbackResponse:
    live = _live(request)
    require_admin(live, x_admin_token)
    row, before = _before_state(live, receipt_id)
    done = rollback_to(
        live.client,
        live.journal,
        str(row["run_id"]),
        int(str(row["round"])),
        len(live.journal.lines()),
        before,
        live.mend,
    )
    return RollbackResponse(
        receipt_id=receipt_id,
        undone_by=done.receipt.receipt_id,
        edge=hop_of(live, done.after.key, done.after.cost),
        changed_anything=True,
    )


@router.post("/v1/mend/round", response_model=RoundResponse)
def mend_round(body: RoundRequest, request: Request, x_admin_token: str | None = Header(default=None)) -> RoundResponse:
    live = _live(request)
    require_admin(live, x_admin_token)
    candidates = tuple(EdgeKey(e.src, e.rel_type.value, e.dst) for e in live.built.graph.edges)
    reweights = quarantines = promoted = retired = ingested = 0
    receipts: list[str] = []
    accuracy = 0.0
    for _ in range(body.rounds):
        live.rounds_run += 1
        outcome = run_round(
            live.client,
            live.journal,
            live.ledger,
            live.tape,
            live.settings.live_run_id,
            live.rounds_run,
            MendPolicy.FULL,
            live.index,
            live.built.split.train,
            live.built.split.held_out,
            candidates,
            arm_rng(live.settings.demo_seed, live.rounds_run),
            live.mend,
            live.search,
            live.built.documents,
            live.built.ingested.pool,
        )
        reweights += outcome.applied.reweights
        quarantines += outcome.applied.quarantines
        promoted += len(outcome.promoted)
        retired += len(outcome.retired)
        ingested += len(outcome.ingested)
        receipts.extend(outcome.receipt_ids)
        accuracy = outcome.held_out.accuracy
    return RoundResponse(
        run_id=live.settings.live_run_id,
        rounds_run=body.rounds,
        reweights=reweights,
        quarantines=quarantines,
        promoted=promoted,
        retired=retired,
        ingested=ingested,
        held_out_accuracy=accuracy,
        receipts=tuple(receipts),
        changed_anything=bool(receipts),
    )


@router.get("/v1/graph/neighbourhood/{entity_id}", response_model=NeighbourhoodResponse)
def neighbourhood(entity_id: int, request: Request) -> NeighbourhoodResponse:
    live = _live(request)
    node = live.built.graph.by_id.get(entity_id)
    if node is None:
        raise TrailMendError(ErrorCode.INVALID_REQUEST, f"no entity {entity_id}")
    around = [
        EdgeKey(e.src, e.rel_type.value, e.dst)
        for e in (*live.built.graph.edges, *live.built.ingested.pool)
        if entity_id in (e.src, e.dst)
    ]
    around.extend(key for key in live_shortcuts(live.client) if entity_id in (key.src, key.dst))
    states = read_states(live.client, sorted(dict.fromkeys(around)))
    return NeighbourhoodResponse(
        entity_id=entity_id,
        name=node.name,
        label=node.label.value,
        neighbours=tuple(
            Neighbour(
                rel_type=key.rel_type,
                other_id=key.dst if key.src == entity_id else key.src,
                other_name=live.name_of(key.dst if key.src == entity_id else key.src),
                direction="out" if key.src == entity_id else "in",
                cost=state.cost,
                status=state.status.value,
            )
            for key, state in sorted(states.items())
        ),
    )
