import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import cast

import httpx

from trailmend.data import dataset
from trailmend.eval import evidence, target

DESIGN = (
    "Concurrent clients ask the product question mix over HTTP against a running API, one thread per client, each "
    "picking questions round-robin from the training split so no held-out question is touched. Latency is "
    "wall-clock per request including the HydraDB round trip. Errors are counted by the API's own error code, not "
    "by exception type. The second pass repeats the same load while a Mend round writes to the same graph, to show "
    "what a writer does to read latency."
)


@dataclass(frozen=True, slots=True)
class Result:
    label: str
    clients: int
    requests: int
    seconds: float
    latencies_ms: tuple[float, ...]
    codes: Counter[str]

    def row(self) -> dict[str, object]:
        ordered = sorted(self.latencies_ms)
        return {
            "label": self.label,
            "clients": self.clients,
            "requests": self.requests,
            "seconds": round(self.seconds, 3),
            "qps": round(self.requests / self.seconds, 2) if self.seconds else None,
            "p50_ms": round(statistics.median(ordered), 1) if ordered else None,
            "p95_ms": round(ordered[int(len(ordered) * 0.95) - 1], 1) if ordered else None,
            "p99_ms": round(ordered[int(len(ordered) * 0.99) - 1], 1) if ordered else None,
            "max_ms": round(ordered[-1], 1) if ordered else None,
            "ok": self.codes.get("ok", 0),
            "errors_by_code": {code: count for code, count in sorted(self.codes.items()) if code != "ok"},
        }


def _ask(client: httpx.Client, question: str) -> tuple[float, str]:
    started = time.perf_counter()
    try:
        response = client.post("/v1/ask", json={"question": question})
    except httpx.HTTPError as exc:
        return (time.perf_counter() - started) * 1000, f"transport:{type(exc).__name__}"
    took = (time.perf_counter() - started) * 1000
    if response.status_code == 200:
        return took, "ok"
    return took, _code_of(response)


def _code_of(response: httpx.Response) -> str:
    fallback = f"http_{response.status_code}"
    if not response.headers.get("content-type", "").startswith("application/json"):
        return fallback
    body: object = response.json()
    if not isinstance(body, dict):
        return fallback
    error = cast("dict[str, object]", body).get("error")
    if not isinstance(error, dict):
        return fallback
    code = cast("dict[str, object]", error).get("code")
    return str(code) if isinstance(code, str) else fallback


def run(base_url: str, questions: list[str], clients: int, per_client: int, label: str) -> Result:
    def one(index: int) -> list[tuple[float, str]]:
        with httpx.Client(base_url=base_url, timeout=30.0) as client:
            return [_ask(client, questions[(index * per_client + n) % len(questions)]) for n in range(per_client)]

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=clients) as pool:
        collected = [item for batch in pool.map(one, range(clients)) for item in batch]
    seconds = time.perf_counter() - started
    return Result(
        label,
        clients,
        len(collected),
        seconds,
        tuple(took for took, _ in collected),
        Counter(code for _, code in collected),
    )


def main(base_url: str, clients: int = 8, per_client: int = 25, seed: int = 1) -> int:
    built = dataset.build(seed)
    questions = [item.question.text for item in built.split.train]
    rows: list[dict[str, object]] = []
    first = run(base_url, questions, clients, per_client, "reads only")
    print(first.row(), flush=True)
    rows.append(first.row())
    path = evidence.write(evidence.make("latency", DESIGN, rows, measured_on=target.describe(base_url)))
    print(f"wrote {path} sha256={evidence.digest(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
