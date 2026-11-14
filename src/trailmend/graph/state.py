from collections.abc import Iterable, Mapping

from trailmend.core.model import EdgeKey, EdgeState, EdgeStatus, Signal
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.graph.schema import ENDPOINTS, RelType

_SIGNAL_CODE: Mapping[Signal, str] = {Signal.CONFIRM: "C", Signal.BLAME: "B"}
_CODE_SIGNAL: Mapping[str, Signal] = {code: signal for signal, code in _SIGNAL_CODE.items()}


def encode_recent(signals: Iterable[Signal]) -> str:
    return "".join(_SIGNAL_CODE[signal] for signal in signals)


def decode_recent(raw: object) -> tuple[Signal, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, str):
        raise TypeError(f"recent must be a string, got {raw!r}")
    unknown = sorted(set(raw) - set(_CODE_SIGNAL))
    if unknown:
        raise ValueError(f"recent holds unknown signal codes {unknown}")
    return tuple(_CODE_SIGNAL[code] for code in raw)


def _labels(rel_type: str) -> tuple[str, str]:
    source, target = ENDPOINTS[RelType(rel_type)]
    return source.value, target.value


def _read_one(client: HydraClient, rel_type: str, src: int, dst: int) -> tuple[float, int, int, str] | None:
    rows = client.run(q.read_edge(rel_type), {"src": src, "dst": dst}).rows
    match rows:
        case ():
            return None
        case ((cost, confirms, blames, recent),):
            pass
        case _:
            raise ValueError(f"{rel_type} between {src} and {dst} matched {len(rows)} edges")
    if isinstance(cost, bool) or not isinstance(cost, int | float):
        raise TypeError(f"{rel_type} edge has an unreadable cost {cost!r}")
    if isinstance(confirms, bool) or not isinstance(confirms, int):
        raise TypeError(f"{rel_type} edge has an unreadable confirms {confirms!r}")
    if isinstance(blames, bool) or not isinstance(blames, int):
        raise TypeError(f"{rel_type} edge has an unreadable blames {blames!r}")
    if recent is not None and not isinstance(recent, str):
        raise TypeError(f"{rel_type} edge has an unreadable recent {recent!r}")
    return float(cost), confirms, blames, recent or ""


def read_state(client: HydraClient, key: EdgeKey) -> EdgeState | None:
    active = _read_one(client, key.rel_type, key.src, key.dst)
    if active is not None:
        cost, confirms, blames, recent = active
        return EdgeState(key, cost, EdgeStatus.ACTIVE, confirms, blames, decode_recent(recent))
    mirrored = _read_one(client, q.quarantine_type(key.rel_type), key.src, key.dst)
    if mirrored is None:
        return None
    cost, confirms, blames, recent = mirrored
    return EdgeState(key, cost, EdgeStatus.QUARANTINED, confirms, blames, decode_recent(recent))


def read_states(client: HydraClient, keys: Iterable[EdgeKey]) -> dict[EdgeKey, EdgeState]:
    found: dict[EdgeKey, EdgeState] = {}
    for key in dict.fromkeys(keys):
        state = read_state(client, key)
        if state is not None:
            found[key] = state
    return found


def _counters(client: HydraClient, rel_type: str, state: EdgeState) -> None:
    client.run(
        q.set_edge_counters(rel_type),
        {
            "src": state.key.src,
            "dst": state.key.dst,
            "cost": state.cost,
            "confirms": state.confirms,
            "blames": state.blames,
            "recent": encode_recent(state.recent),
        },
    )


def _move(client: HydraClient, from_type: str, to_type: str, state: EdgeState, edge_id: int) -> None:
    source, target = _labels(state.key.rel_type)
    copy, delete = q.move_edge(from_type, to_type, source, target)
    client.run(
        copy,
        {
            "rows": [
                {
                    "src": state.key.src,
                    "dst": state.key.dst,
                    "eid": edge_id,
                    "cost": state.cost,
                    "confirms": state.confirms,
                    "blames": state.blames,
                    "recent": encode_recent(state.recent),
                }
            ]
        },
    )
    client.run(delete, {"src": state.key.src, "dst": state.key.dst})


def write_state(client: HydraClient, before: EdgeState, after: EdgeState, edge_id: int) -> None:
    if before.key != after.key:
        raise ValueError(f"cannot write {after.key} over {before.key}")
    rel_type = after.key.rel_type
    mirror = q.quarantine_type(rel_type)
    if before.status is after.status:
        _counters(client, rel_type if after.status is EdgeStatus.ACTIVE else mirror, after)
        return
    if after.status is EdgeStatus.QUARANTINED:
        _move(client, rel_type, mirror, after, edge_id)
        return
    _move(client, mirror, rel_type, after, edge_id)
