from collections import Counter

from trailmend.data import dataset
from trailmend.data.faultmodel import V2, WrongKind
from trailmend.data.faultmodel import to_json as faults_json
from trailmend.data.support import SupportPlan
from trailmend.eval.splits import to_json as split_json
from trailmend.graph.ids import edge_id

SEED = 1


def built_v2() -> dataset.Dataset:
    return dataset.build(SEED, data_version=V2)


def test_the_wrong_edges_split_into_the_three_declared_kinds() -> None:
    faults = built_v2().ingested.faults
    counts = Counter(fault.kind for fault in faults.wrong_edges)
    total = len(faults.wrong_edges)
    assert counts[WrongKind.CONTRADICTED] == round(total * 0.4)
    assert counts[WrongKind.RECOVERABLE] == round(total * 0.3)
    assert sum(counts.values()) == total


def test_a_contradicted_fault_leaves_the_true_edge_in_the_graph_beside_the_stale_one() -> None:
    built = built_v2()
    present = {(edge.src, edge.rel_type, edge.dst) for edge in built.graph.edges}
    faults = built.ingested.faults.wrong_of_kind(WrongKind.CONTRADICTED)
    assert faults
    for fault in faults:
        assert fault.true_key in present
        assert fault.wrong_key in present


def test_a_recoverable_fault_puts_the_true_edge_in_the_pool_with_its_documents() -> None:
    built = built_v2()
    present = {(edge.src, edge.rel_type, edge.dst) for edge in built.graph.edges}
    withheld = {(edge.src, edge.rel_type, edge.dst) for edge in built.ingested.pool}
    faults = built.ingested.faults.wrong_of_kind(WrongKind.RECOVERABLE)
    assert faults
    for fault in faults:
        assert fault.true_key in withheld
        assert fault.true_key not in present
        assert built.documents.pool_support[edge_id(fault.rel_type.value, fault.src, fault.true_dst)] >= 1


def test_a_destroyed_fault_leaves_the_true_edge_nowhere_as_in_run_one() -> None:
    built = built_v2()
    present = {(edge.src, edge.rel_type, edge.dst) for edge in built.graph.edges}
    withheld = {(edge.src, edge.rel_type, edge.dst) for edge in built.ingested.pool}
    faults = built.ingested.faults.wrong_of_kind(WrongKind.DESTROYED)
    assert faults
    for fault in faults:
        assert fault.true_key not in present
        assert fault.true_key not in withheld


def test_the_stale_edge_is_better_documented_than_the_fact_it_contradicts() -> None:
    built = built_v2()
    support = built.support
    for fault in built.ingested.faults.wrong_of_kind(WrongKind.CONTRADICTED):
        stale = support[edge_id(fault.rel_type.value, fault.src, fault.wrong_dst)]
        current = support[edge_id(fault.rel_type.value, fault.src, fault.true_dst)]
        assert stale > current
        assert stale in SupportPlan().stale


def test_every_edge_is_rendered_once_per_supporting_document_with_no_repeated_text() -> None:
    built = built_v2()
    support = built.support
    rendered = Counter(document.edge_id for document in built.documents.ingested)
    assert rendered == Counter(support)
    by_edge: dict[int, set[str]] = {}
    for document in built.documents.ingested:
        by_edge.setdefault(document.edge_id, set()).add(document.text)
    assert all(len(texts) == support[edge] for edge, texts in by_edge.items())


def test_support_cannot_be_read_as_a_fault_flag_in_the_generated_graph() -> None:
    built = built_v2()
    support = built.support
    share = sum(1 for count in support.values() if count >= 3) / len(support)
    assert share >= 0.15


def test_v2_declares_the_kind_of_every_wrong_edge_and_v1_does_not() -> None:
    assert '"kind"' in faults_json(built_v2().ingested.faults)
    assert '"kind"' not in faults_json(dataset.build(SEED).ingested.faults)


def test_the_questions_and_the_split_do_not_depend_on_the_data_version() -> None:
    assert split_json(built_v2().split) == split_json(dataset.build(SEED).split)
