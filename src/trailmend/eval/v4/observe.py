import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

from trailmend.core.model import SearchConfig
from trailmend.errors import ErrorCode
from trailmend.eval.splits import HeldOutQuestion
from trailmend.graph.client import HydraClient
from trailmend.loop.evaluate import judge_all, score
from trailmend.loop.journal import RUNS_DIR
from trailmend.loop.tape import Tape
from trailmend.search.seed import EntityIndex


@dataclass(frozen=True, slots=True)
class ObserveGate:
    client: HydraClient
    index: EntityIndex
    held_out: Sequence[HeldOutQuestion]
    search: SearchConfig
    tape: Tape
    scores: dict[int, dict[str, object]] = field(default_factory=dict[int, dict[str, object]])
    refusals: dict[int, int] = field(default_factory=dict[int, int])

    def __call__(self, round_index: int) -> None:
        judged = judge_all(self.client, self.index, [item.question for item in self.held_out], self.search)
        self.tape.record(round_index, judged)
        self.scores[round_index] = asdict(score(judged))
        self.refusals[round_index] = sum(item.refusal is ErrorCode.LOW_CONFIDENCE for item in judged)


def refusal_counts(name: str) -> dict[int, int]:
    rows = [json.loads(line) for line in (RUNS_DIR / name / "heldout.jsonl").read_text().splitlines() if line]
    return dict(Counter(int(row["round"]) for row in rows if row.get("refusal") == "low_confidence"))
