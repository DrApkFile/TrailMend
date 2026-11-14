import hashlib
import os
import subprocess
import sys

import pytest

from trailmend.data.doctemplates import TEMPLATES
from trailmend.data.documents import DocumentSet, render, to_json
from trailmend.data.faults import inject
from trailmend.data.northwind import generate

SEED = 7


@pytest.fixture(scope="module")
def rendered() -> DocumentSet:
    truth = generate(SEED)
    return render(inject(truth), truth)


def _build() -> DocumentSet:
    truth = generate(SEED)
    return render(inject(truth), truth)


def test_b3_every_ingested_edge_and_every_withheld_edge_becomes_exactly_one_document(
    rendered: DocumentSet,
) -> None:
    ingested = inject(generate(SEED))
    assert [d.edge_id for d in rendered.ingested] == [e.id for e in ingested.graph.edges]
    assert [d.edge_id for d in rendered.pool] == [e.id for e in ingested.pool]


def test_b3_a_document_mentions_exactly_the_two_entities_its_edge_joins(rendered: DocumentSet) -> None:
    ingested = inject(generate(SEED))
    by_edge = {e.id: e for e in ingested.graph.edges + ingested.pool}
    for document in rendered.all:
        edge = by_edge[document.edge_id]
        assert document.mentions == (edge.src, edge.dst)


def test_b3_both_entity_names_appear_in_the_text_so_a_reader_can_find_them(rendered: DocumentSet) -> None:
    truth = generate(SEED)
    ingested = inject(truth)
    names = {n.id: n.name for n in truth.nodes}
    names.update({n.id: n.name for n in ingested.graph.nodes})
    for document in rendered.all:
        for mention in document.mentions:
            assert names[mention] in document.text


def test_b3_document_ids_are_unique_and_the_pool_never_overlaps_what_was_ingested(rendered: DocumentSet) -> None:
    ids = [d.id for d in rendered.all]
    assert len(set(ids)) == len(ids)
    assert not {d.id for d in rendered.ingested} & {d.id for d in rendered.pool}
    assert not {d.edge_id for d in rendered.ingested} & {d.edge_id for d in rendered.pool}


def test_b3_every_document_kind_comes_from_a_declared_template(rendered: DocumentSet) -> None:
    allowed = {t.kind for templates in TEMPLATES.values() for t in templates}
    assert {d.kind for d in rendered.all} <= allowed
    assert len({d.kind for d in rendered.all}) > 1


def test_b3_the_same_seed_renders_byte_identical_documents(rendered: DocumentSet) -> None:
    assert to_json(_build()) == to_json(rendered)


def test_b3_the_document_digest_survives_a_fresh_interpreter_with_a_different_hash_seed(
    rendered: DocumentSet,
) -> None:
    script = (
        "import hashlib;"
        "from trailmend.data.northwind import generate;"
        "from trailmend.data.faults import inject;"
        "from trailmend.data.documents import render, to_json;"
        f"t = generate({SEED});"
        "print(hashlib.sha256(to_json(render(inject(t), t)).encode()).hexdigest())"
    )
    env = {**os.environ, "PYTHONHASHSEED": "98765"}
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True, env=env)
    assert out.stdout.strip() == hashlib.sha256(to_json(rendered).encode()).hexdigest()


def test_b3_pool_only_lookup_returns_withheld_documents_for_that_entity(rendered: DocumentSet) -> None:
    pool_ids = {d.id for d in rendered.pool}
    entity = rendered.pool[0].mentions[0]
    found = rendered.mentioning(entity, pool_only=True)
    assert found
    assert {d.id for d in found} <= pool_ids
    assert all(entity in d.mentions for d in found)
    assert {d.id for d in rendered.mentioning(entity)} >= {d.id for d in found}
