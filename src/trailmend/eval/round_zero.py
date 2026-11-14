import sys
from pathlib import Path

from trailmend.core.config import load_search_config
from trailmend.data import dataset
from trailmend.eval import evidence
from trailmend.graph.client import HydraClient
from trailmend.graph.loader import load
from trailmend.loop.evaluate import judge_all, score
from trailmend.search.seed import build_index
from trailmend.settings import load_settings

DESIGN = (
    "Round 0 is the frozen ingested graph G0: every edge at cost 1.0, no Mend has run. For each seed, load G0, "
    "then answer every held-out question read-only and score it. Correct means the returned answer set equals "
    "gold exactly (DECISIONS 2026-11-14, C3a): a multi-answer template returns every entity tied at minimum "
    "cost, a single-answer template refuses a tie. set_f1 is the mean per-question F1 of answer set against "
    "gold. Held-out questions are never used to change the graph. This is the baseline the Mend has to beat, "
    "not a result about the Mend. Rows marked superseded are earlier measurements kept on record, "
    "with the reason they no longer stand."
)


SUPERSEDED: tuple[dict[str, object], ...] = (
    {
        "dataset": "northwind_generated",
        "seed": 7,
        "arm": "frozen",
        "round": 0,
        "n_heldout": 340,
        "correct": 259,
        "accuracy": 0.7618,
        "set_f1": None,
        "wrong": 17,
        "unreachable": 33,
        "refused": 31,
        "superseded": True,
        "superseded_by": "the C3a rule recorded in DECISIONS on 2026-11-14",
        "superseded_reason": (
            "Measured at commit 2a09c64, when every tie refused as ambiguous_answer. At round 0 every edge "
            "costs 1.0, so all 31 refusals were multi-answer templates whose gold is a set and whose answers "
            "were therefore tied by construction. That figure measured the tie-break rule, not the graph. "
            "Kept on record rather than deleted."
        ),
        "measured_at_commit": "2a09c64",
    },
)


def _client() -> HydraClient:
    settings = load_settings()
    return HydraClient(
        str(settings.hydra_url),
        settings.hydra_token.get_secret_value(),
        settings.hydra_graph_id,
        settings.hydra_cell_id,
        settings.hydra_timeout_s,
    )


def main(seeds: tuple[int, ...]) -> int:
    config = load_search_config(Path("config/mend.toml"))
    rows: list[dict[str, object]] = []
    with _client() as client:
        client.require_writable()
        for seed in seeds:
            built = dataset.build(seed)
            load(client, built.graph)
            index = build_index(built.graph.nodes)
            judged = judge_all(client, index, [h.question for h in built.split.held_out], config)
            result = score(judged)
            rows.append(
                {
                    "dataset": "northwind_generated",
                    "seed": seed,
                    "arm": "frozen",
                    "round": 0,
                    "n_heldout": result.n,
                    "correct": result.correct,
                    "accuracy": round(result.accuracy, 4),
                    "set_f1": round(result.set_f1, 4),
                    "wrong": result.wrong,
                    "unreachable": result.unreachable,
                    "refused": result.refused,
                    "superseded": False,
                }
            )
            print(f"seed {seed}: {result.correct}/{result.n} = {result.accuracy:.4f}, set_f1 {result.set_f1:.4f}")
    path = evidence.write(evidence.make("round_zero", DESIGN, [*rows, *SUPERSEDED]))
    print(f"wrote {path} sha256={evidence.digest(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(tuple(int(a) for a in sys.argv[1:]) or (1, 7, 42)))
