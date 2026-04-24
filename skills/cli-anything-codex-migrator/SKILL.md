---
name: "cli-anything-codex-migrator"
description: "Migrate Codex Desktop local sessions after a macOS username or project path change, with backups, scans, JSON output, and restore support."
---

# CLI-Anything Codex Migrator

Install from this repository:

```bash
cd agent-harness
pip install -e .
```

Use `codex_migration` for the public guided flow. It asks for the new `/Users/<name>` path or username, infers the old home from the copied `~/.codex`, previews the missing matching directories, and migrates Codex state after confirmation. It creates folders only, not project file contents. If the install path contains spaces, use `python -m cli_anything.codex_migrator ...`.
