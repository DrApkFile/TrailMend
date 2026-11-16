import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import fmean
from typing import cast

from trailmend.eval import evidence
from trailmend.eval.v4 import files
from trailmend.eval.v4.analyse import METAQA_REASON, complete

START = "<!-- run4:start -->"
END = "<!-- run4:end -->"
SUMMARY = Path("evidence/summary_v4.json")


def payload() -> Mapping[str, object] | None:
    if not SUMMARY.exists():
        return None
    return cast("Mapping[str, object]", json.loads(SUMMARY.read_text())["rows"][0])


def generate() -> None:
    rows: list[dict[str, object]] = [json.loads(line) for line in files.CURVE.read_text().splitlines() if line]
    run_id = complete(rows)
    hypotheses: list[dict[str, object]] = json.loads(Path("evidence/hypotheses_v4.json").read_text())["rows"]
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
        "shared_trajectory": {"full_v4": "full_v4_no_gate"},
        "training_feedback": "ungated_internal_audit",
        "metaqa": {"classification": "not_run", "reason": METAQA_REASON},
        "limitation": "R3 is a weak non-superiority check; its pass does not establish equivalence or improvement.",
    }
    evidence.write(
        evidence.make("summary_v4", "Run 4 means from complete curves and preregistered verdicts; PRD 3.5.", [row])
    )


def section() -> list[str]:
    summary = payload()
    if summary is None:
        return []
    arms = cast("Sequence[Mapping[str, object]]", summary["arms"])
    verdicts = cast("Mapping[str, object]", summary["verdicts"])
    lines = [
        START,
        "### Run 4: preserve feedback and complete answer sets",
        "",
        f"Generated Northwind v2, run `{summary['run_id']}`, seeds {summary['seeds']}; "
        f"{summary['rounds']} rounds. Training-only cutoffs were frozen before held-out scoring. "
        "The table shows means across seeds; full_v4 and full_v4_no_gate share exactly the same learner trajectory. "
        "They are paired answer policies, not independent training interventions. "
        "Refusals count as neither correct nor wrong, "
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
        "R1 tests the wrong-answer reduction; R2 limits accuracy lost against both the matched ungated hybrid "
        "and the independent weighted full Mend. "
        "Each preregistered verdict is reported as measured. R3 only checks that frozen is not significantly better; "
        "it is not an equivalence or improvement claim. "
        "Run 3 R1/R2, H6' and M4 remain failed in their original experiments.",
        "",
        "**MetaQA run 4: not_run.** " + METAQA_REASON.removeprefix("not_run: "),
        "",
        "Sources: [curve](evidence/curve_v4_northwind.jsonl), [training calibration](evidence/calibration_v4.json), "
        "[hypotheses](evidence/hypotheses_v4.json), [paired questions](evidence/paired_v4.json), "
        "[summary](evidence/summary_v4.json), [manifest and receipts](evidence/run_manifest_v4.json).",
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
