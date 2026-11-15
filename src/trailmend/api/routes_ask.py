from fastapi import APIRouter, Request

from trailmend.api.models import AskRequest, AskResponse, JudgeRequest, JudgeResponse
from trailmend.api.paths import hops_of
from trailmend.api.state import Live, now
from trailmend.core.credit import Outcome, Refused, SetJudged, Wrong, assign_credit
from trailmend.core.model import Signal
from trailmend.core.update import plan_round
from trailmend.data.qtemplates import TEMPLATES, QuestionTemplate
from trailmend.errors import ErrorCode, TrailMendError
from trailmend.graph.state import read_states
from trailmend.loop.apply import apply
from trailmend.loop.evaluate import Verdict
from trailmend.search.answer import AnswerFound, AnswerRefused, answer
from trailmend.search.seed import SeedFound, seed_entity

router = APIRouter()


def _live(request: Request) -> Live:
    live: Live = request.app.state.live
    return live


def _template_for(text: str) -> QuestionTemplate | None:
    lowered = text.lower()
    for spec in TEMPLATES:
        head = spec.text.split("{seed}")[0].strip().lower()
        if head and lowered.startswith(head):
            return spec
    return None


@router.post("/v1/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request) -> AskResponse:
    live = _live(request)
    live.limiter.check(request.client.host if request.client else "unknown", now())
    spec = _template_for(body.question)
    if spec is None:
        raise TrailMendError(ErrorCode.INVALID_REQUEST, "this question does not match a known template")
    found = seed_entity(live.index, body.question)
    if not isinstance(found, SeedFound):
        raise TrailMendError(found.code, body.question)
    outcome = answer(
        live.client,
        found.entity_id,
        spec.search_types,
        spec.answer_label,
        live.search,
        multi_answer=not spec.single_answer,
    )
    if isinstance(outcome, AnswerRefused):
        raise TrailMendError(outcome.code, body.question)
    return AskResponse(
        question=body.question,
        seed_entity_id=found.entity_id,
        seed_entity_name=live.name_of(found.entity_id),
        matched_how=found.how,
        answer_ids=outcome.answer_ids,
        answer_names=tuple(live.name_of(entity) for entity in outcome.answer_ids),
        cost=outcome.cost,
        paths=hops_of(live, outcome.paths),
        template=spec.name,
    )


def _outcome(question_id: str, found: AnswerFound, body: JudgeRequest) -> Outcome:
    if body.verdict is Verdict.CORRECT:
        return SetJudged(question_id, found.paths, (), ())
    if body.verdict is Verdict.WRONG:
        wanted = set(body.correct_answer_ids)
        wrong = tuple(path for entity, path in zip(found.answer_ids, found.paths, strict=True) if entity not in wanted)
        right = tuple(path for entity, path in zip(found.answer_ids, found.paths, strict=True) if entity in wanted)
        return SetJudged(question_id, right, wrong, ()) if right or wrong else Wrong(question_id, found.paths[0], None)
    return Refused(question_id, body.verdict.value)


@router.post("/v1/judge", response_model=JudgeResponse)
def judge(body: JudgeRequest, request: Request) -> JudgeResponse:
    live = _live(request)
    spec = _template_for(body.question)
    if spec is None:
        raise TrailMendError(ErrorCode.INVALID_REQUEST, "this question does not match a known template")
    seed = seed_entity(live.index, body.question)
    if not isinstance(seed, SeedFound):
        raise TrailMendError(seed.code, body.question)
    outcome = answer(
        live.client,
        seed.entity_id,
        spec.search_types,
        spec.answer_label,
        live.search,
        multi_answer=not spec.single_answer,
    )
    if isinstance(outcome, AnswerRefused):
        raise TrailMendError(outcome.code, body.question)
    question_id = f"live-{spec.name}-{seed.entity_id}"
    credits = assign_credit(_outcome(question_id, outcome, body))
    if not credits:
        return JudgeResponse(
            question=body.question,
            verdict=body.verdict,
            confirmed=(),
            blamed=(),
            receipts=(),
            changed_anything=False,
        )
    edges = sorted(dict.fromkeys(credit.edge for credit in credits))
    changes = plan_round(read_states(live.client, edges), credits, live.mend)
    receipts = [
        apply(live.client, live.journal, live.settings.live_run_id, 0, index, change, live.mend).receipt
        for index, change in enumerate(changes)
    ]
    return JudgeResponse(
        question=body.question,
        verdict=body.verdict,
        confirmed=tuple(c.edge.dst for c in credits if c.signal is Signal.CONFIRM),
        blamed=tuple(c.edge.dst for c in credits if c.signal is Signal.BLAME),
        receipts=tuple(r.receipt_id for r in receipts),
        changed_anything=bool(receipts),
    )
