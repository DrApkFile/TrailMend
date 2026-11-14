import os
from dataclasses import dataclass
from pathlib import Path

from trailmend.core.receipts import Receipt, to_json

RUNS_DIR = Path("evidence/runs")


@dataclass(frozen=True, slots=True)
class Journal:
    path: Path

    @classmethod
    def for_run(cls, run_id: str, root: Path = RUNS_DIR) -> "Journal":
        if not run_id or "/" in run_id or run_id in {".", ".."}:
            raise ValueError(f"run_id must be a simple name, got {run_id!r}")
        directory = root / run_id
        directory.mkdir(parents=True, exist_ok=True)
        return cls(directory / "receipts.jsonl")

    def append(self, receipt: Receipt) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(to_json(receipt) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def lines(self) -> tuple[str, ...]:
        if not self.path.exists():
            return ()
        return tuple(line for line in self.path.read_text(encoding="utf-8").splitlines() if line)
