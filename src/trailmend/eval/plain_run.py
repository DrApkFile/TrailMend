import sys

from trailmend.data import dataset
from trailmend.data.faultmodel import V1, V2
from trailmend.eval import evidence
from trailmend.eval.plain_store import TOP_K, build_store, judge_all_plain
from trailmend.loop.evaluate import score

DESIGN = (
    "The plain_store arm answers the same held-out questions from the same ingested documents, with no graph. "
    "BM25 (k1=1.5, b=0.75) ranks the documents by the question text, and the answer is the most frequently "
    "mentioned entity of the template's expected label across the top-k documents. Ties follow the same C3a rule "
    "as the graph arm: a multi-answer template returns the whole tied set, a single-answer template refuses. No "
    "document mentioning an entity of the expected label in the top-k means unreachable. The pool is withheld "
    "from this arm exactly as it is from the graph, so both see the same evidence. It cannot learn, so its number "
    "is the same in every round - that is the point of the arm. top_k was swept on seed 1 held-out accuracy "
    "(k=1: 0.2147, 3: 0.1559, 5: 0.1706, 10: 0.2294, 12: 0.2441, 15: 0.2647, 18: 0.2529, 20: 0.2500, 25: 0.2441, "
    "30: 0.1853, 50: 0.1500) and fixed at its best value, 15, for every seed. That tuning favours the baseline: "
    "it was chosen on held-out scores, while the Mend's constants were frozen in config/mend.toml before any run. "
    "Swept again on data v2, where every edge is asserted by one to three documents instead of exactly one (k=1: "
    "0.2588, 3: 0.2176, 5: 0.2324, 10: 0.2794, 12: 0.2912, 15: 0.2941, 18: 0.2853, 20: 0.2735, 25: 0.2941, 30: "
    "0.2882, 50: 0.2147): 15 and 25 tie for best, so the configured 15 stays and the baseline keeps its advantage."
)


def main(seeds: tuple[int, ...], top_k: int = TOP_K, data_version: str = V1) -> int:
    rows: list[dict[str, object]] = []
    for seed in seeds:
        built = dataset.build(seed, data_version=data_version)
        store = build_store(built.documents.ingested, built.graph.nodes)
        judged = judge_all_plain(store, [h.question for h in built.split.held_out], top_k)
        result = score(judged)
        rows.append(
            {
                "dataset": "northwind_generated",
                "data_version": data_version,
                "seed": seed,
                "arm": "plain_store",
                "round": 0,
                "top_k": top_k,
                "documents": store.size,
                "n_heldout": result.n,
                "correct": result.correct,
                "accuracy": round(result.accuracy, 4),
                "set_f1": round(result.set_f1, 4),
                "wrong": result.wrong,
                "unreachable": result.unreachable,
                "refused": result.refused,
            }
        )
        print(f"seed {seed}: {result.correct}/{result.n} = {result.accuracy:.4f}, set_f1 {result.set_f1:.4f}")
    claim = "plain_store" if data_version == V1 else f"plain_store_{data_version}"
    path = evidence.write(evidence.make(claim, DESIGN, rows))
    print(f"wrote {path} sha256={evidence.digest(path)}")
    return 0


if __name__ == "__main__":
    _args = sys.argv[1:]
    _version = V2 if "--v2" in _args else V1
    raise SystemExit(main(tuple(int(a) for a in _args if a.isdigit()) or (1, 7, 42), data_version=_version))
