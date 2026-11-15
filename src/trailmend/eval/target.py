import re
from pathlib import Path
from urllib.parse import urlsplit

COMPOSE = Path("docker-compose.yml")
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0"})
_DIGEST = re.compile(r"image:\s*(?P<image>\S+)@(?P<digest>sha256:[0-9a-f]{64})")


def hydradb_image(path: Path = COMPOSE) -> dict[str, str]:
    found = _DIGEST.search(path.read_text(encoding="utf-8"))
    if found is None:
        raise ValueError(f"{path} does not pin the hydradb image to a digest")
    return {"image": found.group("image"), "digest": found.group("digest")}


def describe(url: str, compose: Path = COMPOSE) -> dict[str, object]:
    host = urlsplit(url).hostname or ""
    if host in LOCAL_HOSTS:
        pinned = hydradb_image(compose)
        return {"kind": "local", "host": host, "image": pinned["image"], "digest": pinned["digest"]}
    return {
        "kind": "remote",
        "host": host,
        "image": None,
        "digest": None,
        "note": "a hosted HydraDB; its image digest is whatever that service runs and is not readable from here",
    }
