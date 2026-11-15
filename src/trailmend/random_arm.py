from random import Random


def arm_rng(seed: int, round_index: int) -> Random:
    return Random(seed * 1_000_003 + round_index)
