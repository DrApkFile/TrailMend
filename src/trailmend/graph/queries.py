import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from trailmend.core.model import QUARANTINE_PREFIX

_LABEL = re.compile(r"^[A-Z][A-Za-z0-9]{0,40}$")
_REL_TYPE = re.compile(r"^[A-Z][A-Z0-9_]{0,40}$")
PROBE_SOURCE_ID = 4_000_000_000_000_000_001
PROBE_TARGET_ID = 4_000_000_000_000_000_002


class Operation(StrEnum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True, slots=True)
class NamedQuery:
    name: str
    operation: Operation
    cypher: str


def require_label(label: str) -> str:
    if not _LABEL.fullmatch(label):
        raise ValueError(f"invalid node label {label!r}")
    return label


def require_rel_type(rel_type: str) -> str:
    if not _REL_TYPE.fullmatch(rel_type):
        raise ValueError(f"invalid relationship type {rel_type!r}")
    return rel_type


def require_searchable(rel_type: str) -> str:
    if require_rel_type(rel_type).startswith(QUARANTINE_PREFIX):
        raise ValueError(f"quarantined type {rel_type!r} can never be searched")
    return rel_type


ORIGINS = ("ingest", "shortcut", "gapfill")


def require_origin(origin: str) -> str:
    if origin not in ORIGINS:
        raise ValueError(f"unknown edge origin {origin!r}")
    return origin


def quarantine_type(rel_type: str) -> str:
    return require_rel_type(QUARANTINE_PREFIX + require_searchable(rel_type))


PROBE_WRITE = NamedQuery(
    "probe_write",
    Operation.WRITE,
    f"MERGE (a:Probe {{id: {PROBE_SOURCE_ID}}})-[:PROBE {{n: 1}}]->(b:Probe {{id: {PROBE_TARGET_ID}}})",
)
PROBE_READ = NamedQuery(
    "probe_read", Operation.READ, f"MATCH (a {{id: {PROBE_SOURCE_ID}}})-[:PROBE]->(b) RETURN b.id AS id"
)
PROBE_CLEANUP_SOURCE = NamedQuery(
    "probe_cleanup_source", Operation.WRITE, f"MATCH (a {{id: {PROBE_SOURCE_ID}}}) DETACH DELETE a"
)
PROBE_CLEANUP_TARGET = NamedQuery(
    "probe_cleanup_target", Operation.WRITE, f"MATCH (a {{id: {PROBE_TARGET_ID}}}) DETACH DELETE a"
)


def upsert_nodes(label: str) -> NamedQuery:
    return NamedQuery(
        f"upsert_nodes:{label}",
        Operation.WRITE,
        f"UNWIND $rows AS row MERGE (n {{id: row.id}}) SET n:{require_label(label)}, n.name = row.name",
    )


def upsert_edges(src_label: str, rel_type: str, dst_label: str) -> NamedQuery:
    return NamedQuery(
        f"upsert_edges:{rel_type}",
        Operation.WRITE,
        f"UNWIND $rows AS row MATCH (a:{require_label(src_label)} {{id: row.src}}), "
        f"(b:{require_label(dst_label)} {{id: row.dst}}) "
        f"MERGE (a)-[r:{require_rel_type(rel_type)} {{id: row.eid}}]->(b) "
        "SET r.cost = row.cost, r.confirms = row.confirms, r.blames = row.blames, r.recent = row.recent",
    )


def read_edge(rel_type: str) -> NamedQuery:
    return NamedQuery(
        f"read_edge:{rel_type}",
        Operation.READ,
        f"MATCH (a {{id: $src}})-[r:{require_rel_type(rel_type)}]->(b {{id: $dst}}) "
        "RETURN r.cost AS cost, r.confirms AS confirms, r.blames AS blames, r.recent AS recent, "
        "r.via_path AS via_path",
    )


def set_edge_counters(rel_type: str) -> NamedQuery:
    return NamedQuery(
        f"set_edge_counters:{rel_type}",
        Operation.WRITE,
        f"MATCH (a {{id: $src}})-[r:{require_rel_type(rel_type)}]->(b {{id: $dst}}) "
        "SET r.cost = $cost, r.confirms = $confirms, r.blames = $blames, r.recent = $recent",
    )


def delete_edge(rel_type: str) -> NamedQuery:
    return NamedQuery(
        f"delete_edge:{rel_type}",
        Operation.WRITE,
        f"MATCH (a {{id: $src}})-[r:{require_rel_type(rel_type)}]->(b {{id: $dst}}) DELETE r",
    )


def create_edge(src_label: str, rel_type: str, dst_label: str) -> NamedQuery:
    return NamedQuery(
        f"create_edge:{rel_type}",
        Operation.WRITE,
        f"UNWIND $rows AS row MATCH (a:{require_label(src_label)} {{id: row.src}}), "
        f"(b:{require_label(dst_label)} {{id: row.dst}}) "
        f"MERGE (a)-[r:{require_rel_type(rel_type)} {{id: row.eid}}]->(b) "
        "SET r.cost = row.cost, r.confirms = row.confirms, r.blames = row.blames, r.recent = row.recent, "
        "r.via_path = row.via_path, r.target_label = row.target_label, r.origin = row.origin",
    )


def list_edges(rel_type: str) -> NamedQuery:
    return NamedQuery(
        f"list_edges:{rel_type}",
        Operation.READ,
        f"MATCH (a)-[r:{require_rel_type(rel_type)}]->(b) RETURN a.id AS src, b.id AS dst",
    )


def count_nodes(label: str) -> NamedQuery:
    return NamedQuery(f"count_nodes:{label}", Operation.READ, f"MATCH (n:{require_label(label)}) RETURN count(*) AS n")


def count_edges(rel_type: str) -> NamedQuery:
    return NamedQuery(
        f"count_edges:{rel_type}",
        Operation.READ,
        f"MATCH (a)-[r:{require_rel_type(rel_type)}]->(b) RETURN count(*) AS n",
    )


def _rel_list(rel_types: Sequence[str]) -> str:
    if not rel_types:
        raise ValueError("at least one relationship type is required")
    return "[" + ", ".join(f"'{require_searchable(t)}'" for t in rel_types) + "]"


def _weight_clause(weighted: bool) -> str:
    return ", weightProp: 'cost'" if weighted else ""


def weighted_paths_from(
    rel_types: Sequence[str], max_len: int, result_limit: int, *, weighted: bool = True
) -> NamedQuery:
    if not 1 <= max_len <= 4:
        raise ValueError("max_len must be between 1 and 4")
    if not 1 <= result_limit <= 500:
        raise ValueError("result_limit must be between 1 and 500")
    return NamedQuery(
        "weighted_paths_from" if weighted else "unweighted_paths_from",
        Operation.READ,
        "CALL algo.SSpaths({sourceNode: $src, relTypes: " + _rel_list(rel_types) + ", relDirection: 'outgoing', "
        f"maxLen: {max_len}, pathCount: {result_limit}{_weight_clause(weighted)}}}) "
        "YIELD path, pathWeight RETURN path, pathWeight",
    )


def weighted_path_between(rel_types: Sequence[str], max_len: int, *, weighted: bool = True) -> NamedQuery:
    if not 1 <= max_len <= 4:
        raise ValueError("max_len must be between 1 and 4")
    return NamedQuery(
        "weighted_path_between" if weighted else "unweighted_path_between",
        Operation.READ,
        "CALL algo.SPpaths({sourceNode: $src, targetNode: $dst, relTypes: " + _rel_list(rel_types) + ", "
        f"relDirection: 'outgoing', maxLen: {max_len}, pathCount: 0{_weight_clause(weighted)}}}) "
        "YIELD path, pathWeight RETURN path, pathWeight",
    )


def move_edge(from_type: str, to_type: str, src_label: str, dst_label: str) -> tuple[NamedQuery, NamedQuery]:
    copy = NamedQuery(
        f"move_edge_copy:{from_type}->{to_type}",
        Operation.WRITE,
        f"UNWIND $rows AS row MATCH (a:{require_label(src_label)} {{id: row.src}}), "
        f"(b:{require_label(dst_label)} {{id: row.dst}}) "
        f"MERGE (a)-[r:{require_rel_type(to_type)} {{id: row.eid}}]->(b) "
        "SET r.cost = row.cost, r.confirms = row.confirms, r.blames = row.blames, r.recent = row.recent",
    )
    return copy, delete_edge(from_type)
