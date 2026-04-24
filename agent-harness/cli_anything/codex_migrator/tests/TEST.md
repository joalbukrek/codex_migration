# Test Plan

## Test Inventory Plan

- `test_core.py`: 7 unit tests.
- `test_full_e2e.py`: 4 subprocess workflow tests.

## Unit Test Plan

Module: `core.migration`

- Create fake Codex homes with SQLite thread rows and global JSON state.
- Verify old home inference.
- Verify scan counts SQLite and JSON references.
- Verify dry-run apply does not mutate files.
- Verify executed apply rewrites SQLite and JSON paths.
- Verify missing workspace roots are pruned.
- Verify backup manifest is written.
- Verify bootstrap directory planning finds missing migrated project folders.
- Verify bootstrap creates missing directories before applying the migration.
- Verify restore returns the fake Codex home to the backed-up state.

## E2E Test Plan

The E2E tests invoke `cli-anything-codex-migrator` through subprocess, falling back to `python -m cli_anything.codex_migrator` during development.

Workflows:

- `scan --json` on a fake migrated Codex home.
- `apply --execute --json` on a fake Codex home.
- `restore` from the generated backup.
- `bootstrap --execute --json` creates missing directories and migrates state.
- default command launches the guided prompt and can exit without writing.

## Backend Validation

These tests use real SQLite and JSON files. They do not mutate the user's real `~/.codex`.

## Test Results

Command:

```bash
.venv/bin/python -m pytest agent-harness/cli_anything/codex_migrator/tests -v
```

Output:

```text
collected 11 items

agent-harness/cli_anything/codex_migrator/tests/test_core.py::MigrationCoreTests::test_apply_dry_run_does_not_mutate PASSED
agent-harness/cli_anything/codex_migrator/tests/test_core.py::MigrationCoreTests::test_apply_execute_rewrites_operational_state PASSED
agent-harness/cli_anything/codex_migrator/tests/test_core.py::MigrationCoreTests::test_bootstrap_execute_creates_dirs_then_migrates PASSED
agent-harness/cli_anything/codex_migrator/tests/test_core.py::MigrationCoreTests::test_directory_plan_lists_missing_new_project_paths PASSED
agent-harness/cli_anything/codex_migrator/tests/test_core.py::MigrationCoreTests::test_plan_rewrites_roots_to_existing_new_paths PASSED
agent-harness/cli_anything/codex_migrator/tests/test_core.py::MigrationCoreTests::test_restore_backup PASSED
agent-harness/cli_anything/codex_migrator/tests/test_core.py::MigrationCoreTests::test_scan_counts_refs_and_threads PASSED
agent-harness/cli_anything/codex_migrator/tests/test_full_e2e.py::CLISubprocessTests::test_bootstrap_json_workflow PASSED
agent-harness/cli_anything/codex_migrator/tests/test_full_e2e.py::CLISubprocessTests::test_default_command_runs_guided_prompt_dry_run PASSED
agent-harness/cli_anything/codex_migrator/tests/test_full_e2e.py::CLISubprocessTests::test_help PASSED
agent-harness/cli_anything/codex_migrator/tests/test_full_e2e.py::CLISubprocessTests::test_scan_and_apply_json_workflow PASSED

11 passed in 0.22s
```

Coverage note: the `refresh` command is backend-aware but not tested against the live Codex Desktop app, because automated control of Codex Desktop is restricted in this environment.
