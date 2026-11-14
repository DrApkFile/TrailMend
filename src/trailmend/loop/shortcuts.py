from collections.abc import Sequence
from dataclasses import dataclass

from trailmend.core.model import EdgeKey, EdgeState, EdgeStatus, MendConfig, Promote, Retire
from trailmend.core.promote import Candidate, Confirmation, candidates, promotions, retirements
from trailmend.core.receipts import Receipt
from trailmend.data.qtemplates import SHORTCUT_TYPES
from trailmend.graph.client import HydraClient
from trailmend.graph.state import list_edge_keys, read_state, read_states
from trailmend.loop.apply import apply
from trailmend.loop.journal import Journal


@dataclass(frozen=True, slots=True)
class ShortcutRound:
    promoted: tuple[Promote, ...]
    retired: tuple[Retire, ...]
    receipts: tuple[Receipt, ...]


def live_shortcuts(client: HydraClient) -> dict[EdgeKey, tuple[EdgeKey, ...]]:
    found: dict[EdgeKey, tuple[EdgeKey, ...]] = {}
    for shortcut_type in SHORTCUT_TYPES:
        for key in list_edge_keys(client, shortcut_type):
            state = read_state(client, key)
            if state is not None and state.status is EdgeStatus.ACTIVE:
                found[key] = state.via_path
    return found


def _priced_hops(client: HydraClient, found: Sequence[Candidate]) -> dict[EdgeKey, float]:
    hops = sorted({hop for candidate in found for hop in candidate.via_path})
    return {key: state.cost for key, state in read_states(client, hops).items() if state.status is EdgeStatus.ACTIVE}


def _quarantined_hops(client: HydraClient, shortcuts: dict[EdgeKey, tuple[EdgeKey, ...]]) -> set[EdgeKey]:
    hops = sorted({hop for via_path in shortcuts.values() for hop in via_path})
    states: dict[EdgeKey, EdgeState] = read_states(client, hops)
    return {key for key, state in states.items() if state.status is not EdgeStatus.ACTIVE}


def run_shortcuts(
    client: HydraClient,
    journal: Journal,
    run_id: str,
    round_index: int,
    first_sequence: int,
    confirmations: Sequence[Confirmation],
    config: MendConfig,
) -> ShortcutRound:
    live = live_shortcuts(client)
    retired = retirements(live, _quarantined_hops(client, live))
    still_live = {key: via for key, via in live.items() if key not in {r.edge for r in retired}}
    found = candidates(confirmations, still_live.keys(), config)
    promoted = promotions(found, _priced_hops(client, found))
    receipts: list[Receipt] = []
    for offset, change in enumerate((*retired, *promoted)):
        done = apply(client, journal, run_id, round_index, first_sequence + offset, change, config)
        receipts.append(done.receipt)
    return ShortcutRound(promoted, retired, tuple(receipts))
