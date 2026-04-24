from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cli_anything.codex_migrator.tests.test_core import make_fake_codex


def _resolve_cli(name: str):
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    installed = shutil.which(name)
    if installed:
        return [installed]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e agent-harness")
    return [sys.executable, "-m", "cli_anything.codex_migrator"]


class CLISubprocessTests(unittest.TestCase):
    CLI_BASE = _resolve_cli("cli-anything-codex-migrator")

    def run_cli(self, args, check=True, input_text=None):
        return subprocess.run(
            self.CLI_BASE + args,
            input=input_text,
            capture_output=True,
            text=True,
            check=check,
        )

    def test_help(self) -> None:
        result = self.run_cli(["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("Migrate Codex Desktop", result.stdout)

    def test_scan_and_apply_json_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            codex_home, old_home, new_home = make_fake_codex(Path(temp))
            scan = self.run_cli(
                [
                    "--codex-home",
                    str(codex_home),
                    "--json",
                    "scan",
                    "--old-home",
                    str(old_home),
                    "--new-home",
                    str(new_home),
                ]
            )
            scan_data = json.loads(scan.stdout)
            self.assertGreater(scan_data["old_ref_total"], 0)

            applied = self.run_cli(
                [
                    "--codex-home",
                    str(codex_home),
                    "--json",
                    "apply",
                    "--execute",
                    "--backup-parent",
                    str(Path(temp) / "backups"),
                    "--old-home",
                    str(old_home),
                    "--new-home",
                    str(new_home),
                ]
            )
            data = json.loads(applied.stdout)
            self.assertTrue(data["executed"])
            self.assertTrue(Path(data["backup"]).exists())
            self.assertEqual(sum(data["post_scan"]["sqlite"]["old_refs"].values()), 0)

    def test_bootstrap_json_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            codex_home, old_home, new_home = make_fake_codex(
                Path(temp),
                create_new_project=False,
                old_home_override="/Users/olduser",
            )
            bootstrap = self.run_cli(
                [
                    "--codex-home",
                    str(codex_home),
                    "--json",
                    "bootstrap",
                    "--execute",
                    "--backup-parent",
                    str(Path(temp) / "backups"),
                    "--old-home",
                    str(old_home),
                    "--new-home",
                    str(new_home),
                ]
            )
            data = json.loads(bootstrap.stdout)
            self.assertTrue(data["executed"])
            self.assertTrue((new_home / "Documents" / "02 personal" / "04 projects" / "demo").exists())

    def test_default_command_runs_guided_prompt_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            codex_home, old_home, new_home = make_fake_codex(
                Path(temp),
                create_new_project=False,
                old_home_override="/Users/olduser",
            )
            result = self.run_cli(
                [
                    "--codex-home",
                    str(codex_home),
                ],
                input_text=f"{new_home}\nn\n",
            )
            self.assertIn("Codex Migration", result.stdout)
            self.assertIn(f"Old user path: {old_home}", result.stdout)
            self.assertIn("No changes made.", result.stdout)
            self.assertFalse((new_home / "Documents" / "02 personal" / "04 projects" / "demo").exists())


if __name__ == "__main__":
    unittest.main()
