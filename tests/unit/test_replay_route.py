from types import SimpleNamespace
from typing import cast

from fastapi import Request

from trailmend.api.routes_replay import replay_run
from trailmend.data import dataset
from trailmend.data.faultmodel import V2

ROUNDS = 6
KINDS = {"reweight", "quarantine", "gapfill", "promote"}


def _request() -> Request:
    built = dataset.build(1, data_version=V2)
    live = SimpleNamespace(built=built, names={node.id: node.name for node in built.graph.nodes})
    return cast("Request", SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(live=live))))


def test_the_replay_gives_every_recorded_round_with_counts_and_named_example_receipts() -> None:
    body = replay_run("northwind", 1, _request())
    assert body["available"] is True
    rounds = cast("list[dict[str, object]]", body["rounds"])
    assert [r["round"] for r in rounds] == list(range(ROUNDS))
    for row in rounds:
        for arm in ("full_v2", "frozen"):
            held = cast("dict[str, int]", row[arm])
            assert 0 <= held["correct"] <= held["n"]
        for count in ("reweights", "quarantines", "gapfills", "promotions"):
            assert isinstance(row[count], int)
        examples = cast("list[dict[str, object]]", row["examples"])
        assert len(examples) <= 6
        for example in examples:
            assert example["kind"] in KINDS
            edge = cast("dict[str, str]", example["edge"])
            assert edge["src_name"]
            assert edge["dst_name"]
            assert edge["truth"]
            assert edge["src"].isdigit()
    frozen = {cast("dict[str, int]", r["frozen"])["correct"] for r in rounds}
    assert len(frozen) == 1
