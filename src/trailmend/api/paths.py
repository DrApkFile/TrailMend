from collections.abc import Sequence

from trailmend.api.models import Hop
from trailmend.api.state import Live
from trailmend.core.model import EdgeKey
from trailmend.graph.state import read_states


def hops_of(live: Live, paths: Sequence[Sequence[EdgeKey]]) -> tuple[tuple[Hop, ...], ...]:
    keys = sorted({hop for path in paths for hop in path})
    states = read_states(live.client, keys)
    return tuple(
        tuple(
            Hop(
                src=hop.src,
                src_name=live.name_of(hop.src),
                rel_type=hop.rel_type,
                dst=hop.dst,
                dst_name=live.name_of(hop.dst),
                cost=states[hop].cost if hop in states else 0.0,
            )
            for hop in path
        )
        for path in paths
    )


def hop_of(live: Live, edge: EdgeKey, cost: float) -> Hop:
    return Hop(
        src=edge.src,
        src_name=live.name_of(edge.src),
        rel_type=edge.rel_type,
        dst=edge.dst,
        dst_name=live.name_of(edge.dst),
        cost=cost,
    )
