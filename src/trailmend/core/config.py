import tomllib
from pathlib import Path
from typing import cast

from trailmend.core.model import MendConfig, SearchConfig

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


_SEARCH_FIELDS: tuple[str, ...] = ("max_len", "result_limit")


def load_search_config(path: Path) -> SearchConfig:
    raw = tomllib.loads(path.read_text()).get("search")
    if not isinstance(raw, dict):
        raise TypeError(f"{path} has no [search] table")
    section = cast("dict[str, object]", raw)
    unknown = sorted(set(section) - set(_SEARCH_FIELDS))
    missing = sorted(set(_SEARCH_FIELDS) - set(section))
    if unknown or missing:
        raise ValueError(f"{path}: unknown={unknown} missing={missing}")
    return SearchConfig(**section)  # pyright: ignore[reportArgumentType]
