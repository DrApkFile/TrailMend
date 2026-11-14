import tomllib
from pathlib import Path
from typing import cast

from trailmend.core.model import MendConfig

_FIELDS: tuple[str, ...] = (
    "eta",
    "cost_floor",
    "cost_ceiling",
    "window",
    "quarantine_min_blames",
    "quarantine_blame_share",
    "quarantine_confirm_ceiling",
    "promote_min_questions",
)


def load_mend_config(path: Path) -> MendConfig:
    raw = tomllib.loads(path.read_text()).get("mend")
    if not isinstance(raw, dict):
        raise TypeError(f"{path} has no [mend] table")
    section = cast("dict[str, object]", raw)
    unknown = sorted(set(section) - set(_FIELDS))
    missing = sorted(set(_FIELDS) - set(section))
    if unknown or missing:
        raise ValueError(f"{path}: unknown={unknown} missing={missing}")
    return MendConfig(**section)  # pyright: ignore[reportArgumentType]
