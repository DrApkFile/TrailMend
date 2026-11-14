from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from trailmend.core.model import EdgeKey
from trailmend.data import dataset
from trailmend.eval.regression import as_int, edge_of, receipts_of
from trailmend.loop.journal import RUNS_DIR


@dataclass(frozen=True, slots=True)
class FaultEdges:
    wrong: frozenset[EdgeKey]
    added_by_faults: frozenset[EdgeKey]
    withheld: frozenset[EdgeKey]
    truth: frozenset[EdgeKey]


def fault_edges(seed: int) -> FaultEdges:
    built = dataset.build(seed)
    faults = built.ingested.faults
    wrong = frozenset(EdgeKey(f.src, f.rel_type.value, f.wrong_dst) for f in faults.wrong_edges)
    added = frozenset(EdgeKey(e.src, e.rel_type.value, e.dst) for e in faults.added_edges())
    withheld = frozenset(EdgeKey(e.src, e.rel_type.value, e.dst) for e in built.ingested.pool)
    truth = frozenset(EdgeKey(e.src, e.rel_type.value, e.dst) for e in built.truth.edges)
    return FaultEdges(wrong, added | wrong, withheld, truth)


def _of_kind(receipts: Sequence[Mapping[str, object]], kind: str) -> tuple[tuple[int, EdgeKey], ...]:
    return tuple((as_int(r["round"], "round"), edge_of(r)) for r in receipts if str(r["kind"]) == kind)


def report(seed: int, arm: str, run_id: str, root: Path = RUNS_DIR) -> dict[str, object]:
    facts = fault_edges(seed)
    receipts = receipts_of(run_id, root)
    quarantined = _of_kind(receipts, "quarantine")
    ingested = _of_kind(receipts, "gapfill")
    edges = tuple(dict.fromkeys(edge for _, edge in quarantined))
    hits = tuple(edge for edge in edges if edge in facts.added_by_faults)
    on_truth = tuple(edge for edge in edges if edge in facts.truth)
    filled = tuple(dict.fromkeys(edge for _, edge in ingested))
    return {
        "seed": seed,
        "arm": arm,
        "run_id": run_id,
        "planted_wrong_edges": len(facts.wrong),
        "fault_introduced_edges": len(facts.added_by_faults),
        "quarantined": len(edges),
        "quarantined_that_were_planted": len(hits),
        "quarantined_that_are_in_the_truth_graph": len(on_truth),
        "precision": round(len(hits) / len(edges), 4) if edges else None,
        "recall_on_planted_wrong_edges": round(len(tuple(e for e in hits if e in facts.wrong)) / len(facts.wrong), 4)
        if facts.wrong
        else None,
        "false_quarantine_rate": round(len(on_truth) / len(edges), 4) if edges else None,
        "gaps_filled": len(filled),
        "gaps_filled_that_were_withheld_truth": len(tuple(e for e in filled if e in facts.withheld)),
        "spurious_ingests": len(tuple(e for e in filled if e not in facts.truth)),
    }
