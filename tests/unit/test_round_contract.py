from collections.abc import Sequence
from typing import get_args, get_type_hints

from trailmend.eval.splits import HeldOutQuestion, TrainQuestion
from trailmend.loop.round import run_round


def test_inv8_the_round_runner_only_accepts_train_questions() -> None:
    hints = get_type_hints(run_round)
    assert get_args(hints["train"]) == (TrainQuestion,)
    assert hints["train"].__origin__ is Sequence


def test_inv8_held_out_questions_are_a_different_type_the_mend_never_takes() -> None:
    hints = get_type_hints(run_round)
    assert get_args(hints["held_out"]) == (HeldOutQuestion,)
    assert TrainQuestion is not HeldOutQuestion
