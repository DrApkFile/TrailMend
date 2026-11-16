from collections.abc import Sequence
from pathlib import Path
from random import Random
from typing import cast

import pytest

from trailmend.core.config import load_mend_config
from trailmend.core.model import Change, EdgeKey, MendConfig, SearchConfig
from trailmend.data import dataset
from trailmend.data.questions import Question
from trailmend.errors import ErrorCode
from trailmend.eval.v4.analyse import within_budget
from trailmend.graph.client import HydraClient, Params, QueryResult
from trailmend.graph.queries import NamedQuery
from trailmend.graph.schema import NodeLabel
from trailmend.graph.values import PathRel, PathValue
from trailmend.loop.evaluate import Judged, Verdict
from trailmend.loop.journal import Journal
from trailmend.loop.ledger import Ledger
from trailmend.loop.policy import MendPolicy
from trailmend.loop.round import Verdicts, credits_of, run_round
from trailmend.loop.tape import Tape
from trailmend.search.answer import AnswerFound, answer
from trailmend.search.seed import EntityIndex, build_index


@pytest.mark.parametrize("multi", [False, True])
def test_run4_set_search_uses_base_hops_while_single_answers_retain_weighted_shortcuts(
    monkeypatch: pytest.MonkeyPatch, multi: bool
) -> None:
    observed: list[str] = []
    path = PathValue((1, 2), (PathRel("SERVES", 1, 2, {}),))

    def execute(_self: HydraClient, query: NamedQuery, _params: Params) -> QueryResult:
        observed.append(query.cypher)
        return QueryResult("test", "test", ("path", "weight"), ((path, 1.0),))

    monkeypatch.setattr(HydraClient, "run", execute)
    with HydraClient("http://127.0.0.1:1", "test", "default", "cell-0", 1.0) as client:
        result = answer(
            client,
            1,
            ("SERVES", "SC_SERVICE_CUSTOMERS"),
            NodeLabel.CUSTOMER,
            SearchConfig(1, 10, unweighted_sets=True),
            multi_answer=multi,
        )
    assert isinstance(result, AnswerFound)
    assert ("weightProp" in observed[0]) is (not multi)
    assert ("SC_SERVICE_CUSTOMERS" in observed[0]) is (not multi)


def test_run4_public_refusal_does_not_suppress_internal_training_credit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    built = dataset.build(71771)
    trained = built.split.train[:1]
    held = built.split.held_out[:1]
    teacher = SearchConfig(3, 200)
    public = SearchConfig(3, 200, max_answer_cost=0.0)
    calls: list[SearchConfig] = []

    def judge(
        _client: HydraClient, _index: EntityIndex, questions: Sequence[Question], config: SearchConfig
    ) -> tuple[Judged, ...]:
        calls.append(config)
        q = questions[0]
        if config.max_answer_cost is not None:
            return (
                Judged(q.id, q.template, q.seed_entity_id, Verdict.REFUSED, ErrorCode.LOW_CONFIDENCE, (), q.gold, ()),
            )
        paths = tuple((EdgeKey(q.seed_entity_id, "SERVES", target),) for target in q.gold)
        return (Judged(q.id, q.template, q.seed_entity_id, Verdict.CORRECT, None, q.gold, q.gold, paths),)

    def plan(_client: HydraClient, verdicts: Verdicts, _config: MendConfig) -> tuple[Change, ...]:
        assert verdicts[0][0].question_id == trained[0].question.id
        assert credits_of(verdicts)
        return ()

    monkeypatch.setattr("trailmend.loop.round.judge_all", judge)
    monkeypatch.setattr("trailmend.loop.round.plan", plan)
    result = run_round(
        cast("HydraClient", object()),
        Journal.for_run("test", tmp_path),
        Ledger.for_run("test", tmp_path),
        Tape.for_run("test", tmp_path),
        "test",
        1,
        MendPolicy.FROZEN_V4,
        build_index(built.graph.nodes),
        trained,
        held,
        (),
        Random(1),
        load_mend_config(Path("config/mend.toml")),
        public,
        train_search_config=teacher,
    )
    assert calls == [teacher, public]
    assert result.train.correct == 1
    assert result.held_out.correct == 0
    assert result.held_out.refused == 1


def test_run4_accuracy_budget_must_hold_against_both_controls() -> None:
    assert within_budget(0.90, [0.92, 0.86])
    assert not within_budget(0.89, [0.92, 0.86])
    assert not within_budget(0.89, [0.86, 0.92])
