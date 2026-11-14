import json
import os
from dataclasses import dataclass
from pathlib import Path

from trailmend.core.model import EdgeKey
from trailmend.core.promote import Confirmation
from trailmend.loop.journal import RUNS_DIR, require_run_id


@dataclass(frozen=True, slots=True)
class Ledger:
    path: Path

    @classmethod
    def for_run(cls, run_id: str, root: Path = RUNS_DIR) -> "Ledger":
        directory = root / require_run_id(run_id)
        directory.mkdir(parents=True, exist_ok=True)
        return cls(directory / "confirmations.jsonl")

    def extend(self, confirmations: tuple[Confirmation, ...]) -> None:
        if not confirmations:
            return
        with self.path.open("a", encoding="utf-8") as handle:
            for confirmation in confirmations:
                handle.write(
                    json.dumps(
                        {
                            "question_id": confirmation.question_id,
                            "shortcut_type": confirmation.shortcut_type,
                            "path": [[hop.src, hop.rel_type, hop.dst] for hop in confirmation.path],
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )
            handle.flush()
            os.fsync(handle.fileno())

    def all(self) -> tuple[Confirmation, ...]:
        if not self.path.exists():
            return ()
        found: list[Confirmation] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            row = json.loads(line)
            found.append(
                Confirmation(
                    row["question_id"],
                    row["shortcut_type"],
                    tuple(EdgeKey(int(hop[0]), str(hop[1]), int(hop[2])) for hop in row["path"]),
                )
            )
        return tuple(found)
