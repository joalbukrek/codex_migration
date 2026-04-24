from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


GLOBAL_STATE = ".codex-global-state.json"
GLOBAL_STATE_BAK = ".codex-global-state.json.bak"
SQLITE_STATE = "state_5.sqlite"
HOME_RE = re.compile(r"/Users/[^/\s\"']+")


def expand_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def expand_user_string(value: str | Path) -> str:
    return str(Path(value).expanduser())


def home_from_username(username: str) -> str:
    clean = username.strip().strip("/")
    if not clean:
        raise ValueError("new username cannot be empty")
    if "/" in clean:
        raise ValueError("new username should be a username only, not a path")
    return f"/Users/{clean}"


def resolve_new_home(new_home: str | None = None, new_username: str | None = None) -> str:
    if new_home and new_username:
        raise ValueError("Pass either --new-home or --new-username, not both.")
    if new_username:
        return home_from_username(new_username)
    return expand_user_string(new_home or Path.home())


def default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def _now_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _replace_deep(value: Any, old_home: str, new_home: str) -> Any:
    if isinstance(value, str):
        return value.replace(old_home, new_home)
    if isinstance(value, list):
        return [_replace_deep(item, old_home, new_home) for item in value]
    if isinstance(value, dict):
        return {
            str(key).replace(old_home, new_home): _replace_deep(child, old_home, new_home)
            for key, child in value.items()
        }
    return value


def _uniq(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        if not value:
            continue
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _read_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _text_count(path: Path, needle: str) -> int:
    if not path.exists() or not needle:
        return 0
    try:
        return path.read_text(encoding="utf-8", errors="ignore").count(needle)
    except OSError:
        return 0


def _sqlite_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%'"
    ).fetchall()
    return [row[0] for row in rows]


def _sqlite_text_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    columns = []
    for row in conn.execute(f"pragma table_info({_quote_identifier(table)})"):
        name = row[1]
        declared_type = (row[2] or "").upper()
        if "TEXT" in declared_type or declared_type == "":
            columns.append(name)
    return columns


def _sqlite_count_refs(conn: sqlite3.Connection, old_home: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    like_value = f"%{old_home}%"
    for table in _sqlite_tables(conn):
        for column in _sqlite_text_columns(conn, table):
            table_q = _quote_identifier(table)
            column_q = _quote_identifier(column)
            try:
                value = conn.execute(
                    f"select count(*) from {table_q} where coalesce({column_q}, '') like ?",
                    (like_value,),
                ).fetchone()[0]
            except sqlite3.DatabaseError:
                continue
            if value:
                counts[f"{table}.{column}"] = int(value)
    return counts


def _thread_cwd_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    tables = set(_sqlite_tables(conn))
    if "threads" not in tables:
        return {}
    columns = {row[1] for row in conn.execute('pragma table_info("threads")')}
    if "cwd" not in columns:
        return {}
    where = ""
    if "archived" in columns:
        where = " where archived=0"
    rows = conn.execute(f'select cwd, count(*) from "threads"{where} group by cwd order by cwd').fetchall()
    return {row[0] or "": int(row[1]) for row in rows}


def _thread_count(conn: sqlite3.Connection) -> Dict[str, int]:
    tables = set(_sqlite_tables(conn))
    if "threads" not in tables:
        return {"total": 0, "active": 0}
    columns = {row[1] for row in conn.execute('pragma table_info("threads")')}
    total = int(conn.execute('select count(*) from "threads"').fetchone()[0])
    if "archived" in columns:
        active = int(conn.execute('select count(*) from "threads" where archived=0').fetchone()[0])
    else:
        active = total
    return {"total": total, "active": active}


def _collect_roots_from_state(state: Dict[str, Any]) -> List[str]:
    roots: List[str] = []
    for key in ("electron-saved-workspace-roots", "project-order", "active-workspace-roots"):
        value = state.get(key)
        if isinstance(value, list):
            roots.extend(str(item) for item in value if isinstance(item, str))
    hints = state.get("thread-workspace-root-hints")
    if isinstance(hints, dict):
        roots.extend(str(item) for item in hints.values() if isinstance(item, str))
    labels = state.get("electron-workspace-root-labels")
    if isinstance(labels, dict):
        roots.extend(str(item) for item in labels.keys())
    return _uniq(roots)


def infer_old_home(codex_home: Path, new_home: str) -> Optional[str]:
    candidates: Dict[str, int] = {}
    for filename in (GLOBAL_STATE, GLOBAL_STATE_BAK):
        path = codex_home / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in HOME_RE.findall(text):
            if match != new_home:
                candidates[match] = candidates.get(match, 0) + 1

    sqlite_path = codex_home / SQLITE_STATE
    if sqlite_path.exists():
        with sqlite3.connect(sqlite_path) as conn:
            for cwd in _thread_cwd_counts(conn):
                for match in HOME_RE.findall(cwd):
                    if match != new_home:
                        candidates[match] = candidates.get(match, 0) + 5

    if not candidates:
        return None
    return sorted(candidates.items(), key=lambda item: item[1], reverse=True)[0][0]


def scan_codex(
    codex_home: str | Path | None = None,
    old_home: str | None = None,
    new_home: str | None = None,
) -> Dict[str, Any]:
    root = expand_path(codex_home or default_codex_home())
    resolved_new_home = resolve_new_home(new_home)
    resolved_old_home = old_home or infer_old_home(root, resolved_new_home)

    result: Dict[str, Any] = {
        "codex_home": str(root),
        "old_home": resolved_old_home,
        "new_home": resolved_new_home,
        "exists": root.exists(),
        "files": {},
        "sqlite": {},
        "workspace_roots": [],
        "missing_workspace_roots": [],
        "thread_cwds": {},
        "missing_thread_cwds": [],
        "old_ref_total": 0,
    }

    for filename in (GLOBAL_STATE, GLOBAL_STATE_BAK):
        path = root / filename
        refs = _text_count(path, resolved_old_home or "")
        result["files"][filename] = {"exists": path.exists(), "old_refs": refs}
        result["old_ref_total"] += refs

    state = _read_json(root / GLOBAL_STATE)
    if isinstance(state, dict):
        workspace_roots = _collect_roots_from_state(state)
        result["workspace_roots"] = workspace_roots
        result["missing_workspace_roots"] = [item for item in workspace_roots if not Path(item).exists()]

    sqlite_path = root / SQLITE_STATE
    if sqlite_path.exists():
        with sqlite3.connect(sqlite_path) as conn:
            ref_counts = _sqlite_count_refs(conn, resolved_old_home or "") if resolved_old_home else {}
            thread_cwds = _thread_cwd_counts(conn)
            result["sqlite"] = {
                "exists": True,
                "threads": _thread_count(conn),
                "old_refs": ref_counts,
            }
            result["thread_cwds"] = thread_cwds
            result["missing_thread_cwds"] = [cwd for cwd in thread_cwds if cwd and not Path(cwd).exists()]
            result["old_ref_total"] += sum(ref_counts.values())
    else:
        result["sqlite"] = {"exists": False, "threads": {"total": 0, "active": 0}, "old_refs": {}}

    return result


def _roots_from_threads(scan: Dict[str, Any], old_home: str, new_home: str) -> List[str]:
    roots = []
    for cwd in scan.get("thread_cwds", {}):
        if not cwd:
            continue
        migrated = cwd.replace(old_home, new_home)
        if migrated == new_home:
            continue
        if Path(migrated).exists():
            roots.append(migrated)
    return roots


def build_directory_plan(
    codex_home: str | Path | None = None,
    old_home: str | None = None,
    new_home: str | None = None,
    new_username: str | None = None,
) -> Dict[str, Any]:
    resolved_new_home = resolve_new_home(new_home, new_username)
    scan = scan_codex(codex_home, old_home, resolved_new_home)
    resolved_old_home = scan["old_home"]
    if not resolved_old_home:
        raise ValueError(
            "Could not infer old_home. This workflow assumes the old ~/.codex folder was copied directly."
        )
    if resolved_old_home == resolved_new_home:
        raise ValueError("old_home and new_home are the same; there is nothing to migrate.")

    raw_roots = _uniq(
        list(scan.get("workspace_roots", []))
        + list(scan.get("thread_cwds", {}).keys())
    )
    directories = []
    prefix = resolved_new_home.rstrip("/") + "/"
    for old_path in raw_roots:
        if not old_path or resolved_old_home not in old_path:
            continue
        new_path = old_path.replace(resolved_old_home, resolved_new_home)
        if new_path == resolved_new_home or not new_path.startswith(prefix):
            continue
        directories.append(
            {
                "old": old_path,
                "new": new_path,
                "exists": Path(new_path).exists(),
                "will_create": not Path(new_path).exists(),
            }
        )

    deduped = []
    seen = set()
    for item in sorted(directories, key=lambda entry: entry["new"]):
        if item["new"] in seen:
            continue
        seen.add(item["new"])
        deduped.append(item)

    return {
        "codex_home": scan["codex_home"],
        "old_home": resolved_old_home,
        "new_home": resolved_new_home,
        "directories": deduped,
        "directories_to_create": [item["new"] for item in deduped if item["will_create"]],
        "note": "This creates missing directories only. It does not recreate project source files.",
    }


def bootstrap_migration(
    codex_home: str | Path | None = None,
    old_home: str | None = None,
    new_home: str | None = None,
    new_username: str | None = None,
    execute: bool = False,
    backup_parent: str | Path | None = None,
    rewrite_sessions: bool = False,
) -> Dict[str, Any]:
    directory_plan = build_directory_plan(
        codex_home=codex_home,
        old_home=old_home,
        new_home=new_home,
        new_username=new_username,
    )
    if not execute:
        migration_plan = build_plan(
            codex_home=directory_plan["codex_home"],
            old_home=directory_plan["old_home"],
            new_home=directory_plan["new_home"],
            prune_missing=False,
            rewrite_sessions=rewrite_sessions,
        )
        return {
            "executed": False,
            "precondition": "old ~/.codex copied directly to this Mac",
            "directory_plan": directory_plan,
            "migration_plan": migration_plan,
        }

    created = []
    for item in directory_plan["directories"]:
        if item["will_create"]:
            Path(item["new"]).mkdir(parents=True, exist_ok=True)
            created.append(item["new"])

    migration = apply_migration(
        codex_home=directory_plan["codex_home"],
        old_home=directory_plan["old_home"],
        new_home=directory_plan["new_home"],
        execute=True,
        prune_missing=True,
        rewrite_sessions=rewrite_sessions,
        backup_parent=backup_parent,
    )
    return {
        "executed": True,
        "precondition": "old ~/.codex copied directly to this Mac",
        "created_directories": created,
        "migration": migration,
        "restart_required": True,
        "note": "Directories were created, but project file contents must still exist or be copied separately.",
    }


def _planned_roots(scan: Dict[str, Any], old_home: str, new_home: str, prune_missing: bool = True) -> List[str]:
    current_roots = [
        str(root).replace(old_home, new_home) for root in scan.get("workspace_roots", [])
    ]
    candidates = _uniq(_roots_from_threads(scan, old_home, new_home) + current_roots)
    if prune_missing:
        candidates = [root for root in candidates if Path(root).exists()]
    return candidates


def build_plan(
    codex_home: str | Path | None = None,
    old_home: str | None = None,
    new_home: str | None = None,
    prune_missing: bool = True,
    rewrite_sessions: bool = False,
) -> Dict[str, Any]:
    scan = scan_codex(codex_home, old_home, new_home)
    if not scan["old_home"]:
        raise ValueError("Could not infer old_home. Pass --old-home explicitly.")
    roots = _planned_roots(scan, scan["old_home"], scan["new_home"], prune_missing=prune_missing)
    return {
        "codex_home": scan["codex_home"],
        "old_home": scan["old_home"],
        "new_home": scan["new_home"],
        "rewrite_sessions": rewrite_sessions,
        "prune_missing": prune_missing,
        "old_ref_total": scan["old_ref_total"],
        "workspace_roots_after": roots,
        "thread_cwds_after": {
            cwd.replace(scan["old_home"], scan["new_home"]): count
            for cwd, count in scan.get("thread_cwds", {}).items()
        },
        "backup_files": [
            filename
            for filename in (SQLITE_STATE, GLOBAL_STATE, GLOBAL_STATE_BAK)
            if (Path(scan["codex_home"]) / filename).exists()
        ],
        "warnings": _plan_warnings(scan, roots),
    }


def _plan_warnings(scan: Dict[str, Any], roots: List[str]) -> List[str]:
    warnings: List[str] = []
    if not scan["exists"]:
        warnings.append("Codex home does not exist.")
    if not scan.get("sqlite", {}).get("exists"):
        warnings.append("state_5.sqlite was not found.")
    if scan.get("missing_thread_cwds"):
        warnings.append("Some thread cwd paths are missing even after current scan.")
    if not roots:
        warnings.append("No existing workspace roots would remain after migration.")
    return warnings


def _backup_file(source: Path, backup_root: Path, codex_home: Path, manifest_files: List[Dict[str, str]]) -> None:
    if not source.exists():
        return
    rel = source.relative_to(codex_home)
    target = backup_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    manifest_files.append({"relative_path": str(rel), "backup_path": str(target)})


def _create_backup(
    codex_home: Path,
    rewrite_sessions: bool = False,
    backup_parent: str | Path | None = None,
) -> Path:
    parent = (
        Path(backup_parent).expanduser()
        if backup_parent
        else Path(os.environ.get("CODEX_MIGRATOR_BACKUP_HOME", Path.home() / ".codex-migration-backups")).expanduser()
    )
    backup_root = parent / f"codex-migrator-{_now_id()}"
    backup_root.mkdir(parents=True, exist_ok=True)
    files: List[Dict[str, str]] = []
    for filename in (SQLITE_STATE, GLOBAL_STATE, GLOBAL_STATE_BAK):
        _backup_file(codex_home / filename, backup_root, codex_home, files)
    if rewrite_sessions:
        sessions = codex_home / "sessions"
        if sessions.exists():
            for item in sessions.rglob("*.jsonl"):
                _backup_file(item, backup_root, codex_home, files)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "codex_home": str(codex_home),
        "files": files,
    }
    _write_json(backup_root / "manifest.json", manifest)
    return backup_root


def _rewrite_sqlite(sqlite_path: Path, old_home: str, new_home: str) -> Dict[str, int]:
    changed: Dict[str, int] = {}
    with sqlite3.connect(sqlite_path) as conn:
        like_value = f"%{old_home}%"
        for table in _sqlite_tables(conn):
            for column in _sqlite_text_columns(conn, table):
                table_q = _quote_identifier(table)
                column_q = _quote_identifier(column)
                before = conn.total_changes
                try:
                    conn.execute(
                        f"update {table_q} set {column_q}=replace({column_q}, ?, ?) where coalesce({column_q}, '') like ?",
                        (old_home, new_home, like_value),
                    )
                except sqlite3.DatabaseError:
                    continue
                delta = conn.total_changes - before
                if delta:
                    changed[f"{table}.{column}"] = delta
        conn.commit()
    return changed


def _rewrite_global_state(
    path: Path,
    old_home: str,
    new_home: str,
    roots: List[str],
    prune_missing: bool,
) -> bool:
    state = _read_json(path)
    if not isinstance(state, dict):
        return False
    state = _replace_deep(state, old_home, new_home)
    state["electron-saved-workspace-roots"] = roots
    state["project-order"] = roots

    active = state.get("active-workspace-roots")
    if isinstance(active, list):
        active_roots = _uniq(str(item) for item in active if isinstance(item, str))
        if prune_missing:
            active_roots = [root for root in active_roots if Path(root).exists()]
        state["active-workspace-roots"] = active_roots or roots[:1]

    hints = state.get("thread-workspace-root-hints")
    if isinstance(hints, dict) and prune_missing:
        for thread_id, root in list(hints.items()):
            if not isinstance(root, str) or not Path(root).exists():
                del hints[thread_id]

    labels = state.get("electron-workspace-root-labels")
    if isinstance(labels, dict) and prune_missing:
        for root in list(labels.keys()):
            if not Path(root).exists():
                del labels[root]

    _write_json(path, state)
    return True


def _rewrite_sessions(codex_home: Path, old_home: str, new_home: str) -> int:
    sessions = codex_home / "sessions"
    if not sessions.exists():
        return 0
    changed = 0
    for item in sessions.rglob("*.jsonl"):
        text = item.read_text(encoding="utf-8", errors="ignore")
        if old_home not in text:
            continue
        item.write_text(text.replace(old_home, new_home), encoding="utf-8")
        changed += 1
    return changed


def apply_migration(
    codex_home: str | Path | None = None,
    old_home: str | None = None,
    new_home: str | None = None,
    execute: bool = False,
    prune_missing: bool = True,
    rewrite_sessions: bool = False,
    backup_parent: str | Path | None = None,
) -> Dict[str, Any]:
    plan = build_plan(
        codex_home=codex_home,
        old_home=old_home,
        new_home=new_home,
        prune_missing=prune_missing,
        rewrite_sessions=rewrite_sessions,
    )
    if not execute:
        return {"executed": False, "plan": plan}

    root = Path(plan["codex_home"])
    backup_root = _create_backup(root, rewrite_sessions=rewrite_sessions, backup_parent=backup_parent)
    sqlite_changes: Dict[str, int] = {}
    sqlite_path = root / SQLITE_STATE
    if sqlite_path.exists():
        sqlite_changes = _rewrite_sqlite(sqlite_path, plan["old_home"], plan["new_home"])

    json_files_changed = []
    for filename in (GLOBAL_STATE, GLOBAL_STATE_BAK):
        path = root / filename
        if path.exists() and _rewrite_global_state(
            path,
            plan["old_home"],
            plan["new_home"],
            plan["workspace_roots_after"],
            prune_missing=prune_missing,
        ):
            json_files_changed.append(filename)

    sessions_changed = 0
    if rewrite_sessions:
        sessions_changed = _rewrite_sessions(root, plan["old_home"], plan["new_home"])

    post_scan = scan_codex(root, plan["old_home"], plan["new_home"])
    return {
        "executed": True,
        "backup": str(backup_root),
        "sqlite_changes": sqlite_changes,
        "json_files_changed": json_files_changed,
        "sessions_changed": sessions_changed,
        "post_scan": post_scan,
        "restart_required": True,
    }


def restore_backup(backup_dir: str | Path, codex_home: str | Path | None = None) -> Dict[str, Any]:
    root = expand_path(backup_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.json found in {root}")
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError(f"Invalid manifest in {manifest_path}")
    target_codex_home = expand_path(codex_home or manifest["codex_home"])
    restored = []
    for file_info in manifest.get("files", []):
        relative_path = Path(file_info["relative_path"])
        source = root / relative_path
        target = target_codex_home / relative_path
        if not source.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        restored.append(str(target))
    return {"backup": str(root), "codex_home": str(target_codex_home), "restored": restored}
