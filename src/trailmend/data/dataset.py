from dataclasses import dataclass

from trailmend.data.documents import DocumentSet, render
from trailmend.data.faultmodel import Ingested
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

    @property
    def graph(self) -> TruthGraph:
        return self.ingested.graph


def build(
    seed: int,
    sizes: Sizes | None = None,
    faults: FaultPlan | None = None,
    train_share: float = TRAIN_SHARE,
) -> Dataset:
    truth = generate(seed, sizes)
    ingested = inject(truth, faults)
    documents = render(ingested, truth)
    questions = build_questions(truth)
    return Dataset(seed, truth, ingested, documents, questions, make_split(questions, train_share))
