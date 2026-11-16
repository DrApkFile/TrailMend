import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from trailmend.data import dataset
from trailmend.data.faultmodel import V2
from trailmend.eval import curve, evidence, paired, replication_facts
from trailmend.loop.policy import MendPolicy

EVIDENCE = evidence.EVIDENCE_DIR
CURVE_METAQA = EVIDENCE / "curve_metaqa.jsonl"
METAQA_DIR = EVIDENCE / "metaqa"
FULL = MendPolicy.FULL_V2.value
FROZEN = MendPolicy.FROZEN.value
RANDOM = MendPolicy.RANDOM_REWEIGHT.value
UNWEIGHTED = MendPolicy.FULL_UNWEIGHTED.value
GAPFILL_ONLY = MendPolicy.GAPFILL_WIDE_ONLY.value
PLAIN = "plain_store"
ALPHA = 0.05
DESIGN = (
    "The benchmark paragraph, one sentence per row, composed by trailmend.eval.benchmark from the evidence files named "
    "in each row's sources and from nothing else. A sentence is only written in its strong form when the numbers "
    "support it; otherwise it states what was measured. `facts` holds every number a sentence uses."
)
SUMMARY_DESIGN = (
    "The generated company graphs of run 2, one row per seed: nodes and edges in G0, withheld edges, and the planted "
    "faults by kind. Regenerated from the seed by the dataset code, whose digests are in run_manifest_v2.json."
)

type Rows = Sequence[Mapping[str, object]]


def _jsonl(path: Path) -> Rows:
    if not path.exists():
        return ()
    return tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)


def _file(name: str) -> Rows:
    path = EVIDENCE / f"{name}.json"
    if not path.exists():
        return ()
    rows = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8"))).get("rows")
    return tuple(cast("list[Mapping[str, object]]", rows)) if isinstance(rows, list) else ()


def _num(raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float | str):
        raise TypeError(f"expected a number, got {raw!r}")
    return float(raw)


def _held(row: Mapping[str, object], name: str) -> float:
    return _num(cast("dict[str, object]", row["held_out"])[name])


def _mean(rows: Rows, arm: str, round_index: int, name: str) -> float | None:
    found = [_held(row, name) for row in rows if row.get("arm") == arm and row.get("round") == round_index]
    return sum(found) / len(found) if found else None


def _pooled(rows: Rows, arm: str, round_index: int, name: str) -> int | None:
    found = [int(_held(row, name)) for row in rows if row.get("arm") == arm and row.get("round") == round_index]
    return sum(found) if found else None


def _seeds(rows: Rows) -> tuple[int, ...]:
    return tuple(sorted({int(_num(row["seed"])) for row in rows}))


def _final(rows: Rows) -> int:
    return max(int(_num(row["round"])) for row in rows)


def _pct(value: float | None, places: int = 1) -> str:
    return f"{100 * value:.{places}f}%" if value is not None else "—"


def _span(values: Sequence[int]) -> str:
    if not values:
        return "—"
    low, high = min(values), max(values)
    return f"{low:,}" if low == high else f"{low:,} to {high:,}"


def dataset_summary(seeds: Sequence[int]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for seed in seeds:
        built = dataset.build(seed, data_version=V2)
        faults = built.ingested.faults
        out.append(
            {
                "dataset": "northwind_generated",
                "data_version": V2,
                "seed": seed,
                "nodes": len(built.graph.nodes),
                "edges": len(built.graph.edges),
                "withheld_edges": len(built.ingested.pool),
                "wrong_edges": len(faults.wrong_edges),
                "missing_edges": len(faults.missing_edges),
                "alias_duplicates": len(faults.alias_duplicates),
                "conflations": len(faults.conflations),
                "planted_faults": len(faults.wrong_edges)
                + len(faults.missing_edges)
                + len(faults.alias_duplicates)
                + len(faults.conflations),
                "held_out_questions": len(built.split.held_out),
            }
        )
    return out


def paired_summary(rows: Rows, arm: str, reference: str = FROZEN) -> tuple[int, int, float | None]:
    found = [row for row in rows if row.get("arm") == arm and row.get("reference") == reference]
    significant = sum(_num(row["p_value"]) < ALPHA and _num(row["delta_points"]) > 0 for row in found)
    worst = max((_num(row["p_value"]) for row in found), default=None)
    return significant, len(found), worst


def captured_pooled(rows: Rows) -> float | None:
    reachable = sum(_num(row["reachable_points"]) for row in rows)
    return sum(_num(row["gained_points"]) for row in rows) / reachable if rows and reachable > 0 else None


def stayed_right(run_id: str, seeds: Sequence[int], arm: str, final: int) -> tuple[int, int]:
    kept = total = 0
    for seed in seeds:
        start = paired.correct_at(f"{run_id}-s{seed}-{arm}", 0)
        end = paired.correct_at(f"{run_id}-s{seed}-{arm}", final)
        total += sum(start.values())
        kept += sum(1 for question, right in start.items() if right and end[question])
    return kept, total


def _p_clause(significant: int, seeds: int, worst: float | None) -> str:
    if seeds == 0 or worst is None:
        return "paired test not run"
    if significant == seeds:
        bound = "p < 0.001" if worst < 0.001 else f"p ≤ {worst:.3f}"
        return f"{bound} on a paired test, every seed"
    return f"p < 0.05 on a paired test for {significant} of {seeds} seeds"


def _moved(start: float | None, end: float | None) -> str:
    if start is None or end is None:
        return "was not measured"
    verb = "rose" if end > start + 0.0005 else "fell" if end < start - 0.0005 else "stayed"
    return f"{verb} from {_pct(start)} to {_pct(end)}" if verb != "stayed" else f"stayed at {_pct(end)}"


def _run_id(rows: Rows) -> str | None:
    found = {str(row["run_id"]) for row in rows}
    return found.pop() if len(found) == 1 else None


def _breaks(rows: Rows, arm: str, traced_field: str) -> tuple[int, int]:
    picked = [row for row in rows if row.get("arm") == arm]
    return (
        sum(int(_num(row["newly_broken"])) for row in picked),
        sum(int(_num(row[traced_field])) for row in picked),
    )


def _metaqa_datasets() -> Rows:
    if not METAQA_DIR.exists():
        return ()
    return tuple(json.loads(path.read_text(encoding="utf-8")) for path in sorted(METAQA_DIR.glob("dataset_s*.json")))


def _wrong_change(start: int | None, end: int | None) -> tuple[str, float | None]:
    if start is None or end is None or start == 0:
        return "were not measured", None
    change = (end - start) / start
    verb = "fell" if change < 0 else "rose"
    return f"{verb} {abs(100 * change):.0f}%", change


def northwind_facts() -> dict[str, object]:
    rows = _jsonl(curve.CURVE_V2)
    if not rows:
        return {}
    seeds, final, run_id = _seeds(rows), _final(rows), _run_id(rows)
    summary = _file("dataset_summary_v2")
    pairs = _file("paired_v2")
    significant, tested, worst = paired_summary(pairs, FULL)
    control_wins, _, _ = paired_summary(pairs, RANDOM)
    broken, traced = _breaks(_file("non_regression_v2"), FULL, "breaks_traced_to_a_receipt")
    kept, right = stayed_right(run_id, seeds, FULL, final) if run_id else (0, 0)
    unweighted = _jsonl(curve.CURVE_V2_UNWEIGHTED)
    g0_edges = sum(int(_num(row["edges"])) for row in summary)
    ingested = _sum_field(rows, FULL, final, "gapfill_ingested")
    return {
        "run_id": run_id,
        "seeds": list(seeds),
        "rounds": final,
        "nodes": [int(_num(row["nodes"])) for row in summary],
        "planted_faults": [int(_num(row["planted_faults"])) for row in summary],
        "held_out_questions": _pooled(rows, FULL, 0, "n"),
        "accuracy_round_0": _mean(rows, FULL, 0, "accuracy"),
        "accuracy_round_n": _mean(rows, FULL, final, "accuracy"),
        "seeds_significant": significant,
        "seeds_tested": tested,
        "worst_p": worst,
        "captured_share": captured_pooled(_file("captured_share_v2")),
        "frozen_round_n": _mean(rows, FROZEN, final, "accuracy"),
        "random_reweight_round_n": _mean(rows, RANDOM, final, "accuracy"),
        "random_reweight_seeds_beating_frozen": control_wins,
        "gapfill_only_round_n": _mean(rows, GAPFILL_ONLY, final, "accuracy"),
        "plain_store": _mean(rows, PLAIN, final, "accuracy"),
        "unweighted_run_id": _run_id(unweighted) if unweighted else None,
        "unweighted_round_0": _mean(unweighted, UNWEIGHTED, 0, "accuracy"),
        "unweighted_round_n": _mean(unweighted, UNWEIGHTED, final, "accuracy") if unweighted else None,
        "wrong_round_0": _pooled(rows, FULL, 0, "wrong"),
        "wrong_round_n": _pooled(rows, FULL, final, "wrong"),
        "right_at_round_0": right,
        "still_right_at_round_n": kept,
        "breaks": broken,
        "breaks_traced": traced,
        "g0_edges": g0_edges,
        "edges_ingested": ingested,
    }


def _sum_field(rows: Rows, arm: str, round_index: int, name: str) -> int | None:
    found = [row.get(name) for row in rows if row.get("arm") == arm and row.get("round") == round_index]
    numbers = [int(value) for value in found if isinstance(value, int) and not isinstance(value, bool)]
    return sum(numbers) if numbers else None


def metaqa_facts() -> dict[str, object]:
    rows = _jsonl(CURVE_METAQA)
    described = _metaqa_datasets()
    if not rows or not described:
        return {}
    seeds, final, run_id = _seeds(rows), _final(rows), _run_id(rows)
    pairs = _file("paired_metaqa")
    significant, tested, worst = paired_summary(pairs, FULL)
    control_wins, _, _ = paired_summary(pairs, RANDOM)
    breaks = _file("non_regression_metaqa")
    kept, right = stayed_right(run_id, seeds, FULL, final) if run_id else (0, 0)
    filled = [
        int(_num(row["gapfill_facts"]))
        for row in rows
        if row.get("arm") == FULL and isinstance(row.get("gapfill_facts"), int)
    ]
    return {
        "run_id": run_id,
        "seeds": list(seeds),
        "rounds": final,
        "kb_lines": int(_num(described[0]["kb_lines"])),
        "held_out_questions": [int(_num(row["held_out"])) for row in described],
        "g0_triples": [int(_num(row["g0_triples"])) for row in described],
        "hits_round_0": _mean(rows, FULL, 0, "hits_at_1"),
        "hits_round_n": _mean(rows, FULL, final, "hits_at_1"),
        "exact_round_0": _mean(rows, FULL, 0, "exact_set"),
        "exact_round_n": _mean(rows, FULL, final, "exact_set"),
        "seeds_significant": significant,
        "seeds_tested": tested,
        "worst_p": worst,
        "captured_share": captured_pooled(_file("captured_share_metaqa")),
        "frozen_round_n": _mean(rows, FROZEN, final, "hits_at_1"),
        "random_reweight_round_n": _mean(rows, RANDOM, final, "hits_at_1"),
        "random_reweight_seeds_beating_frozen": control_wins,
        "plain_store": _mean(rows, PLAIN, final, "hits_at_1"),
        "wrong_round_0": _pooled(rows, FULL, 0, "wrong"),
        "wrong_round_n": _pooled(rows, FULL, final, "wrong"),
        "right_at_round_0": right,
        "still_right_at_round_n": kept,
        "breaks": sum(int(_num(row["newly_broken"])) for row in breaks),
        "breaks_traced": sum(int(_num(row["breaks_traced_to_a_receipt"])) for row in breaks),
        "triples_ingested": sum(filled) if filled else None,
    }


def _as_float(raw: object) -> float | None:
    return float(raw) if isinstance(raw, int | float) and not isinstance(raw, bool) else None


def _as_int(raw: object) -> int | None:
    return raw if isinstance(raw, int) and not isinstance(raw, bool) else None


def _ints(raw: object) -> list[int]:
    return [int(v) for v in cast("list[object]", raw) if isinstance(v, int)] if isinstance(raw, list) else []


def _gain(facts: Mapping[str, object], start: str, end: str, what: str) -> str:
    moved = _moved(_as_float(facts.get(start)), _as_float(facts.get(end)))
    clause = _p_clause(
        _as_int(facts.get("seeds_significant")) or 0,
        _as_int(facts.get("seeds_tested")) or 0,
        _as_float(facts.get("worst_p")),
    )
    return f"{what} {moved} ({clause})"


def _control(facts: Mapping[str, object], unit: str) -> str:
    random_end, frozen_end = _as_float(facts.get("random_reweight_round_n")), _as_float(facts.get("frozen_round_n"))
    if random_end is None or frozen_end is None:
        return f"random reweighting was not measured on {unit}"
    return f"{_pct(random_end)} on {unit} against {_pct(frozen_end)} for the untouched graph"


def sentences(
    north: Mapping[str, object], meta: Mapping[str, object], clean: Mapping[str, object] | None = None
) -> list[dict[str, object]]:
    clean = clean or {}
    out: list[dict[str, object]] = []

    def add(key: str, text: str, sources: Sequence[str]) -> None:
        out.append({"key": key, "text": text, "sources": list(sources)})

    seeds = _ints(north.get("seeds"))
    held = _ints(meta.get("held_out_questions"))
    metaqa_clause = (
        f"on MetaQA, a public movie knowledge graph ({_as_int(meta.get('kb_lines')) or 0:,} triples, {_span(held)} "
        f"held-out questions per seed, {len(held)} seeds, half the triples withheld)"
        if meta
        else "MetaQA, a public movie knowledge graph, has not been run yet"
    )
    add(
        "setup",
        f"I tested TrailMend on {len(seeds) or '—'} generated company graphs "
        f"({_span(_ints(north.get('nodes')))} nodes, {_span(_ints(north.get('planted_faults')))} planted faults each) "
        f"and {metaqa_clause}.",
        ("dataset_summary_v2.json", "metaqa/dataset_s*.json"),
    )
    if clean:
        add(
            "comparability",
            replication_facts.comparability(clean),
            ("curve_v2_clean.jsonl", "replication_v2_clean.json"),
        )
    elif any(row.get("comparable") is False for row in _file("paired_v2_unweighted")):
        add(
            "comparability",
            "The company-graph results are provisional: the extension did not reproduce run 2's frozen baseline, "
            "whose recorded paths include edges outside the intended G0 graph. The historical scores and verdicts "
            "remain published; this is not a clean replication.",
            ("paired_v2_unweighted.json",),
        )
    rounds = _as_int(north.get("rounds"))
    add(
        "gain",
        f"After {rounds if rounds is not None else '—'} rounds of learning from its own answers, "
        f"{_gain(north, 'accuracy_round_0', 'accuracy_round_n', 'held-out accuracy on the company graphs')}"
        + (
            f", and {_gain(meta, 'hits_round_0', 'hits_round_n', 'held-out Hits@1 on MetaQA')}."
            if meta
            else "; MetaQA has not been run."
        ),
        ("curve_v2.jsonl", "paired_v2.json", "curve_metaqa.jsonl", "paired_metaqa.json"),
    )
    add(
        "captured",
        f"It captured {_pct(_as_float(north.get('captured_share')), 0)} of the gain that perfect repairs would give on "
        f"the company graphs" + (f" and {_pct(_as_float(meta.get('captured_share')), 0)} on MetaQA." if meta else "."),
        ("captured_share_v2.json", "oracle_v2.json", "captured_share_metaqa.json", "oracle_metaqa.json"),
    )
    wins = (_as_int(north.get("random_reweight_seeds_beating_frozen")) or 0) + (
        _as_int(meta.get("random_reweight_seeds_beating_frozen")) or 0
    )
    verdict = (
        "and random reweighting did not significantly beat the untouched graph on any seed"
        if wins == 0
        else f"though it beat the untouched graph on {wins} seed(s), so part of the gain is perturbation"
    )
    add(
        "random_control",
        "Random reweighting, matched to its own targeted plan's number and size of cost changes each "
        f"round, ends at {_control(north, 'the company graphs')}"
        + (f", and at {_control(meta, 'MetaQA')}" if meta else "")
        + f", {verdict}. The random arm reads no new documents; gap-fill alone, with no reweighting, reaches "
        f"{_pct(_as_float(north.get('gapfill_only_round_n')))} on the company graphs.",
        ("curve_v2.jsonl", "paired_v2.json", "changes_v2.json", "curve_metaqa.jsonl", "paired_metaqa.json"),
    )
    unweighted_end = _as_float(north.get("unweighted_round_n"))
    weighted_end = _as_float(north.get("accuracy_round_n"))
    clean_clause = replication_facts.unweighted_clause(clean)
    if clean_clause is not None:
        unweighted = clean_clause
    elif unweighted_end is None or weighted_end is None:
        unweighted = "the unweighted-search arm has not been run"
    else:
        gap = 100 * (weighted_end - unweighted_end)
        side = "below" if gap > 0 else "above"
        unweighted = (
            f"with unweighted search the same loop goes from {_pct(_as_float(north.get('unweighted_round_0')))} to "
            f"{_pct(unweighted_end)}, {abs(gap):.1f} points {side} the loop that searches on cost "
            "(provisional comparison: the frozen baselines differ, "
            "so the difference cannot be attributed to search alone)"
        )
    add(
        "plain_and_unweighted",
        f"A plain document store over the same corpus stays flat at {_pct(_as_float(north.get('plain_store')))}"
        + (f" ({_pct(_as_float(meta.get('plain_store')))} on MetaQA)" if meta else "")
        + f" because it has no links for the loop to repair, and {unweighted}.",
        ("plain_store_v2.json", "plain_store_metaqa.json", "curve_v2_unweighted.jsonl")
        + (("curve_v2_clean.jsonl", "replication_v2_clean.json") if clean else ()),
    )
    north_wrong, _ = _wrong_change(_as_int(north.get("wrong_round_0")), _as_int(north.get("wrong_round_n")))
    meta_wrong, _ = _wrong_change(_as_int(meta.get("wrong_round_0")), _as_int(meta.get("wrong_round_n")))
    kept = (_as_int(north.get("still_right_at_round_n")) or 0) + (_as_int(meta.get("still_right_at_round_n")) or 0)
    right = (_as_int(north.get("right_at_round_0")) or 0) + (_as_int(meta.get("right_at_round_0")) or 0)
    broken = (_as_int(north.get("breaks")) or 0) + (_as_int(meta.get("breaks")) or 0)
    traced = (_as_int(north.get("breaks_traced")) or 0) + (_as_int(meta.get("breaks_traced")) or 0)
    trace = (
        "with every break along the way traced to a receipt"
        if broken == traced
        else f"with {traced:,} of the {broken:,} breaks along the way traced to a receipt"
    )
    add(
        "wrong_and_kept",
        f"Wrong answers {north_wrong} on the company graphs"
        + (f" and {meta_wrong} on MetaQA" if meta else "")
        + f", and {kept:,} of {right:,} held-out questions that were right at the start were still right at the end, "
        f"{trace}.",
        (
            "curve_v2.jsonl",
            "curve_metaqa.jsonl",
            "non_regression_v2.json",
            "non_regression_metaqa.json",
            "runs/*/heldout.jsonl",
        ),
    )
    ingested, g0 = _as_int(north.get("edges_ingested")), _as_int(north.get("g0_edges"))
    if ingested is None or not g0:
        closing = "How much the graph grew was not measured."
    else:
        closing = (
            f"The graph did get bigger, but only by reading: the company graphs gained {ingested:,} links "
            f"({100 * ingested / g0:.1f}%), each from a withheld document and each under a receipt"
            + (
                f", and MetaQA read back {_as_int(meta.get('triples_ingested')) or 0:,} withheld triples"
                if meta
                else ""
            )
            + ". Reweighting and quarantine also change the graph; "
            "these results do not isolate their gain from gap-fill."
        )
    add("closing", closing, ("curve_v2.jsonl", "dataset_summary_v2.json", "curve_metaqa.jsonl"))
    return out


def write() -> tuple[Path, str]:
    rows = _jsonl(curve.CURVE_V2)
    if rows:
        evidence.write(evidence.make("dataset_summary_v2", SUMMARY_DESIGN, dataset_summary(_seeds(rows))))
    north, meta, clean = northwind_facts(), metaqa_facts(), replication_facts.facts()
    lines = sentences(north, meta, clean)
    payload = evidence.make("benchmark", DESIGN, lines)
    path = evidence.write(payload)
    facts = {"northwind_run_2": north, "metaqa": meta} | ({"northwind_clean_replication": clean} if clean else {})
    (EVIDENCE / "benchmark_facts.json").write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, " ".join(str(line["text"]) for line in lines)


if __name__ == "__main__":
    _path, _paragraph = write()
    print(_paragraph)
    print(f"{_path} sha256={evidence.digest(_path)}")
