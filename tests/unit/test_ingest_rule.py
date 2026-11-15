import json
from pathlib import Path
from random import Random

import pytest

from trailmend.core.ingest import ingest_cost
from trailmend.data import dataset
from trailmend.data.documents import to_json as documents_json
from trailmend.data.faultmodel import to_json as faults_json
from trailmend.data.support import SupportPlan, draw, draw_stale
from trailmend.eval.manifest import sha256_of
from trailmend.eval.splits import to_json as split_json

MANIFEST = Path("evidence/run_manifest.json")


def test_a_better_documented_edge_is_cheaper_to_walk() -> None:
    costs = [ingest_cost(support) for support in (1, 2, 3)]
    assert costs == sorted(costs, reverse=True)
    assert costs[0] == pytest.approx(1.0)


def test_an_edge_no_document_asserts_cannot_be_priced() -> None:
    with pytest.raises(ValueError, match="at least one document"):
        ingest_cost(0)


def test_stale_support_is_drawn_from_the_same_distribution_as_every_edge() -> None:
    plan = SupportPlan()
    assert set(plan.stale) <= set(plan.counts)
    rng = Random(7)
    drawn = {draw_stale(rng, plan) for _ in range(200)}
    assert drawn <= set(plan.stale)


def test_support_three_cannot_be_read_as_a_fault_flag() -> None:
    plan = SupportPlan()
    assert plan.share_at_least(3) >= 0.15
    rng = Random(11)
    sample = [draw(rng, plan) for _ in range(4000)]
    assert sum(1 for count in sample if count >= 3) / len(sample) >= 0.15


def test_stale_support_must_be_a_value_the_distribution_can_produce() -> None:
    with pytest.raises(ValueError, match="same distribution"):
        SupportPlan(weights=((1, 0.5), (2, 0.5)), stale=(3,))


def test_v1_still_reproduces_the_digests_published_with_run_one() -> None:
    recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))["seeds"]
    for seed_text, want in recorded.items():
        built = dataset.build(int(seed_text))
        assert sha256_of(faults_json(built.ingested.faults)) == want["faults"]
        assert sha256_of(documents_json(built.documents)) == want["documents"]
        assert sha256_of(split_json(built.split)) == want["split"]


def test_v1_prices_every_edge_at_one_document_of_support() -> None:
    built = dataset.build(1)
    assert set(built.support.values()) == {1}
    assert len(built.documents.ingested) == len(built.graph.edges)
