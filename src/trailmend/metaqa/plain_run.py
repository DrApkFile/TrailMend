import sys
from dataclasses import asdict

from trailmend.eval import evidence
from trailmend.metaqa import files
from trailmend.metaqa.analyse import rows_of, run_id_of
from trailmend.metaqa.answer import score
from trailmend.metaqa.config import load_metaqa_config
from trailmend.metaqa.kb import read_kb
from trailmend.metaqa.plain import judge_all_plain, rankings, store_of
from trailmend.metaqa.run import DATASET, SEEDS, append
from trailmend.metaqa.sample import build_workload
from trailmend.metaqa.world import build_world

SWEEP: tuple[int, ...] = (1, 3, 5, 10, 15, 30)
DESIGN = (
    "MetaQA document-only baseline: every triple in G0 rendered as the sentences it was ingested from (one per "
    "supporting document), BM25 over them, and the answer is the entity of the expected type mentioned most often in "
    "the top_k documents (ties by entity id; the topic entity itself is never an answer). No graph, no learning, so "
    "every round is the same number. top_k is swept on seed 1's held-out questions and the best is fixed for every "
    "seed - an advantage the graph arms are not given."
)


def main(seeds: tuple[int, ...] = SEEDS) -> int:
    files.verify()
    config = load_metaqa_config()
    run_id = run_id_of(rows_of())
    kb = read_kb()
    rows: list[dict[str, object]] = []
    sweep: dict[int, float] = {}
    chosen = SWEEP[0]
    for seed in seeds:
        world = build_world(kb, seed)
        workload = build_workload(kb, world, config.sample)
        store = store_of(world)
        ranked = rankings(store, workload.held_out, max(SWEEP))
        if seed == seeds[0]:
            sweep = {k: score(judge_all_plain(store, workload.held_out, ranked, k)).hits_at_1 for k in SWEEP}
            chosen = max(sweep, key=lambda k: (sweep[k], -k))
        result = score(judge_all_plain(store, workload.held_out, ranked, chosen))
        print(f"seed {seed}: plain store hits@1 {result.hits}/{result.n} = {result.hits_at_1:.4f}", flush=True)
        evidence_row: dict[str, object] = {
            "dataset": DATASET,
            "seed": seed,
            "top_k": chosen,
            "documents": store.size,
            "run_id": run_id,
        }
        evidence_row |= asdict(result)
        if seed == seeds[0]:
            evidence_row["top_k_sweep_hits_at_1"] = {str(k): round(v, 4) for k, v in sweep.items()}
        rows.append(evidence_row)
        for round_index in range(config.rounds + 1):
            curve_row: dict[str, object] = {
                "dataset": DATASET,
                "seed": seed,
                "arm": "plain_store",
                "round": round_index,
                "run_id": run_id,
                "held_out": asdict(result),
                "train": None,
                "documents": store.size,
                "top_k": chosen,
            }
            append(curve_row)
    path = evidence.write(evidence.make("plain_store_metaqa", DESIGN, rows))
    print(f"{path} sha256={evidence.digest(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(tuple(int(a) for a in sys.argv[1:]) or SEEDS))
