from collections.abc import Sequence

from trailmend.core.model import EdgeKey
from trailmend.graph.client import HydraClient
from trailmend.graph.schema import is_shortcut
from trailmend.graph.state import read_states


def uses_unconfirmed(client: HydraClient, paths: Sequence[Sequence[EdgeKey]], pool: frozenset[EdgeKey]) -> bool:
    keys = {key for path in paths for key in path}
    shortcuts = [key for key in keys if is_shortcut(key.rel_type)]
    states = read_states(client, shortcuts)
    for key in shortcuts:
        state = states.get(key)
        if state is None or not state.via_path:
            return True
        keys.update(state.via_path)
    selected = sorted(keys & pool)
    confirmations = read_states(client, selected)
    return any(key not in confirmations or confirmations[key].confirms == 0 for key in selected)
