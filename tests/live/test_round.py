from dataclasses import replace
from pathlib import Path
from random import Random

import pytest

from trailmend.core.config import load_mend_config, load_search_config
from trailmend.core.credit import Unreachable
from trailmend.core.model import EdgeKey, EdgeStatus, MendConfig, Quarantine, SearchConfig
from trailmend.data import dataset
from trailmend.data.northwind import Sizes
from trailmend.data.qtemplates import SHORTCUT_TYPES
from trailmend.data.questions import Question
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.graph.loader import INITIAL_COST, load
from trailmend.graph.queries import quarantine_type
from trailmend.graph.state import list_edge_keys, read_state
from trailmend.loop.apply import apply
from trailmend.loop.credit_round import outcome_for
from trailmend.loop.evaluate import Verdict, judge, judge_all
from trailmend.loop.gapfill import run_gapfill
from trailmend.loop.journal import Journal
from trailmend.loop.ledger import Ledger
from trailmend.loop.policy import CONTROL_OF, MendPolicy, profile, shape
from trailmend.loop.round import plan, run_round, verdicts_for
from trailmend.loop.shortcuts import live_shortcuts, run_shortcuts
from trailmend.loop.tape import Tape
from trailmend.search.answer import score_paths
from trailmend.search.seed import build_index

pytestmark = pytest.mark.hydra

SEED = 61_111
SMALL = Sizes(people=24, teams=4, services=8, alerts=12, customers=5, incidents=4, runbooks=5, repos=3)


@pytest.fixture(scope="module")
def mend_config() -> MendConfig:
    return load_mend_config(Path("config/mend.toml"))


@pytest.fixture(scope="module")
def search_config() -> SearchConfig:
    return load_search_config(Path("config/mend.toml"))


@pytest.fixture
def loaded(hydra: HydraClient) -> dataset.Dataset:
    built = dataset.build(SEED, SMALL)
    load(hydra, built.graph, built.support)
    for shortcut_type in SHORTCUT_TYPES:
        for existing in (*list_edge_keys(hydra, shortcut_type), *list_edge_keys(hydra, quarantine_type(shortcut_type))):
            hydra.run(q.delete_edge(existing.rel_type), {"src": existing.src, "dst": existing.dst})
    for withheld in built.ingested.pool:
        hydra.run(q.delete_edge(withheld.rel_type.value), {"src": withheld.src, "dst": withheld.dst})
    return built


def read_shortcut_count(hydra: HydraClient, rel_type: str) -> int:
    return len(list_edge_keys(hydra, rel_type))


def _candidates(built: dataset.Dataset) -> tuple[EdgeKey, ...]:
    return tuple(EdgeKey(e.src, e.rel_type.value, e.dst) for e in built.graph.edges)


def test_d2_a_round_judges_the_train_split_then_changes_the_graph_and_scores_held_out(
    hydra: HydraClient,
    loaded: dataset.Dataset,
    tmp_path: Path,
    mend_config: MendConfig,
    search_config: SearchConfig,
) -> None:
    journal = Journal.for_run("round-full", tmp_path)
    outcome = run_round(
        hydra,
        journal,
        Ledger.for_run("round-full", tmp_path),
        Tape.for_run("round-full", tmp_path),
        "round-full",
        1,
        MendPolicy.FULL,
        build_index(loaded.graph.nodes),
        loaded.split.train,
        loaded.split.held_out,
        _candidates(loaded),
        Random(1),
        mend_config,
        search_config,
        loaded.documents,
        loaded.ingested.pool,
    )
    assert outcome.train.n == len(loaded.split.train)
    assert outcome.held_out.n == len(loaded.split.held_out)
    assert outcome.planned == outcome.applied
    assert outcome.planned.reweights > 0
    assert len(outcome.receipt_ids) == (
        outcome.applied.reweights
        + outcome.applied.quarantines
        + len(outcome.promoted)
        + len(outcome.retired)
        + len(outcome.ingested)
    )
    assert len(journal.lines()) == len(outcome.receipt_ids)
    assert len(set(outcome.receipt_ids)) == len(outcome.receipt_ids)


def test_d2_a_frozen_round_scores_the_same_questions_without_touching_the_graph(
    hydra: HydraClient,
    loaded: dataset.Dataset,
    tmp_path: Path,
    mend_config: MendConfig,
    search_config: SearchConfig,
) -> None:
    index = build_index(loaded.graph.nodes)
    before = {key: read_state(hydra, key) for key in _candidates(loaded)[:40]}
    outcome = run_round(
        hydra,
        Journal.for_run("round-frozen", tmp_path),
        Ledger.for_run("round-frozen", tmp_path),
        Tape.for_run("round-frozen", tmp_path),
        "round-frozen",
        1,
        MendPolicy.FROZEN,
        index,
        loaded.split.train,
        loaded.split.held_out,
        _candidates(loaded),
        Random(1),
        mend_config,
        search_config,
    )
    assert outcome.receipt_ids == ()
    assert outcome.applied.reweights == 0
    assert outcome.applied.quarantines == 0
    assert {key: read_state(hydra, key) for key in before} == before


def test_inv6_on_a_real_plan_each_random_arm_mirrors_its_control(
    hydra: HydraClient, loaded: dataset.Dataset, mend_config: MendConfig, search_config: SearchConfig
) -> None:
    judged = judge_all(hydra, build_index(loaded.graph.nodes), [t.question for t in loaded.split.train], search_config)
    planned = plan(hydra, verdicts_for(hydra, judged, search_config), mend_config)
    assert profile(planned).reweights > 0
    for arm, control in CONTROL_OF.items():
        mirrored = shape(arm, planned, _candidates(loaded), Random(5))
        assert profile(mirrored) == profile(shape(control, planned, _candidates(loaded), Random(5)))


def test_d4_a_confirmed_path_is_promoted_to_a_shortcut_the_search_then_uses(
    hydra: HydraClient,
    loaded: dataset.Dataset,
    tmp_path: Path,
    mend_config: MendConfig,
    search_config: SearchConfig,
) -> None:
    eager = replace(mend_config, promote_min_questions=2)
    outcome = run_round(
        hydra,
        Journal.for_run("round-promote", tmp_path),
        Ledger.for_run("round-promote", tmp_path),
        Tape.for_run("round-promote", tmp_path),
        "round-promote",
        1,
        MendPolicy.PROMOTE_ONLY,
        build_index(loaded.graph.nodes),
        loaded.split.train,
        loaded.split.held_out,
        _candidates(loaded),
        Random(1),
        eager,
        search_config,
    )
    assert outcome.applied.reweights == 0
    assert outcome.applied.quarantines == 0
    assert outcome.promoted, "no path was confirmed often enough to compress"
    created = read_state(hydra, outcome.promoted[0])
    assert created is not None
    assert created.status is EdgeStatus.ACTIVE
    assert len(created.via_path) >= 2
    assert created.cost == float(len(created.via_path))
    reached = score_paths(
        hydra.run(q.weighted_paths_from([created.key.rel_type], 1, 50), {"src": created.key.src}).rows
    )
    assert created.key.dst in {path.terminal for path in reached}
    assert created.cost in {path.cost for path in reached}


def test_d4_inv5_a_shortcut_is_retired_once_one_of_its_hops_is_quarantined(
    hydra: HydraClient,
    loaded: dataset.Dataset,
    tmp_path: Path,
    mend_config: MendConfig,
    search_config: SearchConfig,
) -> None:
    eager = replace(mend_config, promote_min_questions=2)
    journal = Journal.for_run("round-retire", tmp_path)
    ledger = Ledger.for_run("round-retire", tmp_path)
    run_round(
        hydra,
        journal,
        ledger,
        Tape.for_run("round-retire", tmp_path),
        "round-retire",
        1,
        MendPolicy.PROMOTE_ONLY,
        build_index(loaded.graph.nodes),
        loaded.split.train,
        loaded.split.held_out,
        _candidates(loaded),
        Random(1),
        eager,
        search_config,
    )
    live = live_shortcuts(hydra)
    assert live, "the promote round left no shortcut to retire"
    key, via_path = sorted(live.items())[0]
    apply(hydra, journal, "round-retire", 2, 900, Quarantine(via_path[0], ("manual",)), eager)
    retired = run_shortcuts(hydra, journal, "round-retire", 2, 0, ledger.all(), eager)
    assert key in {r.edge for r in retired.retired}
    assert read_state(hydra, key) is None
    assert key not in live_shortcuts(hydra)


def _an_unreachable_question(
    hydra: HydraClient, built: dataset.Dataset, search_config: SearchConfig
) -> tuple[Question, Unreachable] | None:
    index = build_index(built.graph.nodes)
    for item in built.split.train:
        if not built.documents.mentioning(item.question.seed_entity_id, pool_only=True):
            continue
        judged = judge(hydra, index, item.question, search_config)
        if judged.verdict is not Verdict.UNREACHABLE:
            continue
        outcome = outcome_for(hydra, judged, search_config)
        if isinstance(outcome, Unreachable):
            return item.question, outcome
    return None


def test_d5_a_gap_is_filled_from_pool_documents_and_the_question_becomes_answerable(
    hydra: HydraClient,
    loaded: dataset.Dataset,
    tmp_path: Path,
    mend_config: MendConfig,
    search_config: SearchConfig,
) -> None:
    found = _an_unreachable_question(hydra, loaded, search_config)
    if found is None:
        pytest.skip("this seed left no unreachable train question to fill")
    question, gap = found
    journal = Journal.for_run("round-gapfill", tmp_path)
    filled = run_gapfill(
        hydra,
        journal,
        "round-gapfill",
        1,
        0,
        loaded.documents,
        loaded.ingested.pool,
        [gap],
        mend_config,
    )
    if not filled.fills:
        pytest.skip("no pool document mentions this seed entity")
    for change in filled.fills:
        landed = read_state(hydra, change.edge)
        assert landed is not None
        assert landed.status is EdgeStatus.ACTIVE
        assert landed.cost == INITIAL_COST
    assert len(journal.lines()) == len(filled.receipts)
    assert all(r.kind == "gapfill" for r in filled.receipts)
    again = judge(hydra, build_index(loaded.graph.nodes), question, search_config)
    assert again.verdict is not Verdict.UNREACHABLE


def test_d5_a_gap_already_in_the_graph_is_not_ingested_twice(
    hydra: HydraClient,
    loaded: dataset.Dataset,
    tmp_path: Path,
    mend_config: MendConfig,
    search_config: SearchConfig,
) -> None:
    found = _an_unreachable_question(hydra, loaded, search_config)
    if found is None:
        pytest.skip("this seed left no unreachable train question to fill")
    journal = Journal.for_run("round-gapfill-twice", tmp_path)
    first = run_gapfill(hydra, journal, "run", 1, 0, loaded.documents, loaded.ingested.pool, [found[1]], mend_config)
    if not first.fills:
        pytest.skip("no pool document mentions this seed entity")
    second = run_gapfill(hydra, journal, "run", 2, 0, loaded.documents, loaded.ingested.pool, [found[1]], mend_config)
    assert second.fills == ()
    assert second.receipts == ()
