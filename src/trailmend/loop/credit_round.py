from collections.abc import Sequence

from trailmend.core.credit import Correct, Outcome, Refused, SetJudged, Unreachable, Wrong
from trailmend.core.model import EdgeKey, SearchConfig
from trailmend.data.qtemplates import template
from trailmend.graph.client import HydraClient
from trailmend.loop.evaluate import Judged, Verdict
from trailmend.loop.gold import cheapest_path_to


def _gold_paths(
    client: HydraClient, judged: Judged, wanted: Sequence[int], config: SearchConfig
) -> tuple[tuple[EdgeKey, ...], ...]:
    spec = template(judged.template)
    found: list[tuple[EdgeKey, ...]] = []
    for target in wanted:
        path = cheapest_path_to(client, judged.seed_entity_id, target, spec.search_types, config)
        if path:
            found.append(path)
    return tuple(found)


def outcome_for(client: HydraClient, judged: Judged, config: SearchConfig) -> Outcome:
    if judged.verdict is Verdict.UNREACHABLE:
        spec = template(judged.template)
        return Unreachable(judged.question_id, judged.seed_entity_id, spec.answer_label.value, judged.template)
    if judged.verdict is Verdict.REFUSED:
        return Refused(judged.question_id, judged.refusal.value if judged.refusal else "refused")

    answered = dict(zip(judged.answer_ids, judged.paths, strict=True))
    gold = set(judged.gold)
    correct_paths = tuple(path for entity, path in answered.items() if entity in gold)
    wrong_paths = tuple(path for entity, path in answered.items() if entity not in gold)
    missed = tuple(sorted(gold - set(judged.answer_ids)))

    if len(judged.gold) == 1 and len(judged.answer_ids) == 1:
        if judged.verdict is Verdict.CORRECT:
            return Correct(judged.question_id, correct_paths[0])
        best = _gold_paths(client, judged, missed, config)
        return Wrong(judged.question_id, wrong_paths[0], best[0] if best else None)

    return SetJudged(judged.question_id, correct_paths, wrong_paths, _gold_paths(client, judged, missed, config))
