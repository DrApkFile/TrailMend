from pathlib import Path
from random import Random

import pytest

from trailmend.core.config import load_mend_config, load_search_config
from trailmend.core.model import EdgeKey, MendConfig, SearchConfig
from trailmend.data import dataset
from trailmend.data.northwind import Sizes
from trailmend.graph.client import HydraClient
from trailmend.graph.loader import load
from trailmend.graph.state import read_state
from trailmend.loop.evaluate import judge_all
from trailmend.loop.journal import Journal
from trailmend.loop.policy import CONTROL_OF, MendPolicy, profile, shape
from trailmend.loop.round import plan, run_round
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
    load(hydra, built.graph)
    return built


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
    )
    assert outcome.train.n == len(loaded.split.train)
    assert outcome.held_out.n == len(loaded.split.held_out)
    assert outcome.planned == outcome.applied
    assert outcome.planned.reweights > 0
    assert len(outcome.receipt_ids) == outcome.applied.reweights + outcome.applied.quarantines
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
    planned = plan(hydra, judged, mend_config, search_config)
    assert profile(planned).reweights > 0
    for arm, control in CONTROL_OF.items():
        mirrored = shape(arm, planned, _candidates(loaded), Random(5))
        assert profile(mirrored) == profile(shape(control, planned, _candidates(loaded), Random(5)))
