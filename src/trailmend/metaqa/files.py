import hashlib
import json
import sys
from pathlib import Path

from trailmend.metaqa.kb import DATA_DIR, KB_FILE
from trailmend.metaqa.questions import QUESTION_FILES

MANIFEST = Path("data/external/metaqa.manifest.json")
LICENCE_FILE = "LICENSE.txt"
SOURCE = "https://github.com/yuyuz/MetaQA"
CITATION = (
    "Zhang, Dai, Kozareva, Smola, Song. Variational Reasoning for Question Answering with Knowledge Graph. AAAI 2018."
)


def _entry(root: Path, name: str, role: dict[str, object]) -> dict[str, object]:
    path = root / name
    if not path.exists():
        raise FileNotFoundError(f"MetaQA file missing: {path}")
    raw = path.read_bytes()
    return {"file": name, "lines": raw.count(b"\n"), "sha256": hashlib.sha256(raw).hexdigest()} | role


def inventory(root: Path = DATA_DIR) -> dict[str, object]:
    files = [_entry(root, KB_FILE, {"role": "kb"}), _entry(root, LICENCE_FILE, {"role": "licence"})]
    for (hop, split), (questions, qtypes) in sorted(QUESTION_FILES.items()):
        files.append(_entry(root, questions, {"role": "questions", "hop": hop, "split": split}))
        files.append(_entry(root, qtypes, {"role": "qtypes", "hop": hop, "split": split}))
    return {"dataset": "MetaQA (vanilla)", "source": SOURCE, "citation": CITATION, "files": files}


def write_manifest(root: Path = DATA_DIR, path: Path = MANIFEST) -> Path:
    path.write_text(json.dumps(inventory(root), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def verify(root: Path = DATA_DIR, path: Path = MANIFEST) -> None:
    pinned = json.loads(path.read_text(encoding="utf-8"))
    found = inventory(root)
    if found["files"] != pinned["files"]:
        raise ValueError(f"the MetaQA files under {root} do not match {path}")


def manifest_digest(path: Path = MANIFEST) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    if "--write" in sys.argv[1:]:
        print(write_manifest())
    verify()
    print(f"{DATA_DIR} matches {MANIFEST} sha256={manifest_digest()}")
