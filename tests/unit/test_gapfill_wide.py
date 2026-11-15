from trailmend.core.credit import Correct, Unreachable, Wrong
from trailmend.core.model import EdgeKey, GapfillRule
from trailmend.data.documents import Document, DocumentSet
from trailmend.data.model import Edge
from trailmend.graph.schema import RelType
from trailmend.loop.evaluate import Judged, Verdict
from trailmend.loop.gapfill import NARROW, UNREACHABLE, WRONG, Gap, candidate_edges, gap_of
from trailmend.loop.round import gaps_of

WIDE = GapfillRule(2, on_wrong=True)
SEED = 11
MIDDLE = 22
FAR = 33
STRANGER = 44
FIRST = Edge(6_001, SEED, RelType.OWNED_BY, MIDDLE)
SECOND = Edge(6_002, MIDDLE, RelType.ON_CALL, FAR)
UNCONNECTED = Edge(6_003, STRANGER, RelType.ON_CALL, FAR)


def _doc(doc_id: int, edge: Edge, mentions: tuple[int, ...]) -> Document:
    return Document(doc_id, "ticket", f"text {doc_id}", mentions, edge.id)


def _pool(*docs: Document) -> DocumentSet:
    return DocumentSet(1, (), docs)


def _judged(question_id: str, verdict: Verdict) -> Judged:
    return Judged(question_id, "page_owner", SEED, verdict, None, (), (), ())


def test_the_narrow_rule_only_fills_for_questions_nothing_could_reach() -> None:
    verdicts = (
        (_judged("q1", Verdict.WRONG), Wrong("q1", (EdgeKey(SEED, "OWNED_BY", MIDDLE),), None)),
        (_judged("q2", Verdict.UNREACHABLE), Unreachable("q2", SEED, "Person", "page_owner")),
    )
    assert [gap.question_id for gap in gaps_of(verdicts, NARROW)] == ["q2"]


def test_the_wide_rule_also_fills_for_a_question_that_was_answered_wrongly() -> None:
    verdicts = (
        (_judged("q1", Verdict.WRONG), Wrong("q1", (EdgeKey(SEED, "OWNED_BY", MIDDLE),), None)),
        (_judged("q2", Verdict.UNREACHABLE), Unreachable("q2", SEED, "Person", "page_owner")),
    )
    gaps = gaps_of(verdicts, WIDE)
    assert [(gap.question_id, gap.reason) for gap in gaps] == [("q1", WRONG), ("q2", UNREACHABLE)]


def test_a_correct_answer_never_asks_for_a_document() -> None:
    verdicts = ((_judged("q1", Verdict.CORRECT), Correct("q1", ())),)
    assert gaps_of(verdicts, WIDE) == ()


def test_one_wave_stops_at_the_documents_that_mention_the_seed_entity() -> None:
    documents = _pool(_doc(1, FIRST, (SEED, MIDDLE)), _doc(2, SECOND, (MIDDLE, FAR)))
    planned = candidate_edges(documents, (FIRST, SECOND), [gap_of(Unreachable("q", SEED, "Person", "page_owner"))])
    assert list(planned) == [EdgeKey(SEED, "OWNED_BY", MIDDLE)]


def test_a_second_wave_follows_the_entity_the_first_wave_reached() -> None:
    documents = _pool(_doc(1, FIRST, (SEED, MIDDLE)), _doc(2, SECOND, (MIDDLE, FAR)))
    planned = candidate_edges(
        documents, (FIRST, SECOND), [gap_of(Unreachable("q", SEED, "Person", "page_owner"))], WIDE
    )
    assert list(planned) == [EdgeKey(SEED, "OWNED_BY", MIDDLE), EdgeKey(MIDDLE, "ON_CALL", FAR)]


def test_inv7_the_wide_rule_still_never_reads_a_document_it_has_not_reached() -> None:
    documents = _pool(_doc(1, FIRST, (SEED, MIDDLE)), _doc(2, UNCONNECTED, (STRANGER, FAR)))
    planned = candidate_edges(
        documents, (FIRST, UNCONNECTED), [gap_of(Unreachable("q", SEED, "Person", "page_owner"))], WIDE
    )
    assert list(planned) == [EdgeKey(SEED, "OWNED_BY", MIDDLE)]


def test_a_wrong_answer_fills_from_the_entity_the_question_named() -> None:
    documents = _pool(_doc(1, FIRST, (SEED, MIDDLE)))
    planned = candidate_edges(documents, (FIRST,), [Gap("q1", SEED, WRONG)], WIDE)
    assert list(planned) == [EdgeKey(SEED, "OWNED_BY", MIDDLE)]
