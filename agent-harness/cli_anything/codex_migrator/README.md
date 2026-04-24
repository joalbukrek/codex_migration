# CLI-Anything Codex Migrator

This harness migrates Codex Desktop local state after moving `~/.codex` from one macOS user path to another.

It was built around the real failure mode where chats still exist in `state_5.sqlite`, but Codex Desktop project groups show `No chats` because saved workspace roots and local environment paths still point at `/Users/<oldname>`.

## Install

```bash
cd agent-harness
pip install -e .
```

After install, users start the guided flow with:

```bash
codex_migration
```

If your virtual environment lives inside a path with spaces, prefer the module form:

```bash
python -m cli_anything.codex_migrator --help
```

## Guided Flow

The default command asks for the new user path:

```text
$ codex_migration
Codex Migration
Use this only after copying the old Mac's ~/.codex folder to this Mac.

New user path or username [/Users/newname]:
```

The user may enter either:

```text
/Users/joalbukrek
```

or just:

```text
joalbukrek
```

The program then previews the inferred old user path, directories to create, and workspace roots to migrate. It writes nothing until the user confirms.

## Inspect

```bash
python -m cli_anything.codex_migrator --json scan \
  --old-home /Users/jonathanalbukrek \
  --new-home /Users/joalbukrek
```

## One-Command Migration For Other Users

This is the intended public workflow when the old `~/.codex` folder was copied directly to the new Mac:

```bash
python -m cli_anything.codex_migrator --json bootstrap \
  --new-username joalbukrek
```

That dry run will:

- infer the old `/Users/<oldname>` path from the copied Codex state
- show the missing directories it would create under `/Users/joalbukrek`
- show the Codex state migration it would apply

Execute it after reviewing the output:

```bash
python -m cli_anything.codex_migrator bootstrap --execute \
  --new-username joalbukrek
```

The command creates matching directories only. It does not recreate project source files; users still need to copy or clone their project contents separately.

## Dry Run

```bash
python -m cli_anything.codex_migrator --json apply \
  --old-home /Users/jonathanalbukrek \
  --new-home /Users/joalbukrek
```

## Execute

```bash
python -m cli_anything.codex_migrator apply --execute \
  --old-home /Users/jonathanalbukrek \
  --new-home /Users/joalbukrek
```

The command creates a backup under `~/.codex-migration-backups/` before editing:

- `state_5.sqlite`
- `.codex-global-state.json`
- `.codex-global-state.json.bak`

After applying, fully quit and reopen Codex Desktop if the current window still shows stale or empty project groups.

## Restore

```bash
python -m cli_anything.codex_migrator restore ~/.codex-migration-backups/codex-migrator-YYYYMMDDHHMMSS
```

## Commands

- `scan`: Count old path references and list current workspace/thread paths.
- `bootstrap`: Infer the old copied-home path, create matching new directories, then migrate state.
- `wizard`: Same public workflow as running `codex_migration` with no subcommand.
- `plan`: Show the path rewrite and workspace roots that would remain.
- `apply`: Backup and rewrite Codex state. Dry-run by default.
- `refresh`: Ask Codex Desktop to open migrated workspace roots.
- `restore`: Restore from a backup manifest.
- no command: Start a small REPL.
