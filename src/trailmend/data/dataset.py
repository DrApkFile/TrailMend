from collections.abc import Mapping
from dataclasses import dataclass

from trailmend.data.documents import DocumentSet, render
from trailmend.data.faultmodel import V1, Ingested
from trailmend.data.faults import FaultPlan, inject
from trailmend.data.model import TruthGraph
from trailmend.data.northwind import Sizes, generate
from trailmend.data.questions import QuestionSet
from trailmend.data.questions import build as build_questions
from trailmend.eval.splits import TRAIN_SHARE, Split, make_split


@dataclass(frozen=True, slots=True)
class Dataset:
    seed: int
    truth: TruthGraph
    ingested: Ingested
    documents: DocumentSet
    questions: QuestionSet
    split: Split
    data_version: str = V1

    @property
    def graph(self) -> TruthGraph:
        return self.ingested.graph

    @property
    def support(self) -> Mapping[int, int]:
        return self.documents.ingested_support


def build(
    seed: int,
    sizes: Sizes | None = None,
    faults: FaultPlan | None = None,
    train_share: float = TRAIN_SHARE,
    data_version: str = V1,
) -> Dataset:
    truth = generate(seed, sizes)
    ingested = inject(truth, faults, data_version)
    documents = render(ingested, truth)
    questions = build_questions(truth)
    split = make_split(questions, train_share)
    return Dataset(seed, truth, ingested, documents, questions, split, data_version)
