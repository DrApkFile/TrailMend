import pytest

from trailmend.core.model import SearchConfig
from trailmend.data import dataset
from trailmend.data.northwind import Sizes
from trailmend.data.qtemplates import template
from trailmend.errors import ErrorCode
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.graph.loader import load
from trailmend.graph.schema import NodeLabel, RelType
from trailmend.search.answer import AnswerFound, AnswerRefused, answer
from trailmend.search.seed import SeedFound, build_index, seed_entity

pytestmark = pytest.mark.hydra

SEED = 5_151
SMALL = Sizes(people=30, teams=5, services=10, alerts=16, customers=6, incidents=4, runbooks=6, repos=4)
CONFIG = SearchConfig(max_len=3, result_limit=200)


@pytest.fixture(scope="module")
def built() -> dataset.Dataset:
    return dataset.build(SEED, SMALL)


@pytest.fixture
def loaded(hydra: HydraClient, built: dataset.Dataset) -> dataset.Dataset:
    load(hydra, built.graph)
    return built


def _page_owner(built: dataset.Dataset) -> tuple[int, tuple[int, ...]]:
    links = {(e.src, e.rel_type): e.dst for e in built.graph.edges}
    for question in built.questions.questions:
        if question.template != "page_owner":
            continue
        service = links.get((question.seed_entity_id, RelType.ALERTS_ON))
        team = links.get((service, RelType.OWNED_BY)) if service is not None else None
        person = links.get((team, RelType.ON_CALL)) if team is not None else None
        if person is not None:
            return question.seed_entity_id, (person,)
    pytest.skip("this small graph has no fully connected page_owner question")


def test_c3_a_question_seeds_and_then_answers_from_the_live_graph(hydra: HydraClient, loaded: dataset.Dataset) -> None:
    index = build_index(loaded.graph.nodes)
    question = next(q_ for q_ in loaded.questions.questions if q_.template == "service_owner_team")
    found = seed_entity(index, question.text)
    assert isinstance(found, SeedFound)
    outcome = answer(hydra, found.entity_id, template(question.template).search_types, NodeLabel.TEAM, CONFIG)
    assert isinstance(outcome, AnswerFound)
    assert outcome.answer_id in question.gold


def test_c3_the_answer_follows_the_cheapest_route_and_moves_when_a_cost_rises(
    hydra: HydraClient, loaded: dataset.Dataset
) -> None:
    alert_id, expected = _page_owner(loaded)
    types = template("page_owner").search_types
    first = answer(hydra, alert_id, types, NodeLabel.PERSON, CONFIG)
    assert isinstance(first, AnswerFound)
    assert first.answer_id == expected[0]
    last_hop = first.path[-1]
    hydra.run(
        q.set_edge_counters(last_hop.rel_type),
        {"src": last_hop.src, "dst": last_hop.dst, "cost": 15.0, "confirms": 0, "blames": 4, "recent": "BBBB"},
    )
    raised = answer(hydra, alert_id, types, NodeLabel.PERSON, CONFIG)
    assert isinstance(raised, AnswerFound)
    assert raised.cost > first.cost
    hydra.run(
        q.set_edge_counters(last_hop.rel_type),
        {"src": last_hop.src, "dst": last_hop.dst, "cost": 1.0, "confirms": 0, "blames": 0, "recent": ""},
    )


def test_c3_a_result_that_fills_the_budget_refuses_instead_of_scoring_a_partial_answer(
    hydra: HydraClient, loaded: dataset.Dataset
) -> None:
    alert_id, _ = _page_owner(loaded)
    outcome = answer(hydra, alert_id, template("page_owner").search_types, NodeLabel.PERSON, SearchConfig(3, 1))
    assert isinstance(outcome, AnswerRefused)
    assert outcome.code is ErrorCode.BUDGET_EXCEEDED


def test_inv4_search_can_never_be_asked_for_a_quarantined_type() -> None:
    with pytest.raises(ValueError, match="can never be searched"):
        q.weighted_paths_from(["Q_ON_CALL"], 3, 10)
