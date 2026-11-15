from collections.abc import Mapping
from dataclasses import dataclass

from trailmend.data.model import TruthGraph
from trailmend.data.qtemplates import SHORTCUT_TYPES
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.graph.loader import load
from trailmend.graph.schema import NORTHWIND_REL_TYPES
from trailmend.graph.state import list_edge_keys


@dataclass(frozen=True, slots=True)
class ResetReport:
    quarantines_cleared: int
    shortcuts_cleared: int
    pool_edges_withheld: int
    edges_pruned: int


def _clear(client: HydraClient, rel_type: str) -> int:
    keys = list_edge_keys(client, rel_type)
    for key in keys:
        client.run(q.delete_edge(rel_type), {"src": key.src, "dst": key.dst})
    return len(keys)


def _prune(client: HydraClient, graph: TruthGraph) -> int:
    wanted = {(edge.src, edge.rel_type.value, edge.dst) for edge in graph.edges}
    pruned = 0
    for rel_type in NORTHWIND_REL_TYPES:
        for key in list_edge_keys(client, rel_type.value):
            if (key.src, rel_type.value, key.dst) in wanted:
                continue
            client.run(q.delete_edge(rel_type.value), {"src": key.src, "dst": key.dst})
            pruned += 1
    return pruned


def reset_to_ingested(
    client: HydraClient, graph: TruthGraph, pool: tuple[tuple[int, str, int], ...], support: Mapping[int, int]
) -> ResetReport:
    quarantines = sum(_clear(client, q.quarantine_type(rel_type.value)) for rel_type in NORTHWIND_REL_TYPES)
    shortcuts = 0
    for shortcut_type in SHORTCUT_TYPES:
        shortcuts += _clear(client, shortcut_type)
        shortcuts += _clear(client, q.quarantine_type(shortcut_type))
    pruned = _prune(client, graph)
    load(client, graph, support)
    return ResetReport(quarantines, shortcuts, len(pool), pruned)
