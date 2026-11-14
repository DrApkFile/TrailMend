import hashlib
import re

_KEY = re.compile(r"^[a-z][a-z0-9_]*:[a-z0-9][a-z0-9_\-.]*$")
_ID_BITS = 62


def entity_id(natural_key: str) -> int:
    if not _KEY.fullmatch(natural_key):
        raise ValueError(f"natural key must look like 'kind:slug', got {natural_key!r}")
    digest = hashlib.blake2b(natural_key.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") >> (64 - _ID_BITS)


def edge_id(rel_type: str, src: int, dst: int) -> int:
    return entity_id(f"edge:{rel_type.lower()}-{src}-{dst}")
