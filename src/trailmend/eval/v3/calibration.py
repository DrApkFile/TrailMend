import math
from collections.abc import Sequence

from trailmend.core.model import SearchConfig
from trailmend.data.qtemplates import template
from trailmend.eval.splits import TrainQuestion
from trailmend.graph.client import HydraClient
from trailmend.search.answer import AnswerFound, answer
from trailmend.search.seed import EntityIndex, SeedFound, seed_entity


def cutoff(costs: Sequence[float], quantile: float) -> float:
    if not 0 < quantile <= 1:
        raise ValueError("quantile must be in (0, 1]")
    return sorted(costs)[math.ceil(quantile * len(costs)) - 1] if costs else 0.0


def fit(
    client: HydraClient, index: EntityIndex, train: Sequence[TrainQuestion], config: SearchConfig, quantile: float
) -> tuple[tuple[tuple[str, float], ...], list[dict[str, object]]]:
    if config.confidence_thresholds or config.max_answer_cost is not None or config.gapfill_edges:
        raise ValueError("calibration requires the unchanged non-abstaining search")
    samples: dict[str, list[tuple[str, float]]] = {}
    for item in train:
        question = item.question
        collected = samples.setdefault(question.template, [])
        found = seed_entity(index, question.text)
        if not isinstance(found, SeedFound):
            continue
        spec = template(question.template)
        result = answer(
            client,
            found.entity_id,
            spec.search_types,
            question.answer_label,
            config,
            multi_answer=not spec.single_answer,
        )
        if isinstance(result, AnswerFound) and set(result.answer_ids) == set(question.gold):
            collected.append((question.id, result.cost))
    rows: list[dict[str, object]] = []
    for name, values in sorted(samples.items()):
        threshold = cutoff([cost for _, cost in values], quantile)
        rows.append(
            {
                "template": name,
                "threshold": threshold,
                "quantile": quantile,
                "correct_train_n": len(values),
                "empty_stratum": not values,
                "training_samples": [{"question_id": qid, "cost": cost} for qid, cost in values],
            }
        )
    thresholds = tuple((str(row["template"]), float(str(row["threshold"]))) for row in rows)
    return thresholds, rows
