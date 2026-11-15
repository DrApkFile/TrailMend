import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from trailmend.core.config import load_mend_config, load_search_config
from trailmend.core.model import MendConfig, SearchConfig
from trailmend.data import dataset
from trailmend.errors import ErrorCode, TrailMendError
from trailmend.graph.client import HydraClient
from trailmend.loop.journal import Journal
from trailmend.loop.ledger import Ledger
from trailmend.loop.tape import Tape
from trailmend.search.seed import EntityIndex, build_index
from trailmend.settings import Settings


@dataclass(slots=True)
class RateLimiter:
    per_minute: int
    seen: dict[str, deque[float]] = field(default_factory=lambda: cast("dict[str, deque[float]]", {}))

    def check(self, who: str, now: float) -> None:
        window = self.seen.setdefault(who, deque())
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.per_minute:
            raise TrailMendError(ErrorCode.RATE_LIMITED, f"{self.per_minute} asks a minute")
        window.append(now)


@dataclass(slots=True)
class Live:
    settings: Settings
    client: HydraClient
    built: dataset.Dataset
    index: EntityIndex
    mend: MendConfig
    search: SearchConfig
    journal: Journal
    ledger: Ledger
    tape: Tape
    limiter: RateLimiter
    rounds_run: int = 0

    @property
    def names(self) -> dict[int, str]:
        return {node.id: node.name for node in self.built.graph.nodes}

    def name_of(self, entity_id: int) -> str:
        return self.names.get(entity_id, str(entity_id))

    def close(self) -> None:
        self.client.close()


def build_live(settings: Settings) -> Live:
    config = Path(settings.mend_config_path)
    client = HydraClient(
        str(settings.hydra_url),
        settings.hydra_token.get_secret_value(),
        settings.hydra_graph_id,
        settings.hydra_cell_id,
        settings.hydra_timeout_s,
    )
    built = dataset.build(settings.demo_seed)
    return Live(
        settings,
        client,
        built,
        build_index(built.graph.nodes),
        load_mend_config(config),
        load_search_config(config),
        Journal.for_run(settings.live_run_id),
        Ledger.for_run(settings.live_run_id),
        Tape.for_run(settings.live_run_id),
        RateLimiter(settings.ask_rate_per_minute),
    )


def now() -> float:
    return time.monotonic()
