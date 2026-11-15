from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from trailmend.core.credit import Outcome, SetJudged, Unreachable, Wrong, assign_credit, confirmed_paths
from trailmend.core.model import Change, Credit, EdgeKey, MendConfig, Quarantine, SearchConfig
from trailmend.core.promote import Confirmation
from trailmend.core.receipts import Receipt
from trailmend.core.update import plan_round
from trailmend.data.documents import DocumentSet
from trailmend.data.model import Edge
from trailmend.data.qtemplates import template
from trailmend.eval.splits import HeldOutQuestion, TrainQuestion
from trailmend.graph.client import HydraClient
from trailmend.graph.state import read_states
from trailmend.loop.apply import apply
from trailmend.loop.credit_round import outcome_for
from trailmend.loop.evaluate import Judged, Score, judge_all, score
from trailmend.loop.gapfill import NARROW, WRONG, Filled, Gap, GapfillRule, gap_of, run_gapfill
from trailmend.loop.journal import Journal
from trailmend.loop.ledger import Ledger
from trailmend.loop.policy import ChangeProfile, MendPolicy, mechanisms, profile, shape
from trailmend.loop.shortcuts import ShortcutRound, run_shortcuts
from trailmend.loop.tape import Tape
from trailmend.search.seed import EntityIndex

type Verdicts = tuple[tuple[Judged, Outcome], ...]


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
    promoted: tuple[EdgeKey, ...]
    retired: tuple[EdgeKey, ...]
    gaps: int
    ingested: tuple[EdgeKey, ...]
    reached: tuple[EdgeKey, ...]
    receipt_ids: tuple[str, ...]


def verdicts_for(client: HydraClient, judged: Sequence[Judged], config: SearchConfig) -> Verdicts:
    return tuple((item, outcome_for(client, item, config)) for item in judged)


def credits_of(verdicts: Verdicts) -> tuple[Credit, ...]:
    return tuple(credit for _, outcome in verdicts for credit in assign_credit(outcome))


def confirmations_of(verdicts: Verdicts) -> tuple[Confirmation, ...]:
    return tuple(
        Confirmation(judged.question_id, template(judged.template).shortcut_type, tuple(path))
        for judged, outcome in verdicts
        for path in confirmed_paths(outcome)
    )


def gaps_of(verdicts: Verdicts, rule: GapfillRule = NARROW) -> tuple[Gap, ...]:
    gaps: list[Gap] = []
    for judged, outcome in verdicts:
        match outcome:
            case Unreachable():
                gaps.append(gap_of(outcome))
            case Wrong() if rule.on_wrong:
                gaps.append(Gap(outcome.question_id, judged.seed_entity_id, WRONG))
            case SetJudged(wrong_paths=wrong, missed_gold_paths=missed) if rule.on_wrong and (wrong or missed):
                gaps.append(Gap(outcome.question_id, judged.seed_entity_id, WRONG))
            case _:
                continue
    return tuple(gaps)


def plan(client: HydraClient, verdicts: Verdicts, config: MendConfig) -> tuple[Change, ...]:
    credits = credits_of(verdicts)
    edges = sorted(dict.fromkeys(credit.edge for credit in credits))
    return plan_round(read_states(client, edges), credits, config)


def run_round(
    client: HydraClient,
    journal: Journal,
    ledger: Ledger,
    tape: Tape,
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
    documents: DocumentSet | None = None,
    pool: Sequence[Edge] = (),
    gapfill_rule: GapfillRule = NARROW,
) -> RoundOutcome:
    arms = mechanisms(policy)
    judged_train = judge_all(client, index, [item.question for item in train], search_config)
    verdicts = verdicts_for(client, judged_train, search_config)
    planned = plan(client, verdicts, mend_config)
    chosen = shape(policy, planned, candidates, rng)
    receipts: list[Receipt] = []
    for sequence, change in enumerate(chosen):
        receipts.append(apply(client, journal, run_id, round_index, sequence, change, mend_config).receipt)
    ledger.extend(confirmations_of(verdicts))
    shortcuts = ShortcutRound((), (), ())
    if arms.promote:
        shortcuts = run_shortcuts(client, journal, run_id, round_index, len(chosen), ledger.all(), mend_config)
    gaps = gaps_of(verdicts, gapfill_rule if arms.gapfill else NARROW)
    filled = Filled(gaps, (), ())
    if arms.gapfill:
        if documents is None:
            raise ValueError(f"{policy} fills gaps, so it needs the document set and the pool")
        filled = run_gapfill(
            client,
            journal,
            run_id,
            round_index,
            len(chosen) + len(shortcuts.receipts),
            documents,
            pool,
            gaps,
            mend_config,
            gapfill_rule,
        )
    judged_held_out = judge_all(client, index, [item.question for item in held_out], search_config)
    tape.record(round_index, judged_held_out)
    return RoundOutcome(
        run_id,
        round_index,
        policy,
        score(judged_train),
        score(judged_held_out),
        profile(planned),
        profile(chosen),
        tuple(c.edge for c in chosen if isinstance(c, Quarantine)),
        tuple(p.edge for p in shortcuts.promoted),
        tuple(r.edge for r in shortcuts.retired),
        len(gaps),
        tuple(f.edge for f in filled.fills),
        filled.reached,
        tuple(r.receipt_id for r in (*receipts, *shortcuts.receipts, *filled.receipts)),
    )
