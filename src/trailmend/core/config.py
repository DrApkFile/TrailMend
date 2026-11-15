import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trailmend.core.model import GapfillRule, MendConfig, SearchConfig

V2_RULE = "v2"
V1_RULE = "v1"

_FIELDS: tuple[str, ...] = (
    "eta",
    "eta_confirm",
    "cost_floor",
    "cost_ceiling",
    "window",
    "quarantine_min_blames",
    "quarantine_blame_share",
    "quarantine_confirm_ceiling",
    "promote_min_questions",
)


_RUN1_FIELDS: tuple[str, ...] = ("eta", "cost_floor")


def _table(path: Path, name: str, fields: tuple[str, ...]) -> dict[str, object]:
    raw = tomllib.loads(path.read_text()).get(name)
    if not isinstance(raw, dict):
        raise TypeError(f"{path} has no [{name}] table")
    section = cast("dict[str, object]", raw)
    unknown = sorted(set(section) - set(fields))
    missing = sorted(set(fields) - set(section))
    if unknown or missing:
        raise ValueError(f"{path} [{name}]: unknown={unknown} missing={missing}")
    return section


def load_mend_config(path: Path, rule: str = V2_RULE) -> MendConfig:
    section = _table(path, "mend", _FIELDS)
    if rule == V2_RULE:
        return MendConfig(**section)  # pyright: ignore[reportArgumentType]
    if rule != V1_RULE:
        raise ValueError(f"unknown update rule {rule!r}")
    prior = _table(path, "run1_rule", _RUN1_FIELDS)
    return MendConfig(**(section | prior | {"eta_confirm": None}))  # pyright: ignore[reportArgumentType]


_GAPFILL_FIELDS: tuple[str, ...] = ("waves", "on_wrong")


def load_gapfill_rule(path: Path) -> GapfillRule:
    return GapfillRule(**_table(path, "gapfill", _GAPFILL_FIELDS))  # pyright: ignore[reportArgumentType]


_SEARCH_FIELDS: tuple[str, ...] = ("max_len", "result_limit")


def load_search_config(path: Path) -> SearchConfig:
    return SearchConfig(**_table(path, "search", _SEARCH_FIELDS))  # pyright: ignore[reportArgumentType]


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
    return RunConfig(**_table(path, "run", _RUN_FIELDS))  # pyright: ignore[reportArgumentType]


def config_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
