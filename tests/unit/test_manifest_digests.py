from pathlib import Path

from trailmend.eval import manifest


def test_the_manifest_hashes_every_measured_file_and_not_itself(tmp_path: Path) -> None:
    (tmp_path / "curve.jsonl").write_text('{"a": 1}\n')
    (tmp_path / "mechanisms.json").write_text("{}")
    (tmp_path / "curve.svg").write_text("<svg/>")
    (tmp_path / "run_manifest.json").write_text("{}")

    digests = manifest.evidence_digests(tmp_path)

    assert set(digests) == {"curve.jsonl", "mechanisms.json", "curve.svg"}
    assert all(len(value) == 64 for value in digests.values())


def test_prose_in_the_evidence_directory_is_not_hashed_as_a_measurement(tmp_path: Path) -> None:
    (tmp_path / "curve.jsonl").write_text('{"a": 1}\n')
    (tmp_path / "posts.md").write_text("a draft that is edited after the run")
    (tmp_path / ".gitkeep").write_text("")
    (tmp_path / ".measuring.json").write_text('{"pid": 123}')

    assert set(manifest.evidence_digests(tmp_path)) == {"curve.jsonl"}
