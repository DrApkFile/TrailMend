from collections.abc import Container, Mapping, Sequence
from dataclasses import dataclass

from trailmend.core.credit import Unreachable
from trailmend.core.ingest import MIN_SUPPORT, ingest_cost
from trailmend.core.model import EdgeKey, EdgeStatus, Fill, GapfillRule, MendConfig
from trailmend.core.receipts import Receipt
from trailmend.data.documents import DocumentSet
from trailmend.data.model import Edge
from trailmend.graph.client import HydraClient
from trailmend.graph.state import read_state
from trailmend.loop.apply import apply
from trailmend.loop.journal import Journal

GAPFILL_ORIGIN = "gapfill"
UNREACHABLE = "unreachable"
WRONG = "wrong"


@dataclass(frozen=True, slots=True)
class Gap:
    question_id: str
    seed_id: int
    reason: str


NARROW = GapfillRule(1, on_wrong=False)


def gap_of(unreachable: Unreachable) -> Gap:
    return Gap(unreachable.question_id, unreachable.seed_id, UNREACHABLE)


@dataclass(frozen=True, slots=True)
class Filled:
    gaps: tuple[Gap, ...]
    fills: tuple[Fill, ...]
    receipts: tuple[Receipt, ...]
    reached: tuple[EdgeKey, ...] = ()


def _key(edge: Edge) -> EdgeKey:
    return EdgeKey(edge.src, edge.rel_type.value, edge.dst)


def _wave(
    documents: DocumentSet, withheld: Mapping[int, Edge], frontier: Sequence[int], taken: Container[EdgeKey]
) -> dict[EdgeKey, list[int]]:
    found: dict[EdgeKey, list[int]] = {}
    for entity in sorted(set(frontier)):
        for document in documents.mentioning(entity, pool_only=True):
            edge = withheld.get(document.edge_id)
            if edge is None or _key(edge) in taken:
                continue
            found.setdefault(_key(edge), []).append(document.id)
    return found


def candidate_edges(
    documents: DocumentSet, pool: Sequence[Edge], gaps: Sequence[Gap], rule: GapfillRule = NARROW
) -> dict[EdgeKey, Fill]:
    withheld = {edge.id: edge for edge in pool}
    support = documents.pool_support
    by_key = {_key(edge): edge for edge in pool}
    chosen: dict[EdgeKey, list[int]] = {}
    frontier: list[int] = [gap.seed_id for gap in gaps]
    for _ in range(rule.waves):
        if not frontier:
            break
        found = _wave(documents, withheld, frontier, chosen)
        chosen.update(found)
        frontier = [entity for key in found for entity in (key.src, key.dst)]
    return {
        key: Fill(key, tuple(dict.fromkeys(ids)), ingest_cost(support.get(by_key[key].id, MIN_SUPPORT)))
        for key, ids in sorted(chosen.items())
    }


def run_gapfill(
    client: HydraClient,
    journal: Journal,
    run_id: str,
    round_index: int,
    first_sequence: int,
    documents: DocumentSet,
    pool: Sequence[Edge],
    gaps: Sequence[Gap],
    config: MendConfig,
    rule: GapfillRule = NARROW,
) -> Filled:
    applied: list[Fill] = []
    receipts: list[Receipt] = []
    candidates = candidate_edges(documents, pool, gaps, rule)
    for change in candidates.values():
        if read_state(client, change.edge) is not None:
            continue
        done = apply(
            client, journal, run_id, round_index, first_sequence + len(applied), change, config, GAPFILL_ORIGIN
        )
        landed = read_state(client, change.edge)
        if landed is None or landed.status is not EdgeStatus.ACTIVE:
            raise RuntimeError(f"receipt {done.receipt.receipt_id} claims {change.edge} was ingested, but it is absent")
        applied.append(change)
        receipts.append(done.receipt)
    return Filled(tuple(gaps), tuple(applied), tuple(receipts), tuple(candidates))
