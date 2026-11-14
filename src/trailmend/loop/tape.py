import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from trailmend.core.model import EdgeKey
from trailmend.loop.evaluate import Judged
from trailmend.loop.journal import RUNS_DIR, require_run_id


@dataclass(frozen=True, slots=True)
class Answered:
    round_index: int
    question_id: str
    template: str
    verdict: str
    answer_ids: tuple[int, ...]
    paths: tuple[tuple[EdgeKey, ...], ...]


@dataclass(frozen=True, slots=True)
class Tape:
    path: Path

    @classmethod
    def for_run(cls, run_id: str, root: Path = RUNS_DIR) -> "Tape":
        directory = root / require_run_id(run_id)
        directory.mkdir(parents=True, exist_ok=True)
        return cls(directory / "heldout.jsonl")

    def record(self, round_index: int, judged: Sequence[Judged]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            for item in judged:
                handle.write(
                    json.dumps(
                        {
                            "round": round_index,
                            "question_id": item.question_id,
                            "template": item.template,
                            "verdict": item.verdict.value,
                            "answer_ids": list(item.answer_ids),
                            "paths": [[[h.src, h.rel_type, h.dst] for h in path] for path in item.paths],
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )
            handle.flush()
            os.fsync(handle.fileno())

    def rounds(self) -> tuple[Answered, ...]:
        if not self.path.exists():
            return ()
        found: list[Answered] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            row = json.loads(line)
            found.append(
                Answered(
                    int(row["round"]),
                    str(row["question_id"]),
                    str(row["template"]),
                    str(row["verdict"]),
                    tuple(int(a) for a in row["answer_ids"]),
                    tuple(tuple(EdgeKey(int(h[0]), str(h[1]), int(h[2])) for h in path) for path in row["paths"]),
                )
            )
        return tuple(found)
