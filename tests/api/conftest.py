import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from trailmend.api.app import app
from trailmend.graph.client import HydraClient

URL = os.environ.get("TRAILMEND_HYDRA_URL", "http://127.0.0.1:8443")
TOKEN = os.environ.get("TRAILMEND_HYDRA_TOKEN", "local-development-token-32-bytes")
ADMIN = "test-admin-token-not-a-real-secret"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    probe = HydraClient(URL, TOKEN, "default", "cell-0", 10.0)
    healthy = probe.is_healthy()
    probe.close()
    if not healthy:
        pytest.skip(f"HydraDB not reachable at {URL}")
    os.environ["TRAILMEND_HYDRA_URL"] = URL
    os.environ["TRAILMEND_HYDRA_TOKEN"] = TOKEN
    os.environ["TRAILMEND_ADMIN_TOKEN"] = ADMIN
    with TestClient(app) as started:
        yield started
