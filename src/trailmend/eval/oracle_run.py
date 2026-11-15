import sys

from trailmend.core.config import load_search_config
from trailmend.data import dataset
from trailmend.data.faultmodel import V2
from trailmend.eval import evidence, measuring, target
from trailmend.eval.diagnose import ORACLE_DESIGN, RECOVERY_DESIGN, ladder, recovery_row
from trailmend.eval.run import CONFIG
from trailmend.eval.session import client_from_settings
from trailmend.graph.reset import reset_to_ingested
from trailmend.loop.evaluate import judge_all, score
from trailmend.search.seed import build_index
from trailmend.settings import load_settings

SEEDS: tuple[int, ...] = (1, 7, 42)


def main(seeds: tuple[int, ...] = SEEDS, data_version: str = V2) -> int:
    search = load_search_config(CONFIG)
    where = target.describe(str(load_settings().hydra_url))
    oracle_rows: list[dict[str, object]] = []
    recovery_rows: list[dict[str, object]] = []
    measuring.acquire(f"oracle-{data_version}")
    try:
        with client_from_settings() as client:
            client.require_writable()
            for seed in seeds:
                built = dataset.build(seed, data_version=data_version)
                pool = tuple((e.src, e.rel_type.value, e.dst) for e in built.ingested.pool)
                print(f"seed {seed} on data {data_version}", flush=True)
                reset_to_ingested(client, built.graph, pool, built.support)
                index = build_index(built.graph.nodes)
                train = [t.question for t in built.split.train]
                at_zero = judge_all(client, index, train, search)
                print(f"  round 0 train: {score(at_zero).correct}/{len(train)}", flush=True)
                recovery_rows.append(recovery_row(seed, built, at_zero))
                oracle_rows.extend(ladder(client, built, search))
    finally:
        measuring.release()
    for claim, design, rows in (
        (f"oracle_{data_version}", ORACLE_DESIGN, oracle_rows),
        (f"fault_recoverability_{data_version}", RECOVERY_DESIGN, recovery_rows),
    ):
        path = evidence.write(evidence.make(claim, design, rows, measured_on=where))
        print(f"{path} sha256={evidence.digest(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(tuple(int(a) for a in sys.argv[1:]) or SEEDS))
