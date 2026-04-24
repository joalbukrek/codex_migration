# Codex Migrator Harness

## Purpose

This CLI-Anything harness makes Codex Desktop session migration repeatable. It targets the failure mode where `~/.codex` was copied from an old Mac, but Codex Desktop still points projects, environments, or thread working directories at the old `/Users/<name>` path.

## Backend

The real backend is the user's local Codex Desktop state:

- `~/.codex/state_5.sqlite` stores thread metadata such as `cwd`, `rollout_path`, and sandbox policy.
- `~/.codex/.codex-global-state.json` stores Desktop workspace roots, project ordering, prompt history, labels, active roots, and thread workspace hints.
- session JSONL files under `~/.codex/sessions/` may contain historical command output and old path strings, but those are not normally used for project grouping.

The harness does not reimplement Codex Desktop. It edits Codex's real local state files after taking backups, then asks Codex Desktop to reopen the migrated project roots when requested.

## Commands

- `scan`: inspect Codex state, count old path references, list thread working directories, and report missing paths.
- `bootstrap`: public first-run workflow for a directly copied old `~/.codex`; infer old home, create matching new directories, and apply migration.
- `wizard`: interactive version of `bootstrap`, launched by the short `codex_migration` command with no subcommand.
- `plan`: produce a deterministic migration plan.
- `apply`: create a timestamped backup and rewrite old home paths to the new home path.
- `refresh`: open migrated roots in Codex Desktop through the bundled `codex app <path>` command.
- `restore`: restore state files from a backup manifest.
- default REPL: agent-friendly interactive loop for repeated scan/plan/apply cycles.

## Safety Rules

- `apply` is dry-run unless `--execute` is provided.
- Every executed migration writes a backup manifest.
- SQLite updates are limited to text columns and use SQLite's `replace()` function.
- JSON updates are structural: keys and string values are both rewritten.
- Missing workspace roots are pruned by default because stale roots create empty project groups in Codex Desktop.

## Migration Model

1. Infer or accept `old_home` and `new_home`.
2. Scan state files and thread cwd values.
3. For the public `bootstrap` workflow, create missing directories that correspond to old workspace roots after replacing the home prefix.
4. Build new workspace roots from existing saved roots plus active thread cwd values after replacement.
5. Backup `state_5.sqlite`, `.codex-global-state.json`, and `.codex-global-state.json.bak`.
6. Rewrite SQLite text columns and JSON keys/values.
7. Re-scan to verify no operational old-home references remain.
8. Ask the user to fully quit and reopen Codex Desktop if the running app cached stale roots.

## Direct Copy Precondition

`bootstrap` is only for users who directly copied the old `~/.codex` folder to the new Mac. It can recreate the missing directory paths Codex expects, but it cannot recreate the project file contents. Users still need to copy or clone their actual project files separately if they want to continue working in those repositories.
