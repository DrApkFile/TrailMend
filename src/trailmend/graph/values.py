from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

type Scalar = int | float | str | bool | None
type Cell = Scalar | "PathValue"

_PROPERTY_KINDS = ("Float", "Integer", "String", "Boolean")


class DecodeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PathRel:
    rel_type: str
    src: int
    dst: int
    props: Mapping[str, Scalar]


@dataclass(frozen=True, slots=True)
class PathValue:
    node_ids: tuple[int, ...]
    rels: tuple[PathRel, ...]


def _require_int(raw: object, field: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise DecodeError(f"{field} must be an integer, got {raw!r}")
    return raw


def _require_mapping(raw: object, field: str) -> Mapping[str, object]:
    if not isinstance(raw, dict):
        raise DecodeError(f"{field} must be an object, got {type(raw).__name__}")
    return {str(k): v for k, v in cast("dict[object, object]", raw).items()}


def _require_sequence(raw: object, field: str) -> Sequence[object]:
    if not isinstance(raw, list):
        raise DecodeError(f"{field} must be a list, got {type(raw).__name__}")
    return cast("list[object]", raw)


def decode_property(raw: object) -> Scalar:
    wrapped = _require_mapping(raw, "property")
    if len(wrapped) != 1:
        raise DecodeError(f"property must have exactly one kind, got {sorted(wrapped)}")
    kind, value = next(iter(wrapped.items()))
    if kind not in _PROPERTY_KINDS:
        raise DecodeError(f"unknown property kind {kind!r}")
    if kind == "Float" and isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float | str | bool):
        return value
    raise DecodeError(f"property {kind} has unsupported value {value!r}")


def decode_path(raw: object) -> PathValue:
    body = _require_mapping(raw, "path")
    nodes = tuple(
        _require_int(_require_mapping(n, "node").get("id"), "node.id")
        for n in _require_sequence(body.get("nodes"), "nodes")
    )
    rels: list[PathRel] = []
    for item in _require_sequence(body.get("relationships"), "relationships"):
        rel = _require_mapping(item, "relationship")
        rel_type = rel.get("edge_type")
        if not isinstance(rel_type, str):
            raise DecodeError("relationship.edge_type must be a string")
        props = {k: decode_property(v) for k, v in _require_mapping(rel.get("properties", {}), "properties").items()}
        rels.append(PathRel(rel_type, _require_int(rel.get("src"), "src"), _require_int(rel.get("dst"), "dst"), props))
    if len(nodes) != len(rels) + 1:
        raise DecodeError(f"path has {len(nodes)} nodes but {len(rels)} relationships")
    return PathValue(nodes, tuple(rels))


def _decode_int(value: object) -> Cell:
    return _require_int(value, "integer")


def _decode_float(value: object) -> Cell:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    raise DecodeError(f"float cell has value {value!r}")


def _decode_string(value: object) -> Cell:
    if isinstance(value, str):
        return value
    raise DecodeError(f"string cell has value {value!r}")


def _decode_boolean(value: object) -> Cell:
    if isinstance(value, bool):
        return value
    raise DecodeError(f"boolean cell has value {value!r}")


def _decode_null(_: object) -> Cell:
    return None


_CELL_DECODERS: dict[str, Callable[[object], Cell]] = {
    "vertex_id": _decode_int,
    "integer": _decode_int,
    "float": _decode_float,
    "string": _decode_string,
    "boolean": _decode_boolean,
    "null": _decode_null,
    "path": decode_path,
}


def decode_cell(raw: object) -> Cell:
    cell = _require_mapping(raw, "cell")
    kind = cell.get("type")
    if "value" not in cell:
        return None
    decoder = _CELL_DECODERS.get(kind) if isinstance(kind, str) else None
    if decoder is None:
        raise DecodeError(f"unknown cell type {kind!r}")
    return decoder(cell["value"])
