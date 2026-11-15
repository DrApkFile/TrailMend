from collections.abc import Sequence
from dataclasses import dataclass

from trailmend.core.credit import Unreachable
from trailmend.core.ingest import MIN_SUPPORT, ingest_cost
from trailmend.core.model import EdgeKey, EdgeStatus, Fill, MendConfig
from trailmend.core.receipts import Receipt
from trailmend.data.documents import DocumentSet
from trailmend.data.model import Edge
from trailmend.graph.client import HydraClient
from trailmend.graph.state import read_state
from trailmend.loop.apply import apply
from trailmend.loop.journal import Journal

GAPFILL_ORIGIN = "gapfill"


@dataclass(frozen=True, slots=True)
class Filled:
    gaps: tuple[Unreachable, ...]
    fills: tuple[Fill, ...]
    receipts: tuple[Receipt, ...]


def _key(edge: Edge) -> EdgeKey:
    return EdgeKey(edge.src, edge.rel_type.value, edge.dst)


def candidate_edges(documents: DocumentSet, pool: Sequence[Edge], gaps: Sequence[Unreachable]) -> dict[EdgeKey, Fill]:
    withheld = {edge.id: edge for edge in pool}
    support = documents.pool_support
    found: dict[EdgeKey, list[int]] = {}
    cost: dict[EdgeKey, float] = {}
    for gap in sorted({g.seed_id for g in gaps}):
        for document in documents.mentioning(gap, pool_only=True):
            edge = withheld.get(document.edge_id)
            if edge is not None:
                found.setdefault(_key(edge), []).append(document.id)
                cost[_key(edge)] = ingest_cost(support.get(edge.id, MIN_SUPPORT))
    return {
        key: Fill(key, tuple(dict.fromkeys(document_ids)), cost[key]) for key, document_ids in sorted(found.items())
    }


def run_gapfill(
    client: HydraClient,
    journal: Journal,
    run_id: str,
    round_index: int,
    first_sequence: int,
    documents: DocumentSet,
    pool: Sequence[Edge],
    gaps: Sequence[Unreachable],
    config: MendConfig,
) -> Filled:
    applied: list[Fill] = []
    receipts: list[Receipt] = []
    for change in candidate_edges(documents, pool, gaps).values():
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
    return Filled(tuple(gaps), tuple(applied), tuple(receipts))
