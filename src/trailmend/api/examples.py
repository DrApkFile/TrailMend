from collections.abc import Sequence

from trailmend.api.models import Example
from trailmend.data.faultmodel import FaultSet, WrongKind
from trailmend.eval.splits import TrainQuestion


def entities_with_a_repairable_fault(faults: FaultSet) -> frozenset[int]:
    return frozenset(fault.src for fault in faults.wrong_of_kind(WrongKind.CONTRADICTED))


def one_per_template(train: Sequence[TrainQuestion], repairable: frozenset[int]) -> dict[str, Example]:
    chosen: dict[str, Example] = {}
    for prefer_repairable in (True, False):
        for item in train:
            question = item.question
            if question.template in chosen:
                continue
            if prefer_repairable and question.seed_entity_id not in repairable:
                continue
            chosen[question.template] = Example(question=question.text, template=question.template, hops=question.hops)
    return chosen
