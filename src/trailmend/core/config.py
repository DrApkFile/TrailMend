import hashlib
import tomllib
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class RunConfig:
    rounds: int
    plain_store_top_k: int

    def __post_init__(self) -> None:
        if not 1 <= self.rounds <= 50:
            raise ValueError("rounds must be between 1 and 50")
        if not 1 <= self.plain_store_top_k <= 500:
            raise ValueError("plain_store_top_k must be between 1 and 500")


_RUN_FIELDS: tuple[str, ...] = ("rounds", "plain_store_top_k")


def load_run_config(path: Path) -> RunConfig:
    raw = tomllib.loads(path.read_text()).get("run")
    if not isinstance(raw, dict):
        raise TypeError(f"{path} has no [run] table")
    section = cast("dict[str, object]", raw)
    unknown = sorted(set(section) - set(_RUN_FIELDS))
    missing = sorted(set(_RUN_FIELDS) - set(section))
    if unknown or missing:
        raise ValueError(f"{path}: unknown={unknown} missing={missing}")
    return RunConfig(**section)  # pyright: ignore[reportArgumentType]


def config_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
