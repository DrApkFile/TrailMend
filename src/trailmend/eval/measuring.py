import json
import os
from pathlib import Path
from typing import cast

from trailmend.eval.evidence import now_utc

LOCK = Path("evidence/.measuring.json")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def holder(path: Path = LOCK) -> dict[str, object] | None:
    if not path.exists():
        return None
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    claim = cast("dict[str, object]", payload)
    pid = claim.get("pid")
    if isinstance(pid, int) and not isinstance(pid, bool) and not _alive(pid):
        return None
    return claim


def acquire(run_id: str, path: Path = LOCK) -> Path:
    held = holder(path)
    if held is not None:
        raise RuntimeError(
            f"a measured run is already writing to the graph: {held.get('run_id')} as pid {held.get('pid')} "
            f"since {held.get('started_at')}. Wait for it, or delete {path} if that process is gone."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"run_id": run_id, "pid": os.getpid(), "started_at": now_utc()}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def release(path: Path = LOCK) -> None:
    path.unlink(missing_ok=True)


def skip_reason(path: Path = LOCK) -> str | None:
    held = holder(path)
    if held is None:
        return None
    return (
        f"a measured run ({held.get('run_id')}, pid {held.get('pid')}) is writing to this graph; "
        "tests that write would contaminate it"
    )
