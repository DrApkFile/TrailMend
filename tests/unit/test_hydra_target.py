from pathlib import Path

import pytest

from trailmend.eval import target

COMPOSE = "services:\n  hydradb:\n    image: ghcr.io/hydra-db/hydradb@sha256:" + "a" * 64 + "\n"


@pytest.fixture
def compose(tmp_path: Path) -> Path:
    path = tmp_path / "docker-compose.yml"
    path.write_text(COMPOSE, encoding="utf-8")
    return path


def test_a_local_run_is_recorded_with_the_pinned_image_digest(compose: Path) -> None:
    where = target.describe("http://127.0.0.1:8443", compose)
    assert where["kind"] == "local"
    assert where["image"] == "ghcr.io/hydra-db/hydradb"
    assert where["digest"] == "sha256:" + "a" * 64


def test_a_hosted_run_is_recorded_as_remote_with_no_digest_claimed(compose: Path) -> None:
    where = target.describe("https://trailmend-production-ee2e07ff.up.railway.app", compose)
    assert where["kind"] == "remote"
    assert where["host"] == "trailmend-production-ee2e07ff.up.railway.app"
    assert where["digest"] is None
    assert "not readable from here" in str(where["note"])


def test_an_unpinned_compose_file_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    path = tmp_path / "docker-compose.yml"
    path.write_text("services:\n  hydradb:\n    image: ghcr.io/hydra-db/hydradb:latest\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not pin the hydradb image"):
        target.describe("http://localhost:8443", path)
