import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from trailmend.graph.ids import entity_id
from trailmend.graph.schema import ENDPOINTS, NATURAL_KEY_KIND, NodeLabel, RelType

DATA_DIR = Path("data/external/metaqa")
KB_FILE = "kb.txt"
REVERSE_SUFFIX = "_REV"

FORWARD: Mapping[str, RelType] = {
    "directed_by": RelType.MQ_DIRECTED_BY,
    "written_by": RelType.MQ_WRITTEN_BY,
    "starred_actors": RelType.MQ_STARRED_ACTORS,
    "release_year": RelType.MQ_RELEASE_YEAR,
    "in_language": RelType.MQ_IN_LANGUAGE,
    "has_tags": RelType.MQ_HAS_TAGS,
    "has_genre": RelType.MQ_HAS_GENRE,
    "has_imdb_votes": RelType.MQ_HAS_IMDB_VOTES,
    "has_imdb_rating": RelType.MQ_HAS_IMDB_RATING,
}


def reverse_of(rel_type: RelType) -> RelType:
    return RelType(rel_type.value + REVERSE_SUFFIX)


@dataclass(frozen=True, slots=True, order=True)
class Triple:
    subject: str
    relation: str
    obj: str

    @property
    def rel_type(self) -> RelType:
        return FORWARD[self.relation]

    @property
    def object_label(self) -> NodeLabel:
        return ENDPOINTS[self.rel_type][1]


@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    lines: int
    triples: tuple[Triple, ...]

    def names_of(self, label: NodeLabel) -> tuple[str, ...]:
        if label is NodeLabel.MQ_MOVIE:
            return tuple(sorted({t.subject for t in self.triples}))
        return tuple(sorted({t.obj for t in self.triples if t.object_label is label}))


def read_kb(path: Path = DATA_DIR / KB_FILE) -> KnowledgeBase:
    seen: dict[Triple, None] = {}
    lines = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw:
            continue
        lines += 1
        parts = raw.split("|")
        if len(parts) != 3 or parts[1] not in FORWARD:
            raise ValueError(f"{path} line {lines} is not subject|relation|object: {raw!r}")
        seen.setdefault(Triple(parts[0], parts[1], parts[2]), None)
    if not seen:
        raise ValueError(f"{path} holds no triples")
    return KnowledgeBase(lines, tuple(seen))


def node_id(scope: str, label: NodeLabel, name: str) -> int:
    slug = hashlib.sha256(name.encode("utf-8")).hexdigest()[:20]
    return entity_id(f"{NATURAL_KEY_KIND[label]}:{scope}-{slug}")
