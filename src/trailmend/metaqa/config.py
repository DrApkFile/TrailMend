import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trailmend.metaqa.files import MANIFEST
from trailmend.metaqa.sample import SamplePlan

METAQA_CONFIG = Path("config/metaqa.toml")
MEND_CONFIG = Path("config/mend.toml")


@dataclass(frozen=True, slots=True)
class MetaqaConfig:
    sample: SamplePlan
    result_limit: int
    rounds: int

    def __post_init__(self) -> None:
        if not 1 <= self.result_limit <= 500:
            raise ValueError("result_limit must be between 1 and 500")
        if not 1 <= self.rounds <= 50:
            raise ValueError("rounds must be between 1 and 50")


def _table(raw: dict[str, object], name: str, fields: tuple[str, ...]) -> dict[str, int]:
    section = raw.get(name)
    if not isinstance(section, dict):
        raise TypeError(f"{METAQA_CONFIG} has no [{name}] table")
    values = cast("dict[str, object]", section)
    if sorted(values) != sorted(fields):
        raise ValueError(f"{METAQA_CONFIG} [{name}] must hold exactly {sorted(fields)}")
    found: dict[str, int] = {}
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{METAQA_CONFIG} [{name}] {key} must be an integer")
        found[key] = value
    return found


def load_metaqa_config(path: Path = METAQA_CONFIG) -> MetaqaConfig:
    raw = tomllib.loads(path.read_text())
    sample = _table(raw, "sample", ("region_movies", "train", "held_out"))
    search = _table(raw, "search", ("result_limit",))
    run = _table(raw, "run", ("rounds",))
    return MetaqaConfig(
        SamplePlan(sample["region_movies"], sample["train"], sample["held_out"]),
        search["result_limit"],
        run["rounds"],
    )


def config_digest() -> str:
    joined = b"".join(path.read_bytes() for path in (MEND_CONFIG, METAQA_CONFIG, MANIFEST))
    return hashlib.sha256(joined).hexdigest()
