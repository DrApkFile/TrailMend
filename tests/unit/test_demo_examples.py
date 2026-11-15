from trailmend.api.examples import entities_with_a_repairable_fault, one_per_template
from trailmend.data import dataset
from trailmend.data.faultmodel import V2, WrongKind

DEMO_SEED = 1


def test_an_example_is_offered_for_every_template_the_training_split_asks() -> None:
    built = dataset.build(DEMO_SEED, data_version=V2)
    repairable = entities_with_a_repairable_fault(built.ingested.faults)
    chosen = one_per_template(built.split.train, repairable)
    assert set(chosen) == {item.question.template for item in built.split.train}


def test_the_demo_offers_a_question_whose_wrong_answer_can_be_repaired() -> None:
    built = dataset.build(DEMO_SEED, data_version=V2)
    repairable = entities_with_a_repairable_fault(built.ingested.faults)
    chosen = one_per_template(built.split.train, repairable)
    asked = {example.question for example in chosen.values()}
    seeded_at_a_contradiction = {
        item.question.text for item in built.split.train if item.question.seed_entity_id in repairable
    }
    assert asked & seeded_at_a_contradiction


def test_a_template_with_no_repairable_question_still_gets_its_first() -> None:
    built = dataset.build(DEMO_SEED, data_version=V2)
    chosen = one_per_template(built.split.train, frozenset())
    first: dict[str, str] = {}
    for item in built.split.train:
        first.setdefault(item.question.template, item.question.text)
    assert {name: example.question for name, example in chosen.items()} == first


def test_only_a_contradicted_fault_counts_as_repairable() -> None:
    built = dataset.build(DEMO_SEED, data_version=V2)
    repairable = entities_with_a_repairable_fault(built.ingested.faults)
    faults = built.ingested.faults
    assert repairable == {fault.src for fault in faults.wrong_of_kind(WrongKind.CONTRADICTED)}
    assert repairable
