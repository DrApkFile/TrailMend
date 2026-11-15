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


CURVE_V2 = "curve_v2.jsonl"


def _curve_v2() -> Path:
    return evidence.EVIDENCE_DIR / CURVE_V2


def _curve_rows(path: Path | None = None) -> tuple[Mapping[str, object], ...]:
    found = path if path is not None else curve.CURVE
    if not found.exists():
        return ()
    return tuple(json.loads(line) for line in found.read_text(encoding="utf-8").splitlines() if line)


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


def hypotheses_table(name: str = "hypotheses") -> list[str]:
    rows = _rows(name)
    if not rows:
        return ["Not decided yet."]
    lines = ["| id | claim | verdict |", "|---|---|---|"]
    for row in rows:
        lines.append(f"| {row.get('id')} | {row.get('claim')} | **{row.get('verdict')}** |")
    return lines


FILES_V2: tuple[tuple[str, str], ...] = (
    ("curve_v2.jsonl", "run 2: held-out and training accuracy per seed, arm and round"),
    ("mechanisms_v2.json", "run 2: one row per arm, from round 0 to the last round"),
    ("paired_v2.json", "run 2: every held-out question counted as a pair against the frozen arm, with its p-value"),
    ("captured_share_v2.json", "run 2: what the full arm gained over what the oracle says was reachable"),
    ("oracle_v2.json", "run 2: the ceiling of each repair, measured by applying it perfectly"),
    ("changes_v2.json", "run 2: change counts per seed, arm and round, every control beside the full arm"),
    ("non_regression_v2.json", "run 2: newly fixed, newly broken and net per round, each break traced to receipts"),
    ("quarantine_v2.json", "run 2: quarantine precision and recall against the planted faults"),
    ("hypotheses_v2.json", "run 2: H1' to H8' with the rule each was decided by"),
    ("plain_store_v2.json", "run 2: the document-only baseline, re-tuned on v2 to its own best score"),
    ("fault_recoverability_v2.json", "run 2: where the truth behind each planted fault is, by fault kind"),
    ("run_manifest_v2.json", "run 2: commit, HydraDB digest, config hash, data version, seeds and every digest"),
)
FILES: tuple[tuple[str, str], ...] = (
    ("curve.jsonl", "held-out and training accuracy per seed, arm and round"),
    ("round_zero.json", "the frozen-graph baseline before any judging"),
    ("plain_store.json", "the document-only baseline, tuned to its own best score"),
    ("mechanisms.json", "one mechanism per arm, against full and against the random controls"),
    ("changes.json", "change counts per seed, arm and round, full and every control side by side"),
    ("non_regression.json", "newly fixed, newly broken and net per round, each break traced to receipts"),
    ("quarantine.json", "quarantine precision and recall against the planted faults"),
    ("hypotheses.json", "H1-H5 with the rule each was decided by"),
    ("anatomy.json", "run 1 diagnosed: every failing train question by what broke its path"),
    ("oracle.json", "run 1 diagnosed: the ceiling of each repair on run 1's data"),
    ("fault_recoverability.json", "run 1 diagnosed: whether the truth behind a planted fault exists anywhere"),
    ("run_manifest.json", "commit, HydraDB image digest, config hash, seeds, and every file's sha256"),
    ("load.json", "loading G0 into HydraDB, and that a re-load adds nothing"),
    ("latency.json", "p50/p95/p99, QPS and errors by code under concurrent clients"),
)


def files_table(files: Sequence[tuple[str, str]] = FILES) -> list[str]:
    lines = ["| file | what it is | sha256 (first 16) |", "|---|---|---|"]
    for name, what in files:
        lines.append(f"| [`evidence/{name}`](evidence/{name}) | {what} | {_digest(name)} |")
    return lines


def captured_table() -> list[str]:
    rows = _rows("captured_share_v2")
    if not rows:
        return ["Not measured yet."]
    lines = ["| seed | round 0 | last round | gained | reachable | captured |", "|---|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            f"| {row.get('seed')} | {_percent(float(str(row.get('round_0'))))} | "
            f"{_percent(float(str(row.get('round_n'))))} | {float(str(row.get('gained_points'))):+.1f} points | "
            f"{float(str(row.get('reachable_points'))):.1f} points | "
            f"{float(str(row.get('captured_share'))) * 100:.0f}% |"
        )
    return lines


def paired_table() -> list[str]:
    rows = [row for row in _rows("paired_v2") if row.get("reference") == "frozen"]
    if not rows:
        return ["Not measured yet."]
    lines = ["| seed | arm | gain over frozen | p (exact McNemar) |", "|---|---|---|---|"]
    for row in sorted(rows, key=lambda r: (str(r.get("arm")), int(str(r.get("seed"))))):
        lines.append(
            f"| {row.get('seed')} | `{row.get('arm')}` | {float(str(row.get('delta_points'))):+.1f} points | "
            f"{float(str(row.get('p_value'))):.4f} |"
        )
    return lines


def run_two() -> list[str]:
    rows = _curve_rows(_curve_v2())
    if not rows:
        return [
            "### Run 2",
            "",
            "Preregistered in [PRD §3.2](docs/PRD.md) and not yet run. Nothing is reported here until it is.",
        ]
    plain = _rows("plain_store_v2")
    plain_mean = sum(float(str(row["accuracy"])) for row in plain) / len(plain) if plain else None
    return [
        "### Run 2, on dataset v2",
        "",
        *arms_table(rows),
        "",
        f"The document-only baseline (BM25 over the same corpus, no graph) scores {_percent(plain_mean)}, "
        "with its one hyperparameter re-tuned on this data to its own best held-out score.",
        "",
        "Against the frozen graph, question by question on the same seed and split:",
        "",
        *paired_table(),
        "",
        "How much of the repairable damage the full arm repaired, with the denominator measured by an oracle on the "
        "same data:",
        "",
        *captured_table(),
        "",
        "#### Hypotheses, fixed before run 2 was built",
        "",
        *hypotheses_table("hypotheses_v2"),
    ]


def run_one() -> list[str]:
    rows = _curve_rows()
    plain = _rows("plain_store")
    plain_mean = sum(float(str(row["accuracy"])) for row in plain) / len(plain) if plain else None
    return [
        "### Run 1, which failed and stays published",
        "",
        "Its headline hypothesis asked for a lift larger than the spread between seeds and did not get one. It is "
        "kept here exactly as it was published, next to run 2. The two runs use different generated data, so only "
        "comparisons inside a run are claims. Why it failed is measured in "
        "[docs/RUN1_DIAGNOSIS.md](docs/RUN1_DIAGNOSIS.md).",
        "",
        *arms_table(rows),
        "",
        f"Document-only baseline on run 1's data: {_percent(plain_mean)}.",
        "",
        *hypotheses_table(),
    ]


def block() -> str:
    parts: list[str] = [
        *run_two(),
        "",
        *run_one(),
        "",
        "### Evidence files",
        "",
        "Run 2:",
        "",
        *files_table(FILES_V2),
        "",
        "Run 1, and the two files that describe the deployment both runs used:",
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
