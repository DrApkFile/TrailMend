import json
from collections.abc import Mapping

from fastapi import APIRouter, Request

from trailmend.api.state import Live
from trailmend.data.faultmodel import V2
from trailmend.errors import ErrorCode, TrailMendError
from trailmend.eval import evidence, replay

router = APIRouter()
DATASETS: tuple[str, ...] = ("northwind",)
PLANTED_WRONG = "planted_wrong"
TRUE = "true"
NOT_IN_TRUTH = "not_in_truth"
SHORTCUT = "shortcut"
SHORTCUT_PREFIX = "SC_"


def _verdicts(live: Live) -> dict[tuple[int, str, int], str]:
    truth = {(e.src, e.rel_type.value, e.dst): TRUE for e in live.built.truth.edges}
    wrong = {(w.src, w.rel_type.value, w.wrong_dst): PLANTED_WRONG for w in live.built.ingested.faults.wrong_edges}
    return truth | wrong


def _true_dst(live: Live) -> dict[tuple[int, str, int], int]:
    return {(w.src, w.rel_type.value, w.wrong_dst): w.true_dst for w in live.built.ingested.faults.wrong_edges}


def _named(
    example: Mapping[str, object],
    names: Mapping[int, str],
    verdicts: Mapping[tuple[int, str, int], str],
    true_dst: Mapping[tuple[int, str, int], int],
) -> dict[str, object]:
    edge = example["edge"]
    assert isinstance(edge, dict)
    src, rel, dst = int(edge["src"]), str(edge["rel_type"]), int(edge["dst"])  # pyright: ignore[reportUnknownArgumentType]
    return dict(example) | {
        "edge": {
            "src": str(src),
            "dst": str(dst),
            "rel_type": rel,
            "src_name": names.get(src, str(src)),
            "dst_name": names.get(dst, str(dst)),
            "truth": SHORTCUT if rel.startswith(SHORTCUT_PREFIX) else verdicts.get((src, rel, dst), NOT_IN_TRUTH),
        }
        | (
            {"true_dst_name": names.get(true_dst[(src, rel, dst)], str(true_dst[(src, rel, dst)]))}
            if (src, rel, dst) in true_dst
            else {}
        )
    }


@router.get("/v1/replay/{dataset}/{seed}")
def replay_run(dataset: str, seed: int, request: Request) -> dict[str, object]:
    live: Live = request.app.state.live
    if dataset not in DATASETS:
        raise TrailMendError(ErrorCode.INVALID_REQUEST, f"no replay for dataset {dataset}")
    if live.built.data_version != V2:
        raise TrailMendError(
            ErrorCode.INVALID_REQUEST, f"the replay is of {V2} data, the app serves {live.built.data_version}"
        )
    if seed != live.built.seed:
        raise TrailMendError(ErrorCode.INVALID_REQUEST, f"names are built for seed {live.built.seed}, not {seed}")
    path = replay.path_for(dataset, seed)
    if not path.exists():
        return {"dataset": dataset, "seed": seed, "available": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    names = {node.id: node.name for node in live.built.truth.nodes} | live.names
    verdicts = _verdicts(live)
    true_dst = _true_dst(live)
    rounds = [
        row | {"examples": [_named(example, names, verdicts, true_dst) for example in row["examples"]]}
        for row in payload["rounds"]
    ]
    return payload | {"available": True, "sha256": evidence.digest(path), "rounds": rounds}
