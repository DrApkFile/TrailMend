import json
from pathlib import Path

import pytest

from trailmend.eval import curve, evidence, report


def _curve_row(arm: str, seed: int, round_index: int, accuracy: float) -> str:
    return json.dumps(
        {
            "arm": arm,
            "seed": seed,
            "round": round_index,
            "held_out": {"accuracy": accuracy, "correct": 1, "n": 2},
            "train": None,
        }
    )


@pytest.fixture
def recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "evidence"
    directory.mkdir()
    (directory / "curve.jsonl").write_text(
        "\n".join(
            [
                _curve_row("full", 1, 0, 0.80),
                _curve_row("full", 7, 0, 0.70),
                _curve_row("full", 1, 1, 0.90),
                _curve_row("full", 7, 1, 0.80),
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(evidence, "EVIDENCE_DIR", directory)
    monkeypatch.setattr(curve, "CURVE", directory / "curve.jsonl")
    monkeypatch.setattr(curve, "CURVE_V2", directory / "curve_v2.jsonl")
    return directory


def test_the_block_averages_an_arm_over_the_seeds_that_recorded_it(recorded: Path) -> None:
    assert "| `full` | 75.0% | 85.0% | +10.0 points |" in report.block()


def test_an_evidence_file_that_was_never_written_is_shown_as_not_measured(recorded: Path) -> None:
    block = report.block()
    row = "| [`evidence/hypotheses.json`](evidence/hypotheses.json) |"
    assert f"{row} H1-H5 with the rule each was decided by | {report.MISSING} |" in block
    assert "Not decided yet." in block


def test_an_evidence_file_is_shown_with_the_digest_of_what_is_on_disk(recorded: Path) -> None:
    path = recorded / "hypotheses.json"
    path.write_text(
        json.dumps({"rows": [{"id": "H1", "claim": "the mend beats frozen", "verdict": "FAIL"}]}),
        encoding="utf-8",
    )
    block = report.block()
    assert f"`{evidence.digest(path)[:16]}…`" in block
    assert "| H1 | the mend beats frozen | **FAIL** |" in block


def test_a_readme_without_the_markers_refuses_to_be_filled(recorded: Path, tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# TrailMend\n\nno markers here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no numbers block"):
        report.write(readme)
    assert readme.read_text(encoding="utf-8") == "# TrailMend\n\nno markers here\n"


def test_filling_replaces_only_what_is_between_the_markers(recorded: Path, tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        f"# TrailMend\n\nbefore\n\n{report.START}\nstale\n{report.END}\n\nafter\n",
        encoding="utf-8",
    )
    report.write(readme)
    text = readme.read_text(encoding="utf-8")
    assert "before" in text
    assert "after" in text
    assert "stale" not in text
    assert "| `full` | 75.0% | 85.0% | +10.0 points |" in text


def test_the_block_reads_the_curve_it_is_pointed_at_not_the_one_imported(recorded: Path) -> None:
    (recorded / "curve_v2.jsonl").write_text(
        "\n".join([_curve_row("full_v2", 1, 0, 0.60), _curve_row("full_v2", 1, 1, 0.75)]),
        encoding="utf-8",
    )
    block = report.block()
    assert "| `full_v2` | 60.0% | 75.0% | +15.0 points |" in block
    assert "| `full` | 75.0% | 85.0% | +10.0 points |" in block
    assert "not yet run" not in block
