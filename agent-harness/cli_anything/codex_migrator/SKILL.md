---
name: "cli-anything-codex-migrator"
description: "Migrate Codex Desktop local sessions after a macOS username or project path change, with backups, scans, JSON output, and restore support."
---

# CLI-Anything Codex Migrator

Use this skill when Codex Desktop local chats disappeared after copying `~/.codex` to a new Mac or changing the home pathname.

## Install

```bash
cd agent-harness
pip install -e .
```

## Common Commands

```bash
codex_migration
cli-anything-codex-migrator scan --codex-home ~/.codex --old-home /Users/oldname --new-home /Users/newname
cli-anything-codex-migrator bootstrap --new-username newname
cli-anything-codex-migrator bootstrap --execute --new-username newname
cli-anything-codex-migrator plan --json --old-home /Users/oldname --new-home /Users/newname
cli-anything-codex-migrator apply --execute --old-home /Users/oldname --new-home /Users/newname
cli-anything-codex-migrator refresh --old-home /Users/oldname --new-home /Users/newname
cli-anything-codex-migrator restore /Users/newname/.codex-migration-backups/<backup-id>
```

When the install path contains spaces, use `python -m cli_anything.codex_migrator ...`.

## Agent Guidance

- Prefer `--json` for machine-readable output.
- Run `scan` before `apply`.
- Prefer `bootstrap --new-username <name>` for non-technical users who directly copied old `~/.codex` to the new Mac.
- For the public interactive UX, tell users to run `codex_migration` and enter the new `/Users/<name>` path or username when prompted.
- Use `apply` without `--execute` for a dry run.
- Explain that `bootstrap` can create missing folders but cannot recreate the contents of project repositories or files.
- Tell the user to fully quit and reopen Codex Desktop after a successful migration if the app still shows stale project groups.
- Do not rewrite session JSONL files unless the user explicitly wants historical command output strings changed; operational grouping is normally controlled by SQLite thread metadata and global workspace-root state.
