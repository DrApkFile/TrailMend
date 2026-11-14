import hashlib
import json
import re
import subprocess
from pathlib import Path

from trailmend.core.config import config_digest
from trailmend.data import dataset
from trailmend.data.documents import to_json as documents_json
from trailmend.data.faultmodel import to_json as faults_json
from trailmend.eval import evidence
from trailmend.eval.splits import to_json as split_json

CONFIG = Path("config/mend.toml")
COMPOSE = Path("docker-compose.yml")
_DIGEST = re.compile(r"image:\s*(?P<image>\S+)@(?P<digest>sha256:[0-9a-f]{64})")


def commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def tree_is_clean() -> bool:
    return not subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, check=True
    ).stdout.strip()


def hydradb_image(path: Path = COMPOSE) -> dict[str, str]:
    found = _DIGEST.search(path.read_text())
    if found is None:
        raise ValueError(f"{path} does not pin the hydradb image to a digest")
    return {"image": found.group("image"), "digest": found.group("digest")}


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def dataset_digests(seed: int) -> dict[str, str]:
    built = dataset.build(seed)
    return {
        "documents": sha256_of(documents_json(built.documents)),
        "faults": sha256_of(faults_json(built.ingested.faults)),
        "split": sha256_of(split_json(built.split)),
    }


def evidence_digests(directory: Path = evidence.EVIDENCE_DIR) -> dict[str, str]:
    files = sorted(p for p in directory.iterdir() if p.is_file() and p.name != "run_manifest.json")
    return {p.name: evidence.digest(p) for p in files}


def build(seeds: tuple[int, ...], run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "code_commit": commit(),
        "working_tree_clean": tree_is_clean(),
        "config": {"path": str(CONFIG), "sha256": config_digest(CONFIG), "text": CONFIG.read_text()},
        "hydradb": hydradb_image(),
        "seeds": {str(seed): dataset_digests(seed) for seed in seeds},
        "evidence_sha256": evidence_digests(),
    }


def write(seeds: tuple[int, ...], run_id: str, directory: Path = evidence.EVIDENCE_DIR) -> Path:
    path = directory / "run_manifest.json"
    path.write_text(json.dumps(build(seeds, run_id), indent=2, sort_keys=True) + "\n")
    return path
