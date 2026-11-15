from typing import cast

import pytest

from trailmend.core.credit import Unreachable
from trailmend.core.model import EdgeKey, EdgeState, EdgeStatus, Fill, MendConfig, SearchConfig
from trailmend.core.receipts import inverse, make_receipt
from trailmend.core.update import apply_change
from trailmend.data.documents import Document, DocumentSet
from trailmend.data.model import Edge
from trailmend.graph.client import HydraClient
from trailmend.graph.schema import RelType
from trailmend.loop.credit_round import outcome_for
from trailmend.loop.evaluate import Judged, Verdict
from trailmend.loop.gapfill import candidate_edges, gap_of

SEED_ENTITY = 11
GOLD_ENTITY = 99
OTHER_ENTITY = 77
WITHHELD = Edge(5_001, SEED_ENTITY, RelType.ALERTS_ON, GOLD_ENTITY)
UNRELATED = Edge(5_002, OTHER_ENTITY, RelType.ALERTS_ON, GOLD_ENTITY)


def _gap() -> Unreachable:
    return Unreachable("q1", SEED_ENTITY, "Person", "page_owner")


def _documents(*docs: Document) -> DocumentSet:
    return DocumentSet(1, (), docs)


def _doc(doc_id: int, edge: Edge, mentions: tuple[int, ...]) -> Document:
    return Document(doc_id, "ticket", "text", mentions, edge.id)


def test_a_pool_document_mentioning_the_seed_entity_is_ingested() -> None:
    documents = _documents(_doc(1, WITHHELD, (SEED_ENTITY, GOLD_ENTITY)))
    planned = candidate_edges(documents, (WITHHELD,), [gap_of(_gap())])
    assert list(planned) == [EdgeKey(SEED_ENTITY, "ALERTS_ON", GOLD_ENTITY)]


def test_inv7_a_pool_document_that_only_mentions_the_gold_entity_stays_in_the_pool() -> None:
    documents = _documents(_doc(1, UNRELATED, (OTHER_ENTITY, GOLD_ENTITY)))
    assert candidate_edges(documents, (UNRELATED,), [gap_of(_gap())]) == {}


def test_an_already_ingested_document_is_never_a_candidate() -> None:
    doc = _doc(1, WITHHELD, (SEED_ENTITY, GOLD_ENTITY))
    documents = DocumentSet(1, (doc,), ())
    assert candidate_edges(documents, (WITHHELD,), [gap_of(_gap())]) == {}


def test_a_document_whose_edge_is_not_in_the_pool_is_ignored() -> None:
    documents = _documents(_doc(1, WITHHELD, (SEED_ENTITY, GOLD_ENTITY)))
    assert candidate_edges(documents, (), [gap_of(_gap())]) == {}


def test_two_documents_for_one_edge_are_recorded_on_a_single_fill() -> None:
    documents = _documents(_doc(1, WITHHELD, (SEED_ENTITY, GOLD_ENTITY)), _doc(2, WITHHELD, (SEED_ENTITY, GOLD_ENTITY)))
    planned = candidate_edges(documents, (WITHHELD,), [gap_of(_gap())])
    assert [f.document_ids for f in planned.values()] == [(1, 2)]


def test_a_filled_edge_starts_at_the_cost_every_ingested_edge_starts_at(cfg: MendConfig) -> None:
    key = EdgeKey(SEED_ENTITY, "ALERTS_ON", GOLD_ENTITY)
    absent = EdgeState(key, 0.0, EdgeStatus.ABSENT)
    live = apply_change(absent, Fill(key, (1,), 1.0), cfg)
    assert live.status is EdgeStatus.ACTIVE
    assert live.cost == 1.0


def test_inv3_rolling_back_a_gapfill_leaves_the_edge_absent(cfg: MendConfig) -> None:
    key = EdgeKey(SEED_ENTITY, "ALERTS_ON", GOLD_ENTITY)
    absent = EdgeState(key, 0.0, EdgeStatus.ABSENT)
    change = Fill(key, (1,), 1.0)
    live = apply_change(absent, change, cfg)
    receipt = make_receipt("run", 1, 0, change, absent, live)
    assert receipt.kind == "gapfill"
    assert apply_change(live, inverse(receipt), cfg) == absent


class _GoldTripwire:
    def __init__(self) -> None:
        self.question_id = "q1"
        self.template = "page_owner"
        self.seed_entity_id = SEED_ENTITY
        self.verdict = Verdict.UNREACHABLE
        self.refusal = None
        self.answer_ids: tuple[int, ...] = ()
        self.paths: tuple[tuple[EdgeKey, ...], ...] = ()

    @property
    def gold(self) -> tuple[int, ...]:
        raise AssertionError("the Mend read the gold ids of an unreachable question")


def test_inv7_an_unreachable_question_is_recorded_without_reading_its_gold_ids() -> None:
    gap = outcome_for(
        cast("HydraClient", None), cast("Judged", _GoldTripwire()), SearchConfig(max_len=3, result_limit=200)
    )
    assert isinstance(gap, Unreachable)
    assert gap.seed_id == SEED_ENTITY
    with pytest.raises(AssertionError, match="read the gold ids"):
        _ = _GoldTripwire().gold
