import pytest

from trailmend.data import dataset
from trailmend.data.model import Node, NodeFactory
from trailmend.errors import ErrorCode
from trailmend.graph.schema import NodeLabel
from trailmend.search.seed import EntityIndex, SeedFound, SeedRefused, build_index, seed_entity, tokenise

SEED = 7


@pytest.fixture(scope="module")
def built() -> dataset.Dataset:
    return dataset.build(SEED)


@pytest.fixture(scope="module")
def index(built: dataset.Dataset) -> EntityIndex:
    return build_index(built.graph.nodes)


def _nodes(*names: str) -> tuple[Node, ...]:
    mint = NodeFactory(0)
    return tuple(mint.node(NodeLabel.SERVICE, name.lower().replace(" ", "-"), name) for name in names)


def test_c2_every_generated_question_seeds_to_the_entity_it_names(built: dataset.Dataset, index: EntityIndex) -> None:
    conflated = {f.absorbed_id for f in built.ingested.faults.conflations}
    for question in built.questions.questions:
        outcome = seed_entity(index, question.text)
        assert isinstance(outcome, SeedFound), f"{question.text} was refused: {outcome}"
        if question.seed_entity_id in conflated:
            continue
        assert outcome.entity_id == question.seed_entity_id, question.text


def test_c2_a_question_naming_a_conflated_person_lands_on_the_surviving_node(
    built: dataset.Dataset, index: EntityIndex
) -> None:
    fault = built.ingested.faults.conflations[0]
    asked = next(q for q in built.questions.questions if q.seed_entity_id == fault.absorbed_id)
    outcome = seed_entity(index, asked.text)
    assert isinstance(outcome, SeedFound)
    assert outcome.entity_id == fault.kept_id
    assert fault.absorbed_id not in built.graph.by_id


def test_c2_the_longest_name_wins_so_an_alert_beats_the_service_inside_its_name(
    built: dataset.Dataset, index: EntityIndex
) -> None:
    alert = next(node for node in built.graph.nodes_with_label(NodeLabel.ALERT) if "-" in node.name)
    outcome = seed_entity(index, f"Who do I page for {alert.name}?")
    assert isinstance(outcome, SeedFound)
    assert outcome.entity_id == alert.id
    assert outcome.how == "exact"
    assert outcome.matched == alert.name.lower()


def test_c2_text_that_names_nothing_is_refused_as_no_seed(index: EntityIndex) -> None:
    outcome = seed_entity(index, "zzzqqq wibblefrotz?")
    assert isinstance(outcome, SeedRefused)
    assert outcome.code is ErrorCode.NO_SEED


def test_c2_two_entities_sharing_a_name_are_refused_as_ambiguous() -> None:
    mint_a, mint_b = NodeFactory(1), NodeFactory(2)
    twins = (
        mint_a.node(NodeLabel.SERVICE, "payments-api", "payments-api"),
        mint_b.node(NodeLabel.SERVICE, "payments-api", "payments-api"),
    )
    outcome = seed_entity(build_index(twins), "Which team owns payments-api?")
    assert isinstance(outcome, SeedRefused)
    assert outcome.code is ErrorCode.AMBIGUOUS_SEED
    assert outcome.candidates == tuple(sorted(n.id for n in twins))


def test_c2_an_alias_seeds_the_entity_that_carries_it(built: dataset.Dataset, index: EntityIndex) -> None:
    node = next(n for n in built.graph.nodes if n.aliases)
    outcome = seed_entity(index, f"Which team owns {node.aliases[0]}?")
    assert isinstance(outcome, SeedFound)
    assert outcome.entity_id == node.id


def test_c2_a_name_embedded_in_a_longer_word_does_not_match() -> None:
    nodes = _nodes("ledger")
    assert isinstance(seed_entity(build_index(nodes), "who owns the ledgerbook?"), SeedRefused)
    assert isinstance(seed_entity(build_index(nodes), "who owns the ledger?"), SeedFound)


def test_c2_the_token_fallback_picks_the_entity_with_the_rarest_shared_words() -> None:
    nodes = _nodes("checkout api", "payments worker")
    outcome = seed_entity(build_index(nodes), "the payments thing")
    assert isinstance(outcome, SeedFound)
    assert outcome.how == "token"
    assert outcome.entity_id == nodes[1].id


def test_c2_the_token_fallback_refuses_a_tie() -> None:
    nodes = _nodes("alpha core", "beta core")
    outcome = seed_entity(build_index(nodes), "the core of it")
    assert isinstance(outcome, SeedRefused)
    assert outcome.code is ErrorCode.AMBIGUOUS_SEED
    assert outcome.candidates == tuple(sorted(n.id for n in nodes))


def test_c2_seeding_is_deterministic(built: dataset.Dataset, index: EntityIndex) -> None:
    again = build_index(built.graph.nodes)
    for question in built.questions.questions[:100]:
        assert seed_entity(again, question.text) == seed_entity(index, question.text)


def test_c2_tokenising_lowercases_and_drops_punctuation() -> None:
    assert tokenise("Who pages checkout-api-latency-high?") == (
        "who",
        "pages",
        "checkout",
        "api",
        "latency",
        "high",
    )
