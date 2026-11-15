from collections.abc import Sequence

from trailmend.core.model import EdgeKey, SearchConfig
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.search.answer import COST_PLACES, score_paths


def cheapest_path_to(
    client: HydraClient, seed_id: int, target_id: int, rel_types: Sequence[str], config: SearchConfig
) -> tuple[EdgeKey, ...] | None:
    result = client.run(
        q.weighted_path_between(rel_types, config.max_len, weighted=config.weighted),
        {"src": seed_id, "dst": target_id},
    )
    scored = [path for path in score_paths(result.rows) if path.terminal == target_id]
    if not scored:
        return None
    best = min(round(path.cost, COST_PLACES) for path in scored)
    for path in scored:
        if round(path.cost, COST_PLACES) == best:
            return path.edges
    return None
