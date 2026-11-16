from pathlib import Path

import pytest

from trailmend.eval import headline, report


def test_the_headline_shows_a_dash_for_every_number_it_has_no_file_for(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(headline, "FACTS", tmp_path / "missing.json")
    monkeypatch.setattr(headline, "SUMMARY_V4", tmp_path / "missing_v4.json")
    for _, before, after, _ in headline.rows():
        assert before == headline.DASH
        assert after == headline.DASH


def test_a_front_page_without_headline_markers_refuses_to_be_filled(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# TrailMend\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no headline block"):
        report.write_front(readme)
    assert readme.read_text(encoding="utf-8") == "# TrailMend\n"


def test_filling_the_headline_replaces_only_what_is_between_its_markers(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(f"before\n{headline.START}\nstale\n{headline.END}\nafter\n", encoding="utf-8")
    report.write_front(readme)
    text = readme.read_text(encoding="utf-8")
    assert text.startswith(f"before\n{headline.START}\n| result |")
    assert text.endswith(f"{headline.END}\nafter\n")
    assert "stale" not in text
