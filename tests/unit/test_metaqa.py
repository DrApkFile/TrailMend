from random import Random

import pytest

from trailmend.core.model import EdgeKey
from trailmend.data.faultmodel import WrongKind
from trailmend.graph.schema import NodeLabel, RelType
from trailmend.graph.values import PathRel, PathValue
from trailmend.loop.evaluate import Verdict
from trailmend.metaqa.answer import judge_ranked, rank, score
from trailmend.metaqa.gapfill import LiveGraph, facts_along
from trailmend.metaqa.kb import KnowledgeBase, Triple, reverse_of
from trailmend.metaqa.questions import RawQuestion, rel_path_of
from trailmend.metaqa.sample import MqQuestion, stratified
from trailmend.metaqa.world import build_world

DIRECTED = RelType.MQ_DIRECTED_BY.value
DIRECTED_REV = RelType.MQ_DIRECTED_BY_REV.value
STARRED = RelType.MQ_STARRED_ACTORS.value


def _kb(movies: int = 60) -> KnowledgeBase:
    triples: list[Triple] = []
    for index in range(movies):
        triples.append(Triple(f"film {index}", "directed_by", f"director {index % 7}"))
        triples.append(Triple(f"film {index}", "starred_actors", f"actor {index % 11}"))
        triples.append(Triple(f"film {index}", "release_year", str(1990 + index % 5)))
    return KnowledgeBase(len(triples), tuple(triples))


def _path(*hops: tuple[int, str, int]) -> PathValue:
    nodes = (hops[0][0], *(dst for _, _, dst in hops))
    return PathValue(nodes, tuple(PathRel(rel, src, dst, {}) for src, rel, dst in hops))


def test_a_qtype_becomes_the_relation_path_with_reverse_types_out_of_a_person() -> None:
    assert rel_path_of("movie_to_director_to_movie_to_actor") == (
        RelType.MQ_DIRECTED_BY,
        RelType.MQ_DIRECTED_BY_REV,
        RelType.MQ_STARRED_ACTORS,
    )
    assert rel_path_of("tag_to_movie") == (reverse_of(RelType.MQ_HAS_TAGS),)
    with pytest.raises(ValueError, match="cannot express"):
        rel_path_of("actor_to_director")


def test_the_world_is_half_the_triples_and_declares_every_planted_fault_by_kind() -> None:
    kb = _kb()
    world = build_world(kb, 7)
    assert world == build_world(kb, 7)
    assert world != build_world(kb, 8)
    true = set(kb.triples)
    planted = [f for f in world.ingested if f.triple not in true]
    assert {f.triple for f in planted} == {f.wrong for f in world.faults}
    assert len(world.faults) == round(len(kb.triples) / 2 * 0.08)
    in_graph = {f.triple for f in world.ingested}
    in_pool = {f.triple for f in world.pool}
    for fault in world.faults:
        if fault.kind is WrongKind.CONTRADICTED:
            assert fault.true in in_graph
        elif fault.kind is WrongKind.RECOVERABLE:
            assert fault.true not in in_graph
            assert fault.true in in_pool
        else:
            assert fault.true not in in_graph
            assert fault.true not in in_pool
    stale = {f.wrong for f in world.faults_of_kind(WrongKind.CONTRADICTED)}
    current = {f.true for f in world.faults_of_kind(WrongKind.CONTRADICTED)}
    assert all(f.support == 3 for f in world.ingested if f.triple in stale)
    assert all(f.support == 1 for f in world.ingested if f.triple in current)


def test_a_planted_wrong_object_is_never_a_true_object_of_that_movie_and_relation() -> None:
    kb = _kb()
    true = set(kb.triples)
    for seed in range(5):
        assert all(fault.wrong not in true for fault in build_world(kb, seed).faults)


def test_only_paths_that_follow_the_qtype_and_visit_no_node_twice_are_answers() -> None:
    rows = [
        (_path((1, DIRECTED, 2), (2, DIRECTED_REV, 3)), 2.0),
        (_path((1, DIRECTED, 2), (2, DIRECTED_REV, 1)), 0.2),
        (_path((1, STARRED, 9)), 0.1),
        (_path((1, DIRECTED, 4), (4, DIRECTED_REV, 3)), 1.5),
        (_path((1, DIRECTED, 4), (4, DIRECTED_REV, 5)), 1.5),
    ]
    ranked = rank(rows, (DIRECTED, DIRECTED_REV))
    assert [(r.terminal, r.cost) for r in ranked] == [
        (3, 1.5),
        (5, 1.5),
    ]
    assert ranked[0].path == (EdgeKey(1, DIRECTED, 4), EdgeKey(4, DIRECTED_REV, 3))


def _question(gold: tuple[int, ...]) -> MqQuestion:
    return MqQuestion(
        "q", "movie_to_director_to_movie", 2, "t", 1, "x", (DIRECTED, DIRECTED_REV), NodeLabel.MQ_MOVIE, gold
    )


def test_hits_at_1_asks_only_that_the_cheapest_answer_is_gold_and_exact_set_asks_for_all_of_them() -> None:
    rows = [
        (_path((1, DIRECTED, 4), (4, DIRECTED_REV, 3)), 1.0),
        (_path((1, DIRECTED, 4), (4, DIRECTED_REV, 5)), 2.0),
    ]
    ranked = rank(rows, (DIRECTED, DIRECTED_REV))
    hit = judge_ranked(_question((3,)), ranked)
    assert hit.verdict is Verdict.CORRECT
    assert not hit.exact
    assert judge_ranked(_question((3, 5)), ranked).exact
    wrong = judge_ranked(_question((5,)), ranked)
    assert wrong.verdict is Verdict.WRONG
    assert wrong.best_gold == (EdgeKey(1, DIRECTED, 4), EdgeKey(4, DIRECTED_REV, 5))
    missing = judge_ranked(_question((5,)), ())
    assert missing.verdict is Verdict.UNREACHABLE
    result = score([hit, wrong, missing])
    assert (result.hits, result.wrong, result.unreachable, result.exact) == (1, 1, 1, 0)


def test_gap_fill_takes_pool_documents_along_the_questions_own_relations_and_never_reads_gold() -> None:
    kb = _kb()
    world = build_world(kb, 3)
    live = LiveGraph.of(world)
    fact = next(f for f in world.pool if f.triple.relation == "directed_by")
    forward, _ = world.edges_of(fact.triple)
    question = MqQuestion("q", "movie_to_director", 1, "t", forward.src, "x", (DIRECTED,), NodeLabel.MQ_PERSON, ())
    found = facts_along(live, question)
    assert fact in found
    assert all(f.triple.relation == "directed_by" and f.triple.subject == fact.triple.subject for f in found)


def test_a_stratified_sample_keeps_each_qtypes_share() -> None:
    questions = [RawQuestion(1, "dev", i, "movie_to_year", "t", "x", ("a",)) for i in range(1, 31)]
    questions += [RawQuestion(1, "dev", i, "movie_to_actor", "t", "x", ("a",)) for i in range(31, 41)]
    picked = stratified(Random(1), questions, 20)
    assert len(picked) == 20
    assert sum(q.qtype == "movie_to_year" for q in picked) == 15
