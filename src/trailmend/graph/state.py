from collections.abc import Iterable, Mapping
from typing import cast

from trailmend.core.model import EdgeKey, EdgeState, EdgeStatus, Signal
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.graph.schema import labels_of

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


def encode_via(path: Iterable[EdgeKey]) -> str:
    return "|".join(f"{hop.rel_type}:{hop.src}>{hop.dst}" for hop in path)


def decode_via(raw: object) -> tuple[EdgeKey, ...]:
    if raw is None or raw == "":
        return ()
    if not isinstance(raw, str):
        raise TypeError(f"via_path must be a string, got {raw!r}")
    hops: list[EdgeKey] = []
    for piece in raw.split("|"):
        rel_type, _, ends = piece.partition(":")
        src, _, dst = ends.partition(">")
        if not rel_type or not src.isdigit() or not dst.isdigit():
            raise ValueError(f"via_path hop {piece!r} is unreadable")
        hops.append(EdgeKey(int(src), rel_type, int(dst)))
    return tuple(hops)


def state_from_row(row: Mapping[str, object]) -> EdgeState:
    key = row["key"]
    if not isinstance(key, dict):
        raise TypeError("an edge state row needs a key")
    parts = cast("dict[str, object]", key)
    recent = row.get("recent")
    via = row.get("via_path")
    return EdgeState(
        EdgeKey(int(str(parts["src"])), str(parts["rel_type"]), int(str(parts["dst"]))),
        float(str(row["cost"])),
        EdgeStatus(str(row["status"])),
        int(str(row["confirms"])),
        int(str(row["blames"])),
        tuple(Signal(str(code)) for code in cast("list[object]", recent))
        if isinstance(recent, list)
        else decode_recent(recent),
        tuple(
            EdgeKey(int(str(h["src"])), str(h["rel_type"]), int(str(h["dst"])))
            for h in cast("list[dict[str, object]]", via)
        )
        if isinstance(via, list)
        else decode_via(via),
    )


def _labels(state: EdgeState) -> tuple[str, str]:
    source, target = labels_of(state.key.rel_type, state.via_path)
    return source.value, target.value


def _read_one(
    client: HydraClient, rel_type: str, src: int, dst: int
) -> tuple[float, int, int, str, tuple[EdgeKey, ...]] | None:
    rows = client.run(q.read_edge(rel_type), {"src": src, "dst": dst}).rows
    match rows:
        case ():
            return None
        case ((cost, confirms, blames, recent, via_path),):
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
    return float(cost), confirms, blames, recent or "", decode_via(via_path)


def read_state(client: HydraClient, key: EdgeKey) -> EdgeState | None:
    active = _read_one(client, key.rel_type, key.src, key.dst)
    if active is not None:
        cost, confirms, blames, recent, via_path = active
        return EdgeState(key, cost, EdgeStatus.ACTIVE, confirms, blames, decode_recent(recent), via_path)
    mirrored = _read_one(client, q.quarantine_type(key.rel_type), key.src, key.dst)
    if mirrored is None:
        return None
    cost, confirms, blames, recent, via_path = mirrored
    return EdgeState(key, cost, EdgeStatus.QUARANTINED, confirms, blames, decode_recent(recent), via_path)


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


def _row(state: EdgeState, edge_id: int, origin: str = "ingest") -> dict[str, int | float | str | bool]:
    _, target = _labels(state)
    return {
        "src": state.key.src,
        "dst": state.key.dst,
        "eid": edge_id,
        "cost": state.cost,
        "confirms": state.confirms,
        "blames": state.blames,
        "recent": encode_recent(state.recent),
        "via_path": encode_via(state.via_path),
        "target_label": target,
        "origin": q.require_origin(origin),
    }


def _create(client: HydraClient, state: EdgeState, edge_id: int, origin: str) -> None:
    source, target = _labels(state)
    client.run(q.create_edge(source, state.key.rel_type, target), {"rows": [_row(state, edge_id, origin)]})


def _remove(client: HydraClient, key: EdgeKey) -> None:
    client.run(q.delete_edge(key.rel_type), {"src": key.src, "dst": key.dst})


def list_edge_keys(client: HydraClient, rel_type: str) -> tuple[EdgeKey, ...]:
    rows = client.run(q.list_edges(rel_type), {}).rows
    keys: list[EdgeKey] = []
    for row in rows:
        src, dst = row[0], row[1]
        if isinstance(src, bool) or isinstance(dst, bool) or not isinstance(src, int) or not isinstance(dst, int):
            raise TypeError(f"{rel_type} edge has unreadable endpoints {src!r}->{dst!r}")
        keys.append(EdgeKey(src, rel_type, dst))
    return tuple(sorted(keys))


def _move(client: HydraClient, from_type: str, to_type: str, state: EdgeState, edge_id: int) -> None:
    source, target = _labels(state)
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


def write_state(
    client: HydraClient, before: EdgeState, after: EdgeState, edge_id: int, origin: str = "shortcut"
) -> None:
    if before.key != after.key:
        raise ValueError(f"cannot write {after.key} over {before.key}")
    rel_type = after.key.rel_type
    mirror = q.quarantine_type(rel_type)
    if before.status is EdgeStatus.ABSENT and after.status is EdgeStatus.ACTIVE:
        _create(client, after, edge_id, origin)
        return
    if after.status is EdgeStatus.ABSENT:
        _remove(
            client,
            before.key if before.status is EdgeStatus.ACTIVE else EdgeKey(before.key.src, mirror, before.key.dst),
        )
        return
    if before.status is after.status:
        _counters(client, rel_type if after.status is EdgeStatus.ACTIVE else mirror, after)
        return
    if after.status is EdgeStatus.QUARANTINED:
        _move(client, rel_type, mirror, after, edge_id)
        return
    _move(client, mirror, rel_type, after, edge_id)
