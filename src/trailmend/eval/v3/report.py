import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import fmean
from typing import cast

from trailmend.eval import evidence
from trailmend.eval.v3 import files
from trailmend.eval.v3.analyse import METAQA_REASON, complete

START = "<!-- run3:start -->"
END = "<!-- run3:end -->"
SUMMARY = Path("evidence/summary_v3.json")


def payload() -> Mapping[str, object] | None:
    if not SUMMARY.exists():
        return None
    return cast("Mapping[str, object]", json.loads(SUMMARY.read_text())["rows"][0])


def generate() -> None:
    rows: list[dict[str, object]] = [json.loads(line) for line in files.CURVE.read_text().splitlines() if line]
    run_id = complete(rows)
    hypotheses: list[dict[str, object]] = json.loads(Path("evidence/hypotheses_v3.json").read_text())["rows"]
    arms: list[dict[str, object]] = []
    for arm in files.ARMS:
        metrics: dict[str, object] = {"arm": arm}
        for round_index in (0, files.ROUNDS):
            picked = [row for row in rows if row["arm"] == arm and row["round"] == round_index]
            held = [cast("Mapping[str, object]", row["held_out"]) for row in picked]
            for key in ("accuracy", "wrong", "refused", "unreachable"):
                metrics[f"{key}_{round_index}"] = fmean(
                    float(str(scores[key])) / (1 if key == "accuracy" else float(str(scores["n"]))) for scores in held
                )
            metrics[f"coverage_{round_index}"] = fmean(float(str(row["coverage"])) for row in picked)
            metrics[f"low_confidence_{round_index}"] = fmean(
                float(str(row["low_confidence"])) / float(str(cast("Mapping[str, object]", row["held_out"])["n"]))
                for row in picked
            )
        arms.append(metrics)
    row: dict[str, object] = {
        "dataset": "northwind_generated",
        "data_version": "v2",
        "classification": "measured",
        "run_id": run_id,
        "config_sha256": files.digest(),
        "seeds": list(files.SEEDS),
        "rounds": files.ROUNDS,
        "aggregation": "unweighted mean of seed-level rates; denominator includes every held-out question",
        "verdicts": {str(h["id"]): h["verdict"] for h in hypotheses if h["dataset"] == "northwind_generated"},
        "arms": arms,
        "metaqa": {"classification": "not_run", "reason": METAQA_REASON},
        "limitation": "R3 is a weak non-superiority check; its pass does not establish equivalence or improvement.",
    }
    evidence.write(
        evidence.make("summary_v3", "Run 3 means from complete curves and preregistered verdicts; PRD 3.4.", [row])
    )


def section() -> list[str]:
    summary = payload()
    if summary is None:
        return []
    arms = cast("Sequence[Mapping[str, object]]", summary["arms"])
    verdicts = cast("Mapping[str, object]", summary["verdicts"])
    lines = [
        START,
        "### Run 3: abstain instead of guessing",
        "",
        f"Generated Northwind v2, run `{summary['run_id']}`, seeds {summary['seeds']}; "
        f"{summary['rounds']} rounds. Training-only cutoffs were frozen before held-out scoring. "
        "The table shows means across seeds; refusals count as neither correct nor wrong, "
        "and remain in the denominator.",
        "",
        "| arm | accuracy r0 → r5 | wrong/n r0 → r5 | refused/n r0 → r5 | coverage r0 → r5 |",
        "|---|---|---|---|---|",
    ]
    for arm in arms:
        cells = [f"`{arm['arm']}`"]
        for key in ("accuracy", "wrong", "refused", "coverage"):
            cells.append(f"{100 * float(str(arm[f'{key}_0'])):.1f}% → {100 * float(str(arm[f'{key}_5'])):.1f}%")
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "Preregistered verdicts: " + "; ".join(f"**{key} {value}**" for key, value in verdicts.items()) + ".",
        "R1 tests the wrong-answer reduction; R2 limits accuracy lost against the concurrent non-abstaining full Mend. "
        "This variant did not meet those safeguards. R3 only checks that frozen is not significantly better; "
        "it is not an equivalence or improvement claim. H6' and M4 remain failed in their original experiments.",
        "",
        "**MetaQA run 3: not_run.** " + METAQA_REASON.removeprefix("not_run: "),
        "",
        "Sources: [curve](evidence/curve_v3_northwind.jsonl), [training calibration](evidence/calibration_v3.json), "
        "[hypotheses](evidence/hypotheses_v3.json), [paired questions](evidence/paired_v3.json), "
        "[summary](evidence/summary_v3.json), [manifest and receipts](evidence/run_manifest_v3.json).",
        END,
    ]
    return lines


def write_readme(path: Path = Path("README.md")) -> None:
    block = "\n".join(section())
    text = path.read_text()
    if START in text:
        before, rest = text.split(START, 1)
        _, after = rest.split(END, 1)
        text = before + block + after
    else:
        text = text.replace("<!-- numbers:end -->", block + "\n<!-- numbers:end -->")
    path.write_text(text)


if __name__ == "__main__":
    generate()
    write_readme()
