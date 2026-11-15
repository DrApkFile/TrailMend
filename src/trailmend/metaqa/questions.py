import re
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from trailmend.graph.schema import ENDPOINTS, NodeLabel, RelType
from trailmend.metaqa.kb import DATA_DIR, reverse_of

DEV = "dev"
TEST = "test"
HOPS: tuple[int, ...] = (1, 2, 3)

QUESTION_FILES: Mapping[tuple[int, str], tuple[str, str]] = {
    (1, DEV): ("1 hop qa_dev.txt", "1 hop qa_dev_qtype.txt"),
    (1, TEST): ("1 hop qa_test.txt", "1 hop qa_test_qtype.txt"),
    (2, DEV): ("2 hop qa_dev.txt", "2 hop qa_dev_qtype.txt"),
    (2, TEST): ("2 hop qa_test.txt", "2 hop qa_test_qtype.txt"),
    (3, DEV): ("3 hop qa dev.txt", "3 hop qa_dev_qtype.txt"),
    (3, TEST): ("3 hop qa_test.txt", "3 hop qa_test_qtype.txt"),
}

_TOPIC = re.compile(r"\[(.+?)\]")
_SEPARATOR = "_to_"

_OUT_OF_MOVIE: Mapping[str, RelType] = {
    "director": RelType.MQ_DIRECTED_BY,
    "writer": RelType.MQ_WRITTEN_BY,
    "actor": RelType.MQ_STARRED_ACTORS,
    "year": RelType.MQ_RELEASE_YEAR,
    "language": RelType.MQ_IN_LANGUAGE,
    "tags": RelType.MQ_HAS_TAGS,
    "tag": RelType.MQ_HAS_TAGS,
    "genre": RelType.MQ_HAS_GENRE,
    "imdbvotes": RelType.MQ_HAS_IMDB_VOTES,
    "imdbrating": RelType.MQ_HAS_IMDB_RATING,
}
MOVIE = "movie"


def rel_path_of(qtype: str) -> tuple[RelType, ...]:
    stops = qtype.split(_SEPARATOR)
    if len(stops) < 2:
        raise ValueError(f"qtype {qtype!r} names no hop")
    path: list[RelType] = []
    for here, there in pairwise(stops):
        if here == MOVIE and there in _OUT_OF_MOVIE:
            path.append(_OUT_OF_MOVIE[there])
        elif there == MOVIE and here in _OUT_OF_MOVIE:
            path.append(reverse_of(_OUT_OF_MOVIE[here]))
        else:
            raise ValueError(f"qtype {qtype!r} has a hop {here}->{there} the knowledge base cannot express")
    return tuple(path)


@dataclass(frozen=True, slots=True)
class RawQuestion:
    hop: int
    split: str
    line: int
    qtype: str
    text: str
    topic: str
    answers: tuple[str, ...]

    @property
    def id(self) -> str:
        return f"mq-{self.hop}hop-{self.split}-{self.line}"

    @property
    def rel_path(self) -> tuple[RelType, ...]:
        return rel_path_of(self.qtype)

    @property
    def topic_label(self) -> NodeLabel:
        return ENDPOINTS[self.rel_path[0]][0]

    @property
    def answer_label(self) -> NodeLabel:
        return ENDPOINTS[self.rel_path[-1]][1]


def read_questions(hop: int, split: str, root: Path = DATA_DIR) -> tuple[RawQuestion, ...]:
    question_file, qtype_file = QUESTION_FILES[(hop, split)]
    lines = (root / question_file).read_text(encoding="utf-8").splitlines()
    qtypes = (root / qtype_file).read_text(encoding="utf-8").splitlines()
    if len(lines) != len(qtypes):
        raise ValueError(f"{question_file} has {len(lines)} lines but {qtype_file} has {len(qtypes)}")
    found: list[RawQuestion] = []
    for number, (raw, qtype) in enumerate(zip(lines, qtypes, strict=True), start=1):
        text, tab, answers = raw.partition("\t")
        topic = _TOPIC.search(text)
        if not tab or topic is None or not answers:
            raise ValueError(f"{question_file} line {number} is not 'question [topic]<TAB>answers'")
        if len(rel_path_of(qtype)) != hop:
            raise ValueError(f"{qtype_file} line {number}: {qtype!r} is not a {hop}-hop type")
        found.append(RawQuestion(hop, split, number, qtype, text, topic.group(1), tuple(answers.split("|"))))
    return tuple(found)


def read_split(split: str, root: Path = DATA_DIR) -> tuple[RawQuestion, ...]:
    return tuple(question for hop in HOPS for question in read_questions(hop, split, root))
