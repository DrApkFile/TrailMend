import json
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from random import Random

from trailmend.core.credit import Correct, Outcome, Refused, Unreachable, Wrong, assign_credit
from trailmend.core.model import Change, EdgeKey, EdgeState, EdgeStatus, MendConfig
from trailmend.core.update import plan_round
from trailmend.graph.client import HydraClient
from trailmend.graph.ids import edge_id
from trailmend.graph.state import read_state, read_states, write_state
from trailmend.loop.apply import apply
from trailmend.loop.evaluate import Verdict
from trailmend.loop.journal import RUNS_DIR, Journal, require_run_id
from trailmend.loop.policy import ChangeProfile, MendPolicy, mechanisms, profile, shape
from trailmend.metaqa.answer import MqJudged, MqScore, judge_all, score
from trailmend.metaqa.gapfill import LiveGraph, run_gapfill
from trailmend.metaqa.sample import MqQuestion

INGEST_ORIGIN = "ingest"


@dataclass(frozen=True, slots=True)
class MqRound:
    round_index: int
    policy: MendPolicy
    train: MqScore
    held_out: MqScore
    planned: ChangeProfile
    applied: ChangeProfile
    gaps: int
    filled_facts: int
    receipts: int


def outcome_of(judged: MqJudged) -> Outcome:
    match judged.verdict:
        case Verdict.CORRECT:
            return Correct(judged.question_id, judged.chosen)
        case Verdict.WRONG:
            return Wrong(judged.question_id, judged.chosen, judged.best_gold)
        case Verdict.UNREACHABLE:
            return Unreachable(judged.question_id, judged.topic_id, "", judged.qtype)
        case Verdict.REFUSED:
            return Refused(judged.question_id, judged.refusal.value if judged.refusal else "refused")


def plan(client: HydraClient, judged: Sequence[MqJudged], config: MendConfig) -> tuple[Change, ...]:
    credits = tuple(credit for item in judged for credit in assign_credit(outcome_of(item)))
    edges = sorted(dict.fromkeys(credit.edge for credit in credits))
    return plan_round(read_states(client, edges), credits, config)


def record_tape(run_id: str, round_index: int, judged: Sequence[MqJudged], root: Path = RUNS_DIR) -> None:
    directory = root / require_run_id(run_id)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "heldout.jsonl").open("a", encoding="utf-8") as handle:
        for item in judged:
            row = {
                "round": round_index,
                "question_id": item.question_id,
                "template": item.qtype,
                "verdict": item.verdict.value,
                "answer_ids": [item.top] if item.top is not None else [],
                "paths": [[[h.src, h.rel_type, h.dst] for h in item.chosen]] if item.chosen else [],
                "exact": item.exact,
            }
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_round(
    client: HydraClient,
    journal: Journal,
    run_id: str,
    round_index: int,
    policy: MendPolicy,
    live: LiveGraph,
    train: Sequence[MqQuestion],
    held_out: Sequence[MqQuestion],
    candidates: Sequence[EdgeKey],
    rng: Random,
    config: MendConfig,
    result_limit: int,
) -> MqRound:
    arms = mechanisms(policy)
    judged_train = judge_all(client, train, result_limit)
    planned = plan(client, judged_train, config)
    chosen = shape(policy, planned, candidates, rng)
    for sequence, change in enumerate(chosen):
        live.remember(apply(client, journal, run_id, round_index, sequence, change, config).before)
    gaps = 0
    filled = 0
    receipts = len(chosen)
    if arms.gapfill:
        done = run_gapfill(client, journal, run_id, round_index, len(chosen), live, train, judged_train, config)
        gaps, filled, receipts = done.gaps, len(done.facts), receipts + len(done.receipts)
    judged_held_out = judge_all(client, held_out, result_limit)
    record_tape(run_id, round_index, judged_held_out)
    return MqRound(
        round_index,
        policy,
        score(judged_train),
        score(judged_held_out),
        profile(planned),
        profile(chosen),
        gaps,
        filled,
        receipts,
    )


def restore(client: HydraClient, live: LiveGraph) -> int:
    for key, before in sorted(live.first_before.items()):
        current = read_state(client, key) or EdgeState(key, 0.0, EdgeStatus.ABSENT)
        if current != before:
            write_state(client, current, before, edge_id(key.rel_type, key.src, key.dst), INGEST_ORIGIN)
    return len(live.first_before)


def row_of(outcome: MqRound) -> dict[str, object]:
    return {
        "arm": outcome.policy.value,
        "round": outcome.round_index,
        "train": asdict(outcome.train),
        "held_out": asdict(outcome.held_out),
        "planned_reweights": outcome.planned.reweights,
        "planned_quarantines": outcome.planned.quarantines,
        "applied_reweights": outcome.applied.reweights,
        "applied_quarantines": outcome.applied.quarantines,
        "gaps": outcome.gaps,
        "gapfill_facts": outcome.filled_facts,
        "receipts": outcome.receipts,
    }
