from collections import defaultdict
from dataclasses import dataclass, replace
from random import Random

from trailmend.data.faultmodel import (
    V1,
    AliasDuplicate,
    ConflatedPerson,
    EdgeDelta,
    FaultSet,
    Ingested,
    MissingEdge,
    WrongEdge,
    WrongKind,
    replay,
)
from trailmend.data.model import (
    Edge,
    Node,
    NodeFactory,
    TruthGraph,
    first_unused_name,
    make_edge,
    require_consistent,
)
from trailmend.graph.schema import NodeLabel, RelType

type EdgeIndex = dict[tuple[int, RelType, int], Edge]

SWAPPABLE: tuple[RelType, ...] = (RelType.OWNED_BY, RelType.ON_CALL)


@dataclass(frozen=True, slots=True)
class FaultPlan:
    wrong_edge_share: float = 0.08
    missing_edge_share: float = 0.06
    alias_duplicate_share: float = 0.05
    conflated_people: int = 1
    contradicted_share: float = 0.4
    recoverable_share: float = 0.3

    def __post_init__(self) -> None:
        for name in ("wrong_edge_share", "missing_edge_share", "alias_duplicate_share"):
            share = getattr(self, name)
            if not 0 <= share < 0.5:
                raise ValueError(f"{name} must be in [0, 0.5)")
        if self.conflated_people < 0:
            raise ValueError("conflated_people must not be negative")
        for name in ("contradicted_share", "recoverable_share"):
            share = getattr(self, name)
            if not 0 <= share <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.contradicted_share + self.recoverable_share > 1:
            raise ValueError("contradicted and recoverable shares must leave room for destroyed faults")


def wrong_kinds(rng: Random, count: int, plan: FaultPlan) -> list[WrongKind]:
    contradicted = round(count * plan.contradicted_share)
    recoverable = round(count * plan.recoverable_share)
    destroyed = count - contradicted - recoverable
    if destroyed < 0:
        raise ValueError("rounding the wrong-edge kinds left no destroyed faults")
    kinds = (
        [WrongKind.CONTRADICTED] * contradicted
        + [WrongKind.RECOVERABLE] * recoverable
        + [WrongKind.DESTROYED] * destroyed
    )
    rng.shuffle(kinds)
    return kinds


def _share(count: int, share: float) -> int:
    return max(1, round(count * share)) if share > 0 and count > 0 else 0


def _swap_targets(
    rng: Random, truth: TruthGraph, index: EdgeIndex, plan: FaultPlan, data_version: str
) -> tuple[list[WrongEdge], list[Edge]]:
    swappable = sorted(
        (e for e in truth.edges if e.rel_type in SWAPPABLE), key=lambda e: (e.rel_type.value, e.src, e.dst)
    )
    chosen = rng.sample(swappable, _share(len(swappable), plan.wrong_edge_share))
    ordered = sorted(chosen, key=lambda e: (e.rel_type.value, e.src, e.dst))
    kinds = [WrongKind.DESTROYED] * len(ordered) if data_version == V1 else wrong_kinds(rng, len(ordered), plan)
    by_id = truth.by_id
    faults: list[WrongEdge] = []
    withheld: list[Edge] = []
    for edge, kind in zip(ordered, kinds, strict=True):
        candidates = [n for n in truth.nodes_with_label(by_id[edge.dst].label) if n.id != edge.dst]
        wrong = rng.choice(candidates)
        replacement = make_edge(by_id[edge.src], edge.rel_type, wrong)
        index[(replacement.src, replacement.rel_type, replacement.dst)] = replacement
        removed: tuple[Edge, ...] = ()
        if kind is not WrongKind.CONTRADICTED:
            del index[(edge.src, edge.rel_type, edge.dst)]
            removed = (edge,)
        if kind is WrongKind.RECOVERABLE:
            withheld.append(edge)
        faults.append(WrongEdge(edge.rel_type, edge.src, edge.dst, wrong.id, EdgeDelta(removed, (replacement,)), kind))
    return faults, withheld


def _withhold(
    rng: Random, index: EdgeIndex, plan: FaultPlan, spent: set[tuple[int, RelType, int]]
) -> tuple[list[MissingEdge], list[Edge]]:
    present = sorted(
        (e for e in index.values() if (e.src, e.rel_type, e.dst) not in spent),
        key=lambda e: (e.rel_type.value, e.src, e.dst),
    )
    chosen = rng.sample(present, _share(len(present), plan.missing_edge_share))
    faults: list[MissingEdge] = []
    pool: list[Edge] = []
    for edge in sorted(chosen, key=lambda e: (e.rel_type.value, e.src, e.dst)):
        del index[(edge.src, edge.rel_type, edge.dst)]
        pool.append(edge)
        faults.append(MissingEdge(edge.rel_type, edge.src, edge.dst, EdgeDelta(removed=(edge,))))
    return faults, pool


def _duplicate_services(
    rng: Random, truth: TruthGraph, index: EdgeIndex, plan: FaultPlan
) -> tuple[list[AliasDuplicate], list[Node]]:
    services = truth.nodes_with_label(NodeLabel.SERVICE)
    chosen = rng.sample(list(services), _share(len(services), plan.alias_duplicate_share))
    incoming: dict[int, list[Edge]] = defaultdict(list)
    for edge in index.values():
        if edge.rel_type is RelType.ALERTS_ON:
            incoming[edge.dst].append(edge)
    faults: list[AliasDuplicate] = []
    added: list[Node] = []
    mint = NodeFactory(truth.seed)
    taken = {n.name for n in truth.nodes} | {a for n in truth.nodes for a in n.aliases}
    for service in sorted(chosen, key=lambda n: n.id):
        short, _, kind = service.name.partition("-")
        name = first_unused_name((f"{short}Svc", f"{short}{kind.title()}Svc", f"{service.name}Svc"), taken)
        alias = first_unused_name((f"{short} service", f"{short} {kind} service", f"{service.name} service"), taken)
        taken.update((name, alias))
        duplicate = mint.node(NodeLabel.SERVICE, f"{service.name}-alias", name, (alias,))
        alerts = sorted(incoming[service.id], key=lambda e: (e.src, e.dst))
        moved = alerts[: max(1, len(alerts) // 2)] if alerts else []
        removed: list[Edge] = []
        created: list[Edge] = []
        for edge in moved:
            replacement = make_edge(truth.node(edge.src), RelType.ALERTS_ON, duplicate)
            del index[(edge.src, edge.rel_type, edge.dst)]
            index[(replacement.src, replacement.rel_type, replacement.dst)] = replacement
            removed.append(edge)
            created.append(replacement)
        added.append(duplicate)
        faults.append(
            AliasDuplicate(service.id, duplicate.id, duplicate.name, EdgeDelta(tuple(removed), tuple(created)))
        )
    return faults, added


def _conflate_people(
    rng: Random, truth: TruthGraph, index: EdgeIndex, plan: FaultPlan, spent: set[int]
) -> tuple[list[ConflatedPerson], list[Node], dict[int, Node]]:
    people = sorted(truth.nodes_with_label(NodeLabel.PERSON), key=lambda n: n.id)
    faults: list[ConflatedPerson] = []
    removed_nodes: list[Node] = []
    rewritten: dict[int, Node] = {}
    for _ in range(plan.conflated_people):
        pair = rng.sample([p for p in people if p.id not in spent], 2)
        kept, absorbed = sorted(pair, key=lambda n: n.id)
        spent.update((kept.id, absorbed.id))
        removed: list[Edge] = []
        created: list[Edge] = []
        for edge in sorted(index.values(), key=lambda e: (e.rel_type.value, e.src, e.dst)):
            if absorbed.id not in (edge.src, edge.dst):
                continue
            src = kept if edge.src == absorbed.id else truth.node(edge.src)
            dst = kept if edge.dst == absorbed.id else truth.node(edge.dst)
            del index[(edge.src, edge.rel_type, edge.dst)]
            removed.append(edge)
            if src.id == dst.id:
                continue
            replacement = make_edge(src, edge.rel_type, dst)
            index[(replacement.src, replacement.rel_type, replacement.dst)] = replacement
            created.append(replacement)
        removed_nodes.append(absorbed)
        rewritten[kept.id] = replace(kept, aliases=(*kept.aliases, absorbed.name, *absorbed.aliases))
        faults.append(
            ConflatedPerson(kept.id, absorbed.id, kept.name, absorbed.name, EdgeDelta(tuple(removed), tuple(created)))
        )
    return faults, removed_nodes, rewritten


def inject(truth: TruthGraph, plan: FaultPlan | None = None, data_version: str = V1) -> Ingested:
    settings = plan or FaultPlan()
    rng = Random(truth.seed * 1_000_003 + 17)
    index: EdgeIndex = {(e.src, e.rel_type, e.dst): e for e in truth.edges}

    wrong, recoverable = _swap_targets(rng, truth, index, settings, data_version)
    touched_edges = {f.wrong_key for f in wrong} | {f.true_key for f in wrong}
    missing, pool = _withhold(rng, index, settings, touched_edges)
    pool = recoverable + pool
    duplicates, added_nodes = _duplicate_services(rng, truth, index, settings)
    touched_people = {f.src for f in wrong} | {f.wrong_dst for f in wrong} | {f.true_dst for f in wrong}
    touched_people |= {f.src for f in missing} | {f.dst for f in missing}
    conflations, removed_nodes, rewritten = _conflate_people(rng, truth, index, settings, touched_people)

    faults = FaultSet(truth.seed, tuple(wrong), tuple(missing), tuple(duplicates), tuple(conflations), data_version)
    gone = {n.id for n in removed_nodes}
    kept = tuple(rewritten.get(n.id, n) for n in truth.nodes if n.id not in gone)
    nodes = kept + tuple(added_nodes)
    edges = tuple(sorted(index.values(), key=lambda e: (e.rel_type.value, e.src, e.dst)))
    declared = replay(truth, faults)
    if set(edges) != set(declared):
        raise ValueError("G0 does not match the declared faults")
    require_consistent(nodes, edges)
    graph = TruthGraph(truth.seed, truth.company, nodes, edges)
    return Ingested(graph, tuple(pool), faults, tuple(added_nodes), tuple(removed_nodes))
