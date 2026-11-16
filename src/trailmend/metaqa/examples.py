import json
from collections.abc import Mapping

from trailmend.eval import evidence
from trailmend.graph.schema import NodeLabel
from trailmend.loop.journal import RUNS_DIR
from trailmend.loop.tape import Answered, Tape
from trailmend.metaqa.analyse import rows_of, run_id_of
from trailmend.metaqa.kb import read_kb
from trailmend.metaqa.questions import TEST, RawQuestion, read_split
from trailmend.metaqa.world import build_world

SEED = 1
PER_HOP_FIXED = 2
PER_HOP_STILL_WRONG = 1
DESIGN = (
    "Recorded MetaQA held-out questions from seed 1 of the MetaQA run, shown on the site so a visitor can read real "
    "public-data questions and what the graph answered. Nothing here is answered live. The selection rule is fixed "
    "in code and does not look at anything but the tapes: for each hop count, in question-id order, the first two "
    "questions that the frozen graph got wrong or could not reach at the last round and full_v2 got right, then the "
    "first question full_v2 still got wrong. Names are read back from the knowledge base by the same id function "
    "the run used."
)


def _names(seed: int) -> dict[int, tuple[str, str]]:
    world = build_world(read_kb(), seed)
    return {world.node(label, name): (label.value, name) for label, names in world.names.items() for name in names}


def _final(run: str) -> tuple[int, dict[str, Answered]]:
    answers = Tape.for_run(run, RUNS_DIR).rounds()
    last = max(a.round_index for a in answers)
    return last, {a.question_id: a for a in answers if a.round_index == last}


def _named(answer: Answered, names: Mapping[int, tuple[str, str]]) -> list[str]:
    return [names[i][1] if i in names else str(i) for i in answer.answer_ids]


def main() -> int:
    run_id = run_id_of(rows_of())
    names = _names(SEED)
    last, frozen = _final(f"{run_id}-s{SEED}-frozen")
    _, mended = _final(f"{run_id}-s{SEED}-full_v2")
    questions: dict[str, RawQuestion] = {q.id: q for q in read_split(TEST)}
    rows: list[dict[str, object]] = []
    for hop in (1, 2, 3):
        ids = sorted(q for q in mended if questions[q].hop == hop)
        fixed = [q for q in ids if mended[q].verdict == "correct" and frozen[q].verdict != "correct"]
        wrong = [q for q in ids if mended[q].verdict != "correct"]
        for kind, picked in (("fixed", fixed[:PER_HOP_FIXED]), ("still_wrong", wrong[:PER_HOP_STILL_WRONG])):
            for qid in picked:
                raw = questions[qid]
                rows.append(
                    {
                        "kind": kind,
                        "question_id": qid,
                        "hop": hop,
                        "qtype": raw.qtype,
                        "question": raw.text.replace("[", "").replace("]", ""),
                        "topic": raw.topic,
                        "answer_label": NodeLabel(raw.answer_label).value,
                        "gold": list(raw.answers),
                        "frozen_verdict": frozen[qid].verdict,
                        "frozen_answer": _named(frozen[qid], names),
                        "full_v2_verdict": mended[qid].verdict,
                        "full_v2_answer": _named(mended[qid], names),
                        "round": last,
                        "run_id": run_id,
                        "seed": SEED,
                    }
                )
    path = evidence.write(evidence.make("metaqa_examples", DESIGN, rows))
    print(json.dumps([[r["kind"], r["question"], r["frozen_answer"], r["full_v2_answer"]] for r in rows], indent=0))
    print(f"{path} sha256={evidence.digest(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
