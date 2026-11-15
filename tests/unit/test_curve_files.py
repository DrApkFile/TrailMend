import json
from pathlib import Path

import pytest

from trailmend.data.faultmodel import V1, V2
from trailmend.eval import curve


def test_each_data_version_writes_its_own_curve_file() -> None:
    assert curve.path_for(V1) == curve.CURVE
    assert curve.path_for(V2) == curve.CURVE_V2
    assert curve.CURVE != curve.CURVE_V2


def test_an_unknown_data_version_has_no_curve_file() -> None:
    with pytest.raises(ValueError, match="no curve file"):
        curve.path_for("v3")


def test_a_run_two_row_cannot_land_in_run_ones_curve(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="belongs in"):
        curve.append({"data_version": V2, "arm": "full_v2"}, curve.CURVE)
    assert not (tmp_path / "unused.jsonl").exists()


def test_a_row_without_a_data_version_is_a_run_one_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "curve.jsonl"
    monkeypatch.setitem(curve.BY_VERSION, V1, path)
    curve.append({"arm": "full", "round": 0}, path)
    assert [json.loads(line)["arm"] for line in path.read_text(encoding="utf-8").splitlines()] == ["full"]


def test_run_ones_curve_carries_only_run_one_rows() -> None:
    rows = [json.loads(line) for line in curve.CURVE.read_text(encoding="utf-8").splitlines() if line]
    assert rows
    assert {row.get("data_version") for row in rows} == {None}
