import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

from trailmend.core.config import config_digest
from trailmend.data import dataset
from trailmend.data.documents import to_json as documents_json
from trailmend.data.faultmodel import V1
from trailmend.data.faultmodel import to_json as faults_json
from trailmend.eval import evidence, target
from trailmend.eval.splits import to_json as split_json

CONFIG = Path("config/mend.toml")
COMPOSE = target.COMPOSE
hydradb_image = target.hydradb_image


def commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def tree_is_clean() -> bool:
    return not subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, check=True
    ).stdout.strip()


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def dataset_digests(seed: int, data_version: str = V1) -> dict[str, str]:
    built = dataset.build(seed, data_version=data_version)
    return {
        "documents": sha256_of(documents_json(built.documents)),
        "faults": sha256_of(faults_json(built.ingested.faults)),
        "split": sha256_of(split_json(built.split)),
    }


MEASURED_SUFFIXES = frozenset({".json", ".jsonl", ".svg"})
MANIFESTS = frozenset({"run_manifest.json", "run_manifest_v2.json"})


def evidence_digests(directory: Path = evidence.EVIDENCE_DIR) -> dict[str, str]:
    files = sorted(
        p
        for p in directory.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.name not in MANIFESTS and p.suffix in MEASURED_SUFFIXES
    )
    return {p.name: evidence.digest(p) for p in files}


def _measured_on(path: Path) -> object:
    if path.suffix == ".jsonl":
        seen: list[object] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row: object = json.loads(line)
            where = cast("dict[str, object]", row).get("hydradb") if isinstance(row, dict) else None
            if where is not None and where not in seen:
                seen.append(where)
        return seen or None
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    return cast("dict[str, object]", payload).get("measured_on") if isinstance(payload, dict) else None


def hydradb_per_file(directory: Path = evidence.EVIDENCE_DIR) -> dict[str, object]:
    out: dict[str, object] = {}
    for path in sorted(directory.iterdir()):
        if (
            not path.is_file()
            or path.name.startswith(".")
            or path.name in MANIFESTS
            or path.suffix not in {".json", ".jsonl"}
        ):
            continue
        out[path.name] = _measured_on(path)
    return out


def build(seeds: tuple[int, ...], run_id: str, data_version: str = V1) -> dict[str, object]:
    return {
        "run_id": run_id,
        "code_commit": commit(),
        "working_tree_clean": tree_is_clean(),
        "config": {"path": str(CONFIG), "sha256": config_digest(CONFIG), "text": CONFIG.read_text()},
        "hydradb": hydradb_image(),
        "hydradb_per_evidence_file": hydradb_per_file(),
        "data_version": data_version,
        "seeds": {str(seed): dataset_digests(seed, data_version) for seed in seeds},
        "evidence_sha256": evidence_digests(),
    }


def write(
    seeds: tuple[int, ...],
    run_id: str,
    directory: Path = evidence.EVIDENCE_DIR,
    name: str = "run_manifest.json",
    data_version: str = V1,
) -> Path:
    if name not in MANIFESTS:
        raise ValueError(f"a manifest is written as one of {sorted(MANIFESTS)}, not {name!r}")
    path = directory / name
    path.write_text(json.dumps(build(seeds, run_id, data_version), indent=2, sort_keys=True) + "\n")
    return path
