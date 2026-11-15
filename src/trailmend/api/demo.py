import logging

from trailmend.api.state import Live
from trailmend.core.receipts import ResetReceipt, make_reset_receipt
from trailmend.errors import TrailMendError
from trailmend.graph.loader import count_graph
from trailmend.graph.reset import ResetReport, reset_to_ingested

logger = logging.getLogger("trailmend.api")


def node_count(live: Live) -> int:
    nodes, _ = count_graph(live.client, live.built.graph)
    return sum(nodes.values())


def restore(live: Live) -> tuple[ResetReport, ResetReceipt]:
    pool = tuple((e.src, e.rel_type.value, e.dst) for e in live.built.ingested.pool)
    report = reset_to_ingested(live.client, live.built.graph, pool, live.built.support)
    restored: dict[str, object] = {
        "quarantines_cleared": report.quarantines_cleared,
        "shortcuts_cleared": report.shortcuts_cleared,
        "pool_edges_withheld": report.pool_edges_withheld,
        "edges_pruned": report.edges_pruned,
        "rounds_discarded": live.rounds_run,
        "demo_seed": live.settings.demo_seed,
    }
    receipt = make_reset_receipt(live.settings.live_run_id, live.rounds_run, len(live.journal.lines()), restored)
    live.journal.append_reset(receipt)
    live.rounds_run = 0
    return report, receipt


def load_if_empty(live: Live) -> ResetReceipt | None:
    try:
        if node_count(live) > 0:
            return None
        _, receipt = restore(live)
    except (TrailMendError, OSError, ValueError):
        logger.exception("the demo graph is empty and could not be loaded; /v1/ask will answer unreachable")
        return None
    logger.info("the demo graph was empty, so G0 was loaded under receipt %s", receipt.receipt_id)
    return receipt
