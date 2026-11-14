from trailmend.data.documents import Document
from trailmend.data.model import Node
from trailmend.data.qtemplates import template
from trailmend.data.questions import Question
from trailmend.eval.plain_store import bm25, build_store, judge_plain
from trailmend.graph.schema import NodeLabel
from trailmend.loop.evaluate import Verdict

ALERT = Node(1, NodeLabel.ALERT, "DiskFull", (), "alert:s1-diskfull")
PERSON_A = Node(2, NodeLabel.PERSON, "Ada Byron", (), "person:s1-ada")
PERSON_B = Node(3, NodeLabel.PERSON, "Bo Chen", (), "person:s1-bo")
TEAM = Node(4, NodeLabel.TEAM, "Aurora", (), "team:s1-aurora")
NODES = (ALERT, PERSON_A, PERSON_B, TEAM)


def _doc(doc_id: int, text: str, mentions: tuple[int, ...]) -> Document:
    return Document(doc_id, "ticket", text, mentions, doc_id + 1_000)


def _question(template_name: str, text: str, gold: tuple[int, ...]) -> Question:
    spec = template(template_name)
    return Question(f"q-{template_name}", template_name, text, ALERT.id, ALERT.name, spec.answer_label, spec.hops, gold)


def test_bm25_ranks_the_document_that_carries_the_query_terms_first() -> None:
    store = build_store(
        (
            _doc(1, "DiskFull pages Ada Byron tonight", (ALERT.id, PERSON_A.id)),
            _doc(2, "Aurora runs a weekly review", (TEAM.id,)),
        ),
        NODES,
    )
    ranked = bm25(store, "Who do I page for DiskFull?")
    assert ranked[0][0] == 1


def test_the_most_mentioned_entity_of_the_expected_label_is_the_answer() -> None:
    store = build_store(
        (
            _doc(1, "DiskFull pages Ada Byron", (ALERT.id, PERSON_A.id)),
            _doc(2, "DiskFull escalates to Ada Byron again", (ALERT.id, PERSON_A.id)),
            _doc(3, "DiskFull once woke Bo Chen", (ALERT.id, PERSON_B.id)),
        ),
        NODES,
    )
    judged = judge_plain(store, _question("page_owner", "Who do I page for DiskFull?", (PERSON_A.id,)))
    assert judged.answer_ids == (PERSON_A.id,)
    assert judged.verdict is Verdict.CORRECT


def test_an_entity_of_another_label_is_never_answered() -> None:
    store = build_store((_doc(1, "DiskFull belongs to Aurora", (ALERT.id, TEAM.id)),), NODES)
    judged = judge_plain(store, _question("page_owner", "Who do I page for DiskFull?", (PERSON_A.id,)))
    assert judged.verdict is Verdict.UNREACHABLE
    assert judged.answer_ids == ()


def test_a_single_answer_template_refuses_a_tie() -> None:
    store = build_store(
        (
            _doc(1, "DiskFull pages Ada Byron", (ALERT.id, PERSON_A.id)),
            _doc(2, "DiskFull pages Bo Chen", (ALERT.id, PERSON_B.id)),
        ),
        NODES,
    )
    judged = judge_plain(store, _question("page_owner", "Who do I page for DiskFull?", (PERSON_A.id,)))
    assert judged.verdict is Verdict.REFUSED


def test_a_multi_answer_template_returns_the_whole_tied_set() -> None:
    store = build_store(
        (
            _doc(1, "Outage affects Ada Byron", (ALERT.id, PERSON_A.id)),
            _doc(2, "Outage affects Bo Chen", (ALERT.id, PERSON_B.id)),
        ),
        NODES,
    )
    judged = judge_plain(
        store, _question("incident_pager", "Who should be paged about Outage?", (PERSON_A.id, PERSON_B.id))
    )
    assert judged.answer_ids == (PERSON_A.id, PERSON_B.id)
    assert judged.verdict is Verdict.CORRECT


def test_the_same_question_always_gets_the_same_answer() -> None:
    documents = tuple(
        _doc(n, "DiskFull pages Ada Byron and Bo Chen", (ALERT.id, PERSON_A.id, PERSON_B.id)) for n in range(1, 6)
    )
    store = build_store(documents, NODES)
    question = _question("page_owner", "Who do I page for DiskFull?", (PERSON_A.id,))
    assert judge_plain(store, question) == judge_plain(store, question)


def test_the_store_only_holds_the_documents_it_was_handed() -> None:
    store = build_store((_doc(1, "DiskFull pages Ada Byron", (ALERT.id, PERSON_A.id)),), NODES)
    assert store.size == 1
