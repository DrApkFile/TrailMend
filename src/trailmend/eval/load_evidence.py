import sys
from collections.abc import Mapping

from trailmend.data import dataset
from trailmend.eval import evidence, target
from trailmend.eval.session import client_from_settings
from trailmend.graph.loader import count_graph, load
from trailmend.settings import load_settings

DESIGN = (
    "For each seed: build the generated Northwind dataset, count the store, write G0 into HydraDB with batch "
    "upserts (<=1000 rows per batch, every edge cost=1.0), count again, write the identical batches a second "
    "time, count again. A re-load is idempotent when the second write adds nothing, so "
    "nodes_added_by_reload and edges_added_by_reload are both 0. The *_counts fields are whole-store counts by "
    "label and relationship type, so they include anything else already in the graph, including other seeds; "
    "only the deltas are about this seed. Times are wall-clock seconds for the write phase alone."
)


def _total(counts: Mapping[str, int]) -> int:
    return sum(counts.values())


def main(seeds: tuple[int, ...]) -> int:
    rows: list[dict[str, object]] = []
    with client_from_settings() as client:
        client.require_writable()
        for seed in seeds:
            built = dataset.build(seed)
            before_nodes, before_edges = count_graph(client, built.graph)
            first = load(client, built.graph)
            second = load(client, built.graph)
            added_by_reload_nodes = _total(second.node_counts) - _total(first.node_counts)
            added_by_reload_edges = _total(second.edge_counts) - _total(first.edge_counts)
            rows.append(
                {
                    "dataset": "northwind_generated",
                    "seed": seed,
                    "nodes_written": first.nodes_written,
                    "edges_written": first.edges_written,
                    "batches": first.batches,
                    "first_load_seconds": round(first.seconds, 3),
                    "reload_seconds": round(second.seconds, 3),
                    "nodes_added_by_first_load": _total(first.node_counts) - _total(before_nodes),
                    "edges_added_by_first_load": _total(first.edge_counts) - _total(before_edges),
                    "nodes_added_by_reload": added_by_reload_nodes,
                    "edges_added_by_reload": added_by_reload_edges,
                    "reload_is_idempotent": added_by_reload_nodes == 0 and added_by_reload_edges == 0,
                    "store_node_counts_after": dict(second.node_counts),
                    "store_edge_counts_after": dict(second.edge_counts),
                }
            )
    path = evidence.write(
        evidence.make("load", DESIGN, rows, measured_on=target.describe(str(load_settings().hydra_url)))
    )
    print(f"wrote {path} sha256={evidence.digest(path)}")
    return 0 if all(bool(row["reload_is_idempotent"]) for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main(tuple(int(a) for a in sys.argv[1:]) or (1, 7, 42)))
