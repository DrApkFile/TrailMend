import os
from collections.abc import Iterator

import pytest

from trailmend.eval import measuring
from trailmend.graph.client import HydraClient

URL = os.environ.get("TRAILMEND_HYDRA_URL", "http://127.0.0.1:8443")
TOKEN = os.environ.get("TRAILMEND_HYDRA_TOKEN", "local-development-token-32-bytes")


@pytest.fixture
def hydra() -> Iterator[HydraClient]:
    client = HydraClient(URL, TOKEN, "default", "cell-0", 30.0)
    if not client.is_healthy():
        client.close()
        pytest.skip(f"HydraDB not reachable at {URL}")
    busy = measuring.skip_reason()
    if busy is not None:
        client.close()
        pytest.skip(busy)
    yield client
    client.close()
