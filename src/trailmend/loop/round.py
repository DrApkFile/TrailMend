from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from trailmend.core.credit import assign_credit
from trailmend.core.model import Change, Credit, EdgeKey, MendConfig, Quarantine, SearchConfig
from trailmend.core.receipts import Receipt
from trailmend.core.update import plan_round
from trailmend.eval.splits import HeldOutQuestion, TrainQuestion
from trailmend.graph.client import HydraClient
from trailmend.graph.state import read_states
from trailmend.loop.apply import apply
from trailmend.loop.credit_round import outcome_for
from trailmend.loop.evaluate import Judged, Score, judge_all, score
from trailmend.loop.journal import Journal
from trailmend.loop.policy import ChangeProfile, MendPolicy, profile, shape
from trailmend.search.seed import EntityIndex


@dataclass(frozen=True, slots=True)
class RoundOutcome:
    run_id: str
    round_index: int
    policy: MendPolicy
    train: Score
    held_out: Score
    planned: ChangeProfile
    applied: ChangeProfile
    quarantined: tuple[EdgeKey, ...]
    receipt_ids: tuple[str, ...]


def credits_for(client: HydraClient, judged: Sequence[Judged], config: SearchConfig) -> tuple[Credit, ...]:
    return tuple(credit for item in judged for credit in assign_credit(outcome_for(client, item, config)))


def plan(
    client: HydraClient, judged: Sequence[Judged], mend_config: MendConfig, search_config: SearchConfig
) -> tuple[Change, ...]:
    credits = credits_for(client, judged, search_config)
    edges = sorted(dict.fromkeys(credit.edge for credit in credits))
    return plan_round(read_states(client, edges), credits, mend_config)


def run_round(
    client: HydraClient,
    journal: Journal,
    run_id: str,
    round_index: int,
    policy: MendPolicy,
    index: EntityIndex,
    train: Sequence[TrainQuestion],
    held_out: Sequence[HeldOutQuestion],
    candidates: Sequence[EdgeKey],
    rng: Random,
    mend_config: MendConfig,
    search_config: SearchConfig,
) -> RoundOutcome:
    judged_train = judge_all(client, index, [item.question for item in train], search_config)
    planned = plan(client, judged_train, mend_config, search_config)
    chosen = shape(policy, planned, candidates, rng)
    receipts: list[Receipt] = []
    for sequence, change in enumerate(chosen):
        receipts.append(apply(client, journal, run_id, round_index, sequence, change, mend_config).receipt)
    judged_held_out = judge_all(client, index, [item.question for item in held_out], search_config)
    return RoundOutcome(
        run_id,
        round_index,
        policy,
        score(judged_train),
        score(judged_held_out),
        profile(planned),
        profile(chosen),
        tuple(c.edge for c in chosen if isinstance(c, Quarantine)),
        tuple(receipt.receipt_id for receipt in receipts),
    )
