import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from trailmend.eval import curve, evidence

README = Path("README.md")
START = "<!-- numbers:start -->"
END = "<!-- numbers:end -->"
MISSING = "not measured"


def _rows(name: str) -> tuple[Mapping[str, object], ...]:
    path = evidence.EVIDENCE_DIR / f"{name}.json"
    if not path.exists():
        return ()
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    rows = cast("dict[str, object]", payload).get("rows") if isinstance(payload, dict) else None
    return tuple(cast("list[Mapping[str, object]]", rows)) if isinstance(rows, list) else ()


def _curve_rows() -> tuple[Mapping[str, object], ...]:
    if not curve.CURVE.exists():
        return ()
    return tuple(json.loads(line) for line in curve.CURVE.read_text(encoding="utf-8").splitlines() if line)


def _accuracy(row: Mapping[str, object]) -> float | None:
    held = row.get("held_out")
    if not isinstance(held, dict):
        return None
    value = cast("dict[str, object]", held).get("accuracy")
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _mean(rows: Sequence[Mapping[str, object]], arm: str, round_index: int) -> float | None:
    found = [
        _accuracy(row)
        for row in rows
        if row.get("arm") == arm and row.get("round") == round_index and _accuracy(row) is not None
    ]
    kept = [value for value in found if value is not None]
    return sum(kept) / len(kept) if kept else None


def _percent(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else MISSING


def _digest(name: str) -> str:
    path = evidence.EVIDENCE_DIR / name
    return f"`{evidence.digest(path)[:16]}…`" if path.exists() else MISSING


def arms_table(rows: Sequence[Mapping[str, object]]) -> list[str]:
    arms = sorted({str(row["arm"]) for row in rows})
    if not arms:
        return ["No run has been recorded yet, so this table is empty."]
    final = max(int(str(row["round"])) for row in rows)
    lines = [
        f"| arm | round 0 | round {final} | change |",
        "|---|---|---|---|",
    ]
    for arm in arms:
        start = _mean(rows, arm, 0)
        end = _mean(rows, arm, final)
        change = f"{(end - start) * 100:+.1f} points" if start is not None and end is not None else MISSING
        lines.append(f"| `{arm}` | {_percent(start)} | {_percent(end)} | {change} |")
    return lines


def hypotheses_table() -> list[str]:
    rows = _rows("hypotheses")
    if not rows:
        return ["Not decided yet."]
    lines = ["| id | claim | verdict |", "|---|---|---|"]
    for row in rows:
        lines.append(f"| {row.get('id')} | {row.get('claim')} | **{row.get('verdict')}** |")
    return lines


FILES: tuple[tuple[str, str], ...] = (
    ("curve.jsonl", "held-out and training accuracy per seed, arm and round"),
    ("round_zero.json", "the frozen-graph baseline before any judging"),
    ("plain_store.json", "the document-only baseline, tuned to its own best score"),
    ("mechanisms.json", "one mechanism per arm, against full and against the random controls"),
    ("non_regression.json", "newly fixed, newly broken and net per round, each break traced to receipts"),
    ("quarantine.json", "quarantine precision and recall against the planted faults"),
    ("hypotheses.json", "H1-H5 with the rule each was decided by"),
    ("run_manifest.json", "commit, HydraDB image digest, config hash, seeds, and every file's sha256"),
    ("load.json", "loading G0 into HydraDB, and that a re-load adds nothing"),
    ("latency.json", "p50/p95/p99, QPS and errors by code under concurrent clients"),
)


def files_table() -> list[str]:
    lines = ["| file | what it is | sha256 (first 16) |", "|---|---|---|"]
    for name, what in FILES:
        lines.append(f"| [`evidence/{name}`](evidence/{name}) | {what} | {_digest(name)} |")
    return lines


def block() -> str:
    rows = _curve_rows()
    plain = _rows("plain_store")
    plain_mean = sum(float(str(row["accuracy"])) for row in plain) / len(plain) if plain else None
    parts: list[str] = [
        "### Held-out accuracy by arm",
        "",
        *arms_table(rows),
        "",
        f"The document-only baseline (BM25 over the same corpus, no graph) scores {_percent(plain_mean)}, "
        "with its one hyperparameter tuned to its own best held-out score.",
        "",
        "### Preregistered hypotheses",
        "",
        *hypotheses_table(),
        "",
        "### Evidence files",
        "",
        *files_table(),
    ]
    return "\n".join(parts)


def write(path: Path = README) -> Path:
    text = path.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise ValueError(f"{path} has no numbers block to fill")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    path.write_text(f"{head}{START}\n{block()}\n{END}{tail}")
    return path


if __name__ == "__main__":
    print(f"filled {write()}")
