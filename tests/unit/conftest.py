import pytest

from trailmend.core.model import EdgeKey, EdgeState, MendConfig


@pytest.fixture
def cfg() -> MendConfig:
    return MendConfig(
        eta=0.35,
        cost_floor=0.05,
        cost_ceiling=20.0,
        window=6,
        quarantine_min_blames=3,
        quarantine_blame_share=0.8,
        quarantine_confirm_ceiling=1,
        promote_min_questions=3,
    )


def edge(n: int, rel: str = "OWNED_BY") -> EdgeKey:
    return EdgeKey(n, rel, n + 1)


def fresh(n: int, rel: str = "OWNED_BY") -> EdgeState:
    return EdgeState(edge(n, rel), cost=1.0)
