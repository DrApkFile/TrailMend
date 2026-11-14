import re
from collections import Counter
from pathlib import Path

import pytest

from trailmend.data.northwind import generate
from trailmend.data.questions import build
from trailmend.eval.splits import HeldOutQuestion, Split, TrainQuestion, make_split, to_json

SEED = 7
SEEDS = (1, 7, 42)
SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "trailmend"
SPLITS_MODULE = SOURCE_ROOT / "eval" / "splits.py"


@pytest.fixture(scope="module")
def split() -> Split:
    return make_split(build(generate(SEED)))


def test_b5_the_split_keeps_every_question_exactly_once(split: Split) -> None:
    questions = build(generate(SEED))
    assert len(split.train) + len(split.held_out) == len(questions.questions)
    assert split.train_ids | split.held_out_ids == {q.id for q in questions.questions}


def test_inv8_no_question_is_in_both_splits(split: Split) -> None:
    assert not split.train_ids & split.held_out_ids


def test_inv8_a_held_out_question_is_a_different_type_from_a_train_question(split: Split) -> None:
    assert {type(item) for item in split.train} == {TrainQuestion}
    assert {type(item) for item in split.held_out} == {HeldOutQuestion}
    assert not issubclass(HeldOutQuestion, TrainQuestion)
    assert not issubclass(TrainQuestion, HeldOutQuestion)


def test_inv8_only_the_splitter_can_mint_a_train_question() -> None:
    minted = {
        path.relative_to(SOURCE_ROOT).as_posix()
        for path in SOURCE_ROOT.rglob("*.py")
        if re.search(r"\bTrainQuestion\(", path.read_text())
    }
    assert minted == {"eval/splits.py"}, (
        "only trailmend/eval/splits.py may construct a TrainQuestion, otherwise a held-out "
        f"question could be relabelled and fed to the Mend; also built in: {sorted(minted)}"
    )


def test_inv8_the_splitter_never_turns_a_held_out_question_into_a_train_question() -> None:
    source = SPLITS_MODULE.read_text()
    assert not re.search(r"TrainQuestion\([^)]*HeldOutQuestion", source)
    assert not re.search(r"\.question\s*for\s*\w+\s*in\s*\w*held_out", source)


def test_b5_each_stratum_is_split_sixty_forty(split: Split) -> None:
    for (name, hops), (train, held_out) in split.stratum_counts().items():
        total = train + held_out
        assert train == round(total * split.train_share), f"{name} at {hops} hops is not 60/40"


def test_b5_every_template_and_hop_count_appears_on_both_sides(split: Split) -> None:
    for (name, hops), (train, held_out) in split.stratum_counts().items():
        assert train > 0, f"{name} at {hops} hops is missing from train"
        assert held_out > 0, f"{name} at {hops} hops is missing from held-out"


def test_b5_a_seed_entity_is_never_asked_the_same_template_on_both_sides(split: Split) -> None:
    train_pairs = {(t.question.template, t.question.seed_entity_id) for t in split.train}
    held_pairs = {(h.question.template, h.question.seed_entity_id) for h in split.held_out}
    assert not train_pairs & held_pairs


def test_b5_held_out_questions_share_graph_regions_with_train_questions(split: Split) -> None:
    train_seeds = {t.question.seed_entity_id for t in split.train}
    held_seeds = {h.question.seed_entity_id for h in split.held_out}
    assert train_seeds & held_seeds, "the splits must overlap in the graph, just not in question"


def test_b5_the_same_seed_splits_the_same_way(split: Split) -> None:
    assert to_json(make_split(build(generate(SEED)))) == to_json(split)


def test_b5_every_seed_splits_close_to_sixty_forty() -> None:
    for seed in SEEDS:
        made = make_split(build(generate(seed)))
        total = len(made.train) + len(made.held_out)
        assert 0.58 <= len(made.train) / total <= 0.62


def test_b5_held_out_counts_are_large_enough_to_measure(split: Split) -> None:
    assert len(split.held_out) >= 300
    assert min(Counter(h.question.hops for h in split.held_out).values()) >= 20


def test_b5_an_impossible_share_is_refused() -> None:
    with pytest.raises(ValueError, match="train_share must be strictly between 0 and 1"):
        make_split(build(generate(SEED)), 1.0)
