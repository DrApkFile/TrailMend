from pathlib import Path

import pytest

from trailmend.core.config import load_mend_config


def test_the_committed_mend_config_loads_and_validates() -> None:
    cfg = load_mend_config(Path("config/mend.toml"))
    assert cfg.quarantine_min_blames <= cfg.window


def test_an_unknown_key_in_the_mend_config_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "mend.toml"
    bad.write_text(Path("config/mend.toml").read_text().replace("eta = 0.35", "eta = 0.35\nsurprise = 1"))
    with pytest.raises(ValueError, match="unknown=\\['surprise'\\]"):
        load_mend_config(bad)
