from dataclasses import dataclass

from trailmend.data.model import TruthGraph
from trailmend.data.qtemplates import SHORTCUT_TYPES
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.graph.loader import load
from trailmend.graph.schema import RelType
from trailmend.graph.state import list_edge_keys


@dataclass(frozen=True, slots=True)
class ResetReport:
    quarantines_cleared: int
    shortcuts_cleared: int
    pool_edges_withheld: int


def _clear(client: HydraClient, rel_type: str) -> int:
    keys = list_edge_keys(client, rel_type)
    for key in keys:
        client.run(q.delete_edge(rel_type), {"src": key.src, "dst": key.dst})
    return len(keys)


def reset_to_ingested(client: HydraClient, graph: TruthGraph, pool: tuple[tuple[int, str, int], ...]) -> ResetReport:
    quarantines = sum(_clear(client, q.quarantine_type(rel_type.value)) for rel_type in RelType)
    shortcuts = 0
    for shortcut_type in SHORTCUT_TYPES:
        shortcuts += _clear(client, shortcut_type)
        shortcuts += _clear(client, q.quarantine_type(shortcut_type))
    for src, rel_type, dst in pool:
        client.run(q.delete_edge(rel_type), {"src": src, "dst": dst})
    load(client, graph)
    return ResetReport(quarantines, shortcuts, len(pool))
