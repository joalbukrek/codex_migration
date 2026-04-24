# Codex Migration

`codex_migration` is a small CLI for migrating local Codex Desktop chats after moving from one Mac user path to another.

It is designed for the specific case where you directly copied the old Mac's `~/.codex` folder to the new Mac, but Codex Desktop still points chats, projects, or local environments at the old path, for example:

```text
/Users/oldusername/...
```

instead of:

```text
/Users/newusername/...
```

## What It Fixes

Codex Desktop stores local thread and workspace metadata in `~/.codex`. After a Mac migration, that copied metadata can still contain the old username path. This can make existing chats appear under empty project groups or show errors such as:

```text
Current working directory missing
```

This tool:

- infers the old `/Users/<oldname>` path from the copied Codex state
- asks for the new username or `/Users/<newname>` path
- previews the migration before writing
- creates missing matching directories under the new user path
- backs up Codex state files
- rewrites Codex SQLite and JSON state paths
- can restore from a backup

## Important Limitations

This tool only migrates Codex Desktop's local metadata and creates missing folders.

It does **not** recreate your project files. You still need to copy or clone your actual repositories and files onto the new Mac.

Use this only when the old `~/.codex` folder was copied directly to the new Mac.

## Install

From this repository:

```bash
cd agent-harness
pip install -e .
```

That installs the guided command:

```bash
codex_migration
```

If your virtual environment or project path contains spaces and the console script fails, use the module form:

```bash
python -m cli_anything.codex_migrator
```

## Guided Usage

Run:

```bash
codex_migration
```

You will be asked:

```text
New user path or username [/Users/currentuser]:
```

Enter either the full path:

```text
/Users/joalbukrek
```

or just the username:

```text
joalbukrek
```

The tool will print a preview and ask for confirmation before it writes anything.

After a successful migration, fully quit and reopen Codex Desktop.

## Non-Interactive Usage

Dry run:

```bash
python -m cli_anything.codex_migrator --json bootstrap --new-username joalbukrek
```

Execute:

```bash
python -m cli_anything.codex_migrator bootstrap --execute --new-username joalbukrek
```

Explicit paths:

```bash
python -m cli_anything.codex_migrator bootstrap --execute \
  --old-home /Users/oldusername \
  --new-home /Users/newusername
```

## Safety

Before writing, the tool creates a timestamped backup under:

```text
~/.codex-migration-backups/
```

Backed up files include:

- `~/.codex/state_5.sqlite`
- `~/.codex/.codex-global-state.json`
- `~/.codex/.codex-global-state.json.bak`

Restore from a backup:

```bash
python -m cli_anything.codex_migrator restore ~/.codex-migration-backups/codex-migrator-YYYYMMDDHHMMSS
```

## Commands

- `codex_migration`: guided migration wizard
- `scan`: inspect current Codex state without writing
- `bootstrap`: infer old path, create matching folders, and migrate state
- `plan`: show a deterministic migration plan
- `apply`: rewrite paths after explicit old/new path input
- `refresh`: ask Codex Desktop to open migrated roots
- `restore`: restore state from a backup manifest

## Development

Install locally:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ./agent-harness pytest
```

Run tests:

```bash
.venv/bin/python -m pytest agent-harness/cli_anything/codex_migrator/tests -v
```

Current test coverage includes fake Codex homes, SQLite rewrites, JSON state rewrites, backup/restore, bootstrap directory creation, and subprocess CLI workflows.
