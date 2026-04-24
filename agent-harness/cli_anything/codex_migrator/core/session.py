from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict


@contextmanager
def _locked_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except ImportError:
            pass
        handle.seek(0)
        yield handle
        handle.flush()
        os.fsync(handle.fileno())
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except ImportError:
            pass


def default_session_path() -> Path:
    override = os.environ.get("CODEX_MIGRATOR_SESSION")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".codex-migrator" / "session.json"


def load_session(path: Path | None = None) -> Dict[str, Any]:
    session_path = path or default_session_path()
    if not session_path.exists():
        return {"history": []}
    with _locked_file(session_path) as handle:
        raw = handle.read().strip()
        if not raw:
            return {"history": []}
        return json.loads(raw)


def save_session(data: Dict[str, Any], path: Path | None = None) -> None:
    session_path = path or default_session_path()
    with _locked_file(session_path) as handle:
        handle.seek(0)
        handle.truncate()
        json.dump(data, handle, indent=2)
        handle.write("\n")


def remember(event: Dict[str, Any], path: Path | None = None) -> None:
    data = load_session(path)
    history = data.setdefault("history", [])
    history.append(event)
    data["last_event"] = event
    save_session(data, path)
