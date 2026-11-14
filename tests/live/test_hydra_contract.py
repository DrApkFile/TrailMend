import itertools

import pytest

from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.graph.values import PathValue

pytestmark = pytest.mark.hydra
_ids = itertools.count(7_100_000_000_000_000_000 + (__import__("os").getpid() % 1000) * 1_000_000)


def _diamond(hydra: HydraClient, cost_top: float, cost_bottom: float) -> tuple[int, int, int, int]:
    s, top, bottom, t = (next(_ids) for _ in range(4))
    hydra.run(q.upsert_nodes("Probe"), {"rows": [{"id": n, "name": str(n)} for n in (s, top, bottom, t)]})
    rows = [
        {"src": s, "dst": top, "eid": next(_ids), "cost": cost_top, "confirms": 0, "blames": 0, "recent": ""},
        {"src": top, "dst": t, "eid": next(_ids), "cost": cost_top, "confirms": 0, "blames": 0, "recent": ""},
        {"src": s, "dst": bottom, "eid": next(_ids), "cost": cost_bottom, "confirms": 0, "blames": 0, "recent": ""},
        {"src": bottom, "dst": t, "eid": next(_ids), "cost": cost_bottom, "confirms": 0, "blames": 0, "recent": ""},
    ]
    hydra.run(q.upsert_edges("Probe", "R", "Probe"), {"rows": rows})
    return s, top, bottom, t


def _best_route(hydra: HydraClient, s: int, t: int) -> tuple[int, ...]:
    result = hydra.run(q.weighted_path_between(["R"], 3), {"src": s, "dst": t})
    assert len(result.rows) == 1
    path = result.rows[0][0]
    assert isinstance(path, PathValue)
    return path.node_ids


def test_a01_the_graph_accepts_writes_and_reads_them_back(hydra: HydraClient) -> None:
    hydra.require_writable()


def test_weighted_search_takes_the_cheaper_route_and_flips_when_cost_changes(hydra: HydraClient) -> None:
    s, top, bottom, t = _diamond(hydra, 1.4, 1.2)
    assert _best_route(hydra, s, t) == (s, bottom, t)
    hydra.run(
        q.set_edge_counters("R"), {"src": s, "dst": bottom, "cost": 9.0, "confirms": 0, "blames": 3, "recent": "BBB"}
    )
    assert _best_route(hydra, s, t) == (s, top, t)


def test_inv4_a_quarantined_edge_is_never_used_by_search(hydra: HydraClient) -> None:
    s, top, bottom, t = _diamond(hydra, 5.0, 1.0)
    copy, delete = q.move_edge("R", q.quarantine_type("R"), "Probe", "Probe")
    hydra.run(
        copy,
        {
            "rows": [
                {"src": s, "dst": bottom, "eid": next(_ids), "cost": 1.0, "confirms": 0, "blames": 4, "recent": "BBBB"}
            ]
        },
    )
    hydra.run(delete, {"src": s, "dst": bottom})
    assert _best_route(hydra, s, t) == (s, top, t)
    moved = hydra.run(q.read_edge("Q_R"), {"src": s, "dst": bottom})
    assert moved.rows == ((1.0, 0, 4, "BBBB", None),)
