from collections.abc import Callable, Sequence
from dataclasses import asdict

from trailmend.core.model import EdgeKey
from trailmend.data.faultmodel import WrongKind
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.metaqa.answer import judge_all, score
from trailmend.metaqa.sample import MqQuestion
from trailmend.metaqa.store import load_facts
from trailmend.metaqa.world import Fact, World

REACHABLE_RUNG = "pool_ingested"
LADDER_DESIGN = (
    "Cumulative oracle ladder on MetaQA held-out questions, answered through HydraDB with the run's own search. "
    "Each rung adds one repair an oracle with the fault file could make and keeps the ones before it: g0 (nothing); "
    "contradicted_removed (every contradicted fault's stale triple deleted); recoverable_restored (every recoverable "
    "fault's wrong triple deleted and its true triple ingested); pool_ingested (every withheld triple ingested - the "
    "top of what reweighting, quarantine and gap-fill could reach); destroyed_removed (every destroyed fault's wrong "
    "triple deleted, which no mechanism can turn into a right answer). Costs come from the same ingest rule."
)


def _delete(client: HydraClient, keys: Sequence[EdgeKey]) -> int:
    for key in keys:
        client.run(q.delete_edge(key.rel_type), {"src": key.src, "dst": key.dst})
    return len(keys)


def _wrong_edges(world: World, kind: WrongKind) -> list[EdgeKey]:
    return [key for fault in world.faults_of_kind(kind) for key in world.edges_of(fault.wrong)]


def ladder(
    client: HydraClient, world: World, held_out: Sequence[MqQuestion], result_limit: int
) -> list[dict[str, object]]:
    recoverable = {fault.true for fault in world.faults_of_kind(WrongKind.RECOVERABLE)}
    restored: list[Fact] = [fact for fact in world.pool if fact.triple in recoverable]
    withheld: list[Fact] = [fact for fact in world.pool if fact.triple not in recoverable]

    def restore_recoverable() -> int:
        _delete(client, _wrong_edges(world, WrongKind.RECOVERABLE))
        return load_facts(client, world, restored)[0]

    rungs: tuple[tuple[str, Callable[[], int]], ...] = (
        ("g0", lambda: 0),
        ("contradicted_removed", lambda: _delete(client, _wrong_edges(world, WrongKind.CONTRADICTED))),
        ("recoverable_restored", restore_recoverable),
        (REACHABLE_RUNG, lambda: load_facts(client, world, withheld)[0]),
        ("destroyed_removed", lambda: _delete(client, _wrong_edges(world, WrongKind.DESTROYED))),
    )
    rows: list[dict[str, object]] = []
    for name, repair in rungs:
        changed = repair()
        result = score(judge_all(client, held_out, result_limit))
        rows.append(
            {
                "dataset": "metaqa",
                "seed": world.seed,
                "rung": name,
                "edges_changed": changed,
                "held_out": asdict(result),
            }
        )
        print(f"  ladder {name}: hits@1 {result.hits}/{result.n} = {result.hits_at_1:.4f}", flush=True)
    return rows
