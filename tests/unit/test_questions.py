import hashlib
import os
import subprocess
import sys
from collections import Counter

import pytest

from trailmend.data.faults import inject
from trailmend.data.northwind import generate
from trailmend.data.qtemplates import TEMPLATES, template
from trailmend.data.questions import QuestionSet, adjacency, build, follow, to_json

SEED = 7
SEEDS = (1, 7, 42)


@pytest.fixture(scope="module")
def questions() -> QuestionSet:
    return build(generate(SEED))


def test_b4_every_seed_yields_at_least_six_hundred_questions() -> None:
    for seed in SEEDS:
        assert len(build(generate(seed)).questions) >= 600


def test_b4_questions_cover_one_two_and_three_hop_paths(questions: QuestionSet) -> None:
    assert set(Counter(q.hops for q in questions.questions)) == {1, 2, 3}


def test_b4_every_question_names_its_seed_entity(questions: QuestionSet) -> None:
    truth = generate(SEED)
    names = {n.id: n.name for n in truth.nodes}
    for question in questions.questions:
        assert question.seed_entity_name == names[question.seed_entity_id]
        assert question.seed_entity_name in question.text


def test_b4_gold_answers_are_what_the_truth_graph_says(questions: QuestionSet) -> None:
    links = adjacency(generate(SEED))
    for question in questions.questions:
        spec = template(question.template)
        assert question.gold == follow(links, question.seed_entity_id, spec.rel_path)
        assert question.gold


def test_b4_gold_answers_come_from_t_and_not_from_the_faulty_ingested_graph(questions: QuestionSet) -> None:
    truth = generate(SEED)
    ingested = inject(truth)
    truth_links = adjacency(truth)
    g0_links = adjacency(ingested.graph)
    disagreed = 0
    for question in questions.questions:
        spec = template(question.template)
        on_truth = follow(truth_links, question.seed_entity_id, spec.rel_path)
        on_g0 = follow(g0_links, question.seed_entity_id, spec.rel_path)
        assert question.gold == on_truth
        disagreed += on_truth != on_g0
    assert disagreed > 0, "the planted faults never change an answer, so the test proves nothing"


def test_b4_a_single_answer_template_always_has_exactly_one_gold_answer(questions: QuestionSet) -> None:
    for question in questions.questions:
        if template(question.template).single_answer:
            assert len(question.gold) == 1


def test_b4_every_gold_answer_has_the_label_the_template_expects(questions: QuestionSet) -> None:
    by_id = generate(SEED).by_id
    for question in questions.questions:
        for answer in question.gold:
            assert by_id[answer].label is question.answer_label


def test_b4_each_seed_entity_is_asked_at_most_once_per_template(questions: QuestionSet) -> None:
    pairs = [(q.template, q.seed_entity_id) for q in questions.questions]
    assert len(set(pairs)) == len(pairs)
    assert len({q.id for q in questions.questions}) == len(pairs)


def test_b4_no_template_exceeds_its_cap(questions: QuestionSet) -> None:
    counts = Counter(q.template for q in questions.questions)
    for spec in TEMPLATES:
        assert counts[spec.name] <= spec.cap


def test_b4_the_same_seed_builds_byte_identical_questions(questions: QuestionSet) -> None:
    assert to_json(build(generate(SEED))) == to_json(questions)


def test_b4_the_question_digest_survives_a_fresh_interpreter_with_a_different_hash_seed(
    questions: QuestionSet,
) -> None:
    script = (
        "import hashlib;"
        "from trailmend.data.northwind import generate;"
        "from trailmend.data.questions import build, to_json;"
        f"print(hashlib.sha256(to_json(build(generate({SEED}))).encode()).hexdigest())"
    )
    env = {**os.environ, "PYTHONHASHSEED": "24680"}
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True, env=env)
    assert out.stdout.strip() == hashlib.sha256(to_json(questions).encode()).hexdigest()


def test_b4_a_template_that_does_not_name_its_seed_is_refused() -> None:
    spec = TEMPLATES[0]
    with pytest.raises(ValueError, match="must name its seed entity"):
        type(spec)("broken", spec.seed_label, spec.rel_path, spec.answer_label, "who owns it?", True, 1)
