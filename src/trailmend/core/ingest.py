from math import log

INGEST_BASE = 1.0
MIN_SUPPORT = 1


def ingest_cost(support: int) -> float:
    if support < MIN_SUPPORT:
        raise ValueError(f"an ingested edge is asserted by at least one document, got {support}")
    return INGEST_BASE / (1.0 + log(support))
