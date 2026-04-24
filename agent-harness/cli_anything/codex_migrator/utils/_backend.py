from __future__ import annotations

import platform
import subprocess
import time
from pathlib import Path
from typing import Iterable, List


def codex_cli_path() -> Path:
    return Path("/Applications/Codex.app/Contents/Resources/codex")


def refresh_codex_roots(roots: Iterable[str], delay_seconds: float = 0.8) -> dict:
    cli_path = codex_cli_path()
    existing_roots: List[str] = [str(Path(root)) for root in roots if Path(root).exists()]

    if platform.system() != "Darwin":
        return {
            "ok": False,
            "reason": "Codex Desktop refresh is only implemented for macOS.",
            "roots": existing_roots,
        }

    if not cli_path.exists():
        return {
            "ok": False,
            "reason": f"Codex Desktop CLI not found at {cli_path}.",
            "roots": existing_roots,
        }

    launched = []
    errors = []
    for root in existing_roots:
        result = subprocess.run(
            [str(cli_path), "app", root],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            launched.append(root)
        else:
            errors.append(
                {
                    "root": root,
                    "returncode": result.returncode,
                    "stderr": result.stderr.strip(),
                }
            )
        time.sleep(delay_seconds)

    return {
        "ok": not errors,
        "launched": launched,
        "errors": errors,
        "restart_required": True,
    }
