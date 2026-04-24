from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cli_anything.codex_migrator.core.migration import (
    apply_migration,
    bootstrap_migration,
    build_directory_plan,
    build_plan,
    restore_backup,
    scan_codex,
)


def make_fake_codex(
    root: Path,
    create_new_project: bool = True,
    old_home_override: str | None = None,
) -> tuple[Path, Path, Path]:
    codex_home = root / ".codex"
    old_home = Path(old_home_override) if old_home_override else root / "olduser"
    new_home = root / "newuser"
    project = new_home / "Documents" / "02 personal" / "04 projects" / "demo"
    old_project = old_home / "Documents" / "02 personal" / "04 projects" / "demo"
    if create_new_project:
        project.mkdir(parents=True)
    codex_home.mkdir()

    conn = sqlite3.connect(codex_home / "state_5.sqlite")
    conn.execute(
        "create table threads (id text primary key, title text, cwd text, rollout_path text, sandbox_policy text, archived integer)"
    )
    conn.execute(
        "insert into threads values (?, ?, ?, ?, ?, ?)",
        (
            "thread-1",
            "Demo",
            str(old_project),
            str(old_home / ".codex" / "sessions" / "demo.jsonl"),
            json.dumps({"writable_roots": [str(old_project)]}),
            0,
        ),
    )
    conn.commit()
    conn.close()

    state = {
        "electron-saved-workspace-roots": [str(old_project), str(old_home / "missing")],
        "project-order": [str(old_project)],
        "active-workspace-roots": [str(old_project)],
        "thread-workspace-root-hints": {"thread-1": str(old_project), "missing": str(old_home / "missing")},
        "electron-workspace-root-labels": {str(old_project): "demo", str(old_home / "missing"): "missing"},
    }
    (codex_home / ".codex-global-state.json").write_text(json.dumps(state), encoding="utf-8")
    (codex_home / ".codex-global-state.json.bak").write_text(json.dumps(state), encoding="utf-8")
    return codex_home, old_home, new_home


class MigrationCoreTests(unittest.TestCase):
    def test_scan_counts_refs_and_threads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            codex_home, old_home, new_home = make_fake_codex(Path(temp))
            result = scan_codex(codex_home, str(old_home), str(new_home))
            self.assertGreater(result["old_ref_total"], 0)
            self.assertEqual(result["sqlite"]["threads"]["active"], 1)
            self.assertIn(str(old_home), result["old_home"])

    def test_plan_rewrites_roots_to_existing_new_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            codex_home, old_home, new_home = make_fake_codex(Path(temp))
            plan = build_plan(codex_home, str(old_home), str(new_home))
            self.assertEqual(plan["workspace_roots_after"], [str(new_home / "Documents" / "02 personal" / "04 projects" / "demo")])

    def test_apply_dry_run_does_not_mutate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            codex_home, old_home, new_home = make_fake_codex(Path(temp))
            result = apply_migration(codex_home, str(old_home), str(new_home), execute=False)
            self.assertFalse(result["executed"])
            after = scan_codex(codex_home, str(old_home), str(new_home))
            self.assertGreater(after["old_ref_total"], 0)

    def test_apply_execute_rewrites_operational_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            codex_home, old_home, new_home = make_fake_codex(Path(temp))
            result = apply_migration(
                codex_home,
                str(old_home),
                str(new_home),
                execute=True,
                backup_parent=Path(temp) / "backups",
            )
            self.assertTrue(result["executed"])
            after = scan_codex(codex_home, str(old_home), str(new_home))
            self.assertEqual(sum(after["sqlite"]["old_refs"].values()), 0)
            state = json.loads((codex_home / ".codex-global-state.json").read_text())
            self.assertEqual(state["electron-saved-workspace-roots"], [str(new_home / "Documents" / "02 personal" / "04 projects" / "demo")])

    def test_restore_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            codex_home, old_home, new_home = make_fake_codex(Path(temp))
            result = apply_migration(
                codex_home,
                str(old_home),
                str(new_home),
                execute=True,
                backup_parent=Path(temp) / "backups",
            )
            restore_result = restore_backup(result["backup"], codex_home)
            self.assertTrue(restore_result["restored"])
            after_restore = scan_codex(codex_home, str(old_home), str(new_home))
            self.assertGreater(after_restore["old_ref_total"], 0)

    def test_directory_plan_lists_missing_new_project_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            codex_home, old_home, new_home = make_fake_codex(Path(temp), create_new_project=False)
            result = build_directory_plan(codex_home, str(old_home), str(new_home))
            expected = str(new_home / "Documents" / "02 personal" / "04 projects" / "demo")
            self.assertIn(expected, result["directories_to_create"])

    def test_bootstrap_execute_creates_dirs_then_migrates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            codex_home, old_home, new_home = make_fake_codex(Path(temp), create_new_project=False)
            result = bootstrap_migration(
                codex_home=codex_home,
                old_home=str(old_home),
                new_home=str(new_home),
                execute=True,
                backup_parent=Path(temp) / "backups",
            )
            expected = new_home / "Documents" / "02 personal" / "04 projects" / "demo"
            self.assertTrue(expected.exists())
            self.assertIn(str(expected), result["created_directories"])
            after = scan_codex(codex_home, str(old_home), str(new_home))
            self.assertEqual(sum(after["sqlite"]["old_refs"].values()), 0)


if __name__ == "__main__":
    unittest.main()
