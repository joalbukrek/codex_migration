from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import click

from . import __version__
from .core.migration import (
    apply_migration,
    bootstrap_migration,
    build_plan,
    default_codex_home,
    resolve_new_home,
    restore_backup,
    scan_codex,
)
from .core.session import remember
from .utils._backend import refresh_codex_roots
from .utils.repl_skin import ReplSkin


def _parse_user_home(value: str) -> str:
    text = value.strip()
    if not text:
        raise click.BadParameter("Enter a macOS username or a /Users/<name> path.")
    if text.startswith("/"):
        return str(Path(text).expanduser())
    return resolve_new_home(new_username=text)


def _remember(event: Dict[str, Any]) -> None:
    try:
        remember(event)
    except OSError:
        pass


def _emit(data: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(data, indent=2))
        return
    if "error" in data:
        click.echo(f"ERROR: {data['error']}", err=True)
        return
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            click.echo(f"{key}: {json.dumps(value, indent=2)}")
        else:
            click.echo(f"{key}: {value}")


def _print_bootstrap_preview(result: Dict[str, Any]) -> None:
    directory_plan = result["directory_plan"]
    migration_plan = result["migration_plan"]
    directories_to_create = directory_plan["directories_to_create"]
    roots_after = migration_plan["workspace_roots_after"]
    threads_after = migration_plan["thread_cwds_after"]

    click.echo("")
    click.echo("Detected migration")
    click.echo(f"  Old user path: {directory_plan['old_home']}")
    click.echo(f"  New user path: {directory_plan['new_home']}")
    click.echo(f"  Codex home:    {directory_plan['codex_home']}")
    click.echo("")
    click.echo(f"Active thread cwd groups found: {len(threads_after)}")
    click.echo(f"Workspace roots after migration: {len(roots_after)}")
    click.echo(f"Directories to create: {len(directories_to_create)}")
    for item in directories_to_create[:20]:
        click.echo(f"  - {item}")
    if len(directories_to_create) > 20:
        click.echo(f"  ... {len(directories_to_create) - 20} more")
    click.echo("")
    click.echo("This will create missing folders and rewrite Codex local state.")
    click.echo("It will not recreate project file contents; those must be copied or cloned separately.")


@click.group(invoke_without_command=True)
@click.option("--codex-home", default=None, help="Codex home directory. Defaults to CODEX_HOME or ~/.codex.")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
@click.version_option(__version__)
@click.pass_context
def cli(ctx: click.Context, codex_home: str | None, as_json: bool) -> None:
    """Migrate Codex Desktop local sessions between user paths."""
    ctx.ensure_object(dict)
    ctx.obj["codex_home"] = codex_home
    ctx.obj["as_json"] = as_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(wizard)


@cli.command()
@click.option("--old-home", default=None, help="Optional override. Otherwise inferred from copied Codex state.")
@click.option("--backup-parent", default=None, help="Directory where timestamped migration backups are created.")
@click.option("--rewrite-sessions", is_flag=True, help="Also rewrite old paths inside session JSONL files.")
@click.option("--refresh-app", is_flag=True, help="Open migrated roots in Codex Desktop after applying.")
@click.pass_context
def wizard(
    ctx: click.Context,
    old_home: str | None,
    backup_parent: str | None,
    rewrite_sessions: bool,
    refresh_app: bool,
) -> None:
    """Guided migration prompt for directly copied old ~/.codex folders."""
    click.echo("Codex Migration")
    click.echo("Use this only after copying the old Mac's ~/.codex folder to this Mac.")
    click.echo("")
    new_home_input = click.prompt(
        "New user path or username",
        default=str(Path.home()),
        show_default=True,
    )
    try:
        new_home = _parse_user_home(new_home_input)
        preview = bootstrap_migration(
            codex_home=ctx.obj["codex_home"],
            old_home=old_home,
            new_home=new_home,
            execute=False,
            rewrite_sessions=rewrite_sessions,
        )
        _print_bootstrap_preview(preview)
        if not click.confirm("Create directories and migrate Codex state now?", default=False):
            click.echo("No changes made.")
            return
        result = bootstrap_migration(
            codex_home=ctx.obj["codex_home"],
            old_home=old_home,
            new_home=new_home,
            execute=True,
            backup_parent=backup_parent,
            rewrite_sessions=rewrite_sessions,
        )
        if refresh_app:
            roots = result["migration"]["post_scan"].get("workspace_roots", [])
            result["refresh"] = refresh_codex_roots(roots)
        _remember({"command": "wizard", "result": result})
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc

    click.echo("")
    click.echo("Migration complete.")
    click.echo(f"Backup: {result['migration']['backup']}")
    click.echo(f"Created directories: {len(result['created_directories'])}")
    click.echo("Fully quit and reopen Codex Desktop before checking the migrated chats.")


@cli.command()
@click.option("--old-home", default=None, help="Old home path, for example /Users/oldname.")
@click.option("--new-home", default=None, help="New home path. Defaults to the current user's home.")
@click.option("--new-username", default=None, help="New macOS username. Expands to /Users/<name>.")
@click.pass_context
def scan(
    ctx: click.Context,
    old_home: str | None,
    new_home: str | None,
    new_username: str | None,
) -> None:
    """Inspect Codex state without changing files."""
    result = scan_codex(ctx.obj["codex_home"], old_home, resolve_new_home(new_home, new_username))
    _remember({"command": "scan", "result": result})
    _emit(result, ctx.obj["as_json"])


@cli.command("plan")
@click.option("--old-home", default=None, help="Old home path, for example /Users/oldname.")
@click.option("--new-home", default=None, help="New home path. Defaults to the current user's home.")
@click.option("--new-username", default=None, help="New macOS username. Expands to /Users/<name>.")
@click.option("--keep-missing", is_flag=True, help="Keep missing workspace roots instead of pruning them.")
@click.option("--rewrite-sessions", is_flag=True, help="Also rewrite old paths inside session JSONL files.")
@click.pass_context
def plan_cmd(
    ctx: click.Context,
    old_home: str | None,
    new_home: str | None,
    new_username: str | None,
    keep_missing: bool,
    rewrite_sessions: bool,
) -> None:
    """Show what apply would change."""
    try:
        result = build_plan(
            ctx.obj["codex_home"],
            old_home,
            resolve_new_home(new_home, new_username),
            prune_missing=not keep_missing,
            rewrite_sessions=rewrite_sessions,
        )
        _remember({"command": "plan", "result": result})
    except Exception as exc:  # noqa: BLE001
        result = {"error": str(exc)}
    _emit(result, ctx.obj["as_json"])


@cli.command("apply")
@click.option("--old-home", default=None, help="Old home path, for example /Users/oldname.")
@click.option("--new-home", default=None, help="New home path. Defaults to the current user's home.")
@click.option("--new-username", default=None, help="New macOS username. Expands to /Users/<name>.")
@click.option("--execute", is_flag=True, help="Actually write changes. Without this, apply is a dry run.")
@click.option("--keep-missing", is_flag=True, help="Keep missing workspace roots instead of pruning them.")
@click.option("--rewrite-sessions", is_flag=True, help="Also rewrite old paths inside session JSONL files.")
@click.option("--refresh-app", is_flag=True, help="Open migrated roots in Codex Desktop after applying.")
@click.option("--backup-parent", default=None, help="Directory where timestamped migration backups are created.")
@click.pass_context
def apply_cmd(
    ctx: click.Context,
    old_home: str | None,
    new_home: str | None,
    new_username: str | None,
    execute: bool,
    keep_missing: bool,
    rewrite_sessions: bool,
    refresh_app: bool,
    backup_parent: str | None,
) -> None:
    """Backup and rewrite Codex state files."""
    try:
        result = apply_migration(
            ctx.obj["codex_home"],
            old_home,
            resolve_new_home(new_home, new_username),
            execute=execute,
            prune_missing=not keep_missing,
            rewrite_sessions=rewrite_sessions,
            backup_parent=backup_parent,
        )
        if execute and refresh_app:
            roots = result["post_scan"].get("workspace_roots", [])
            result["refresh"] = refresh_codex_roots(roots)
        _remember({"command": "apply", "result": result})
    except Exception as exc:  # noqa: BLE001
        result = {"error": str(exc)}
    _emit(result, ctx.obj["as_json"])


@cli.command()
@click.option("--old-home", default=None, help="Old home path, for example /Users/oldname.")
@click.option("--new-home", default=None, help="New home path. Defaults to the current user's home.")
@click.option("--new-username", default=None, help="New macOS username. Expands to /Users/<name>.")
@click.pass_context
def refresh(
    ctx: click.Context,
    old_home: str | None,
    new_home: str | None,
    new_username: str | None,
) -> None:
    """Open migrated workspace roots in Codex Desktop."""
    try:
        result = build_plan(ctx.obj["codex_home"], old_home, resolve_new_home(new_home, new_username))
        refresh_result = refresh_codex_roots(result["workspace_roots_after"])
        refresh_result["workspace_roots"] = result["workspace_roots_after"]
        _remember({"command": "refresh", "result": refresh_result})
    except Exception as exc:  # noqa: BLE001
        refresh_result = {"error": str(exc)}
    _emit(refresh_result, ctx.obj["as_json"])


@cli.command()
@click.option("--old-home", default=None, help="Optional override. Otherwise inferred from copied Codex state.")
@click.option("--new-home", default=None, help="New home path. Defaults to the current user's home.")
@click.option("--new-username", default=None, help="New macOS username. Expands to /Users/<name>.")
@click.option("--execute", is_flag=True, help="Create directories and apply migration. Dry-run by default.")
@click.option("--backup-parent", default=None, help="Directory where timestamped migration backups are created.")
@click.option("--rewrite-sessions", is_flag=True, help="Also rewrite old paths inside session JSONL files.")
@click.option("--refresh-app", is_flag=True, help="Open migrated roots in Codex Desktop after applying.")
@click.pass_context
def bootstrap(
    ctx: click.Context,
    old_home: str | None,
    new_home: str | None,
    new_username: str | None,
    execute: bool,
    backup_parent: str | None,
    rewrite_sessions: bool,
    refresh_app: bool,
) -> None:
    """One-command workflow for a directly copied old ~/.codex folder."""
    try:
        result = bootstrap_migration(
            codex_home=ctx.obj["codex_home"],
            old_home=old_home,
            new_home=new_home,
            new_username=new_username,
            execute=execute,
            backup_parent=backup_parent,
            rewrite_sessions=rewrite_sessions,
        )
        if execute and refresh_app:
            roots = result["migration"]["post_scan"].get("workspace_roots", [])
            result["refresh"] = refresh_codex_roots(roots)
        _remember({"command": "bootstrap", "result": result})
    except Exception as exc:  # noqa: BLE001
        result = {"error": str(exc)}
    _emit(result, ctx.obj["as_json"])


@cli.command()
@click.argument("backup_dir")
@click.option("--target-codex-home", default=None, help="Restore into this Codex home instead of the manifest target.")
@click.pass_context
def restore(ctx: click.Context, backup_dir: str, target_codex_home: str | None) -> None:
    """Restore files from a migration backup."""
    try:
        result = restore_backup(backup_dir, target_codex_home)
        _remember({"command": "restore", "result": result})
    except Exception as exc:  # noqa: BLE001
        result = {"error": str(exc)}
    _emit(result, ctx.obj["as_json"])


@cli.command()
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Start an interactive migration session."""
    skin = ReplSkin("cli-anything-codex-migrator", version=__version__)
    skin.print_banner()
    skin.info(f"Codex home: {ctx.obj.get('codex_home') or default_codex_home()}")
    while True:
        try:
            line = input("codex-migrator> ").strip()
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            return
        if not line:
            continue
        if line in {"quit", "exit"}:
            skin.print_goodbye()
            return
        if line == "help":
            skin.table(
                ["command", "description"],
                [
                    ["scan", "Inspect state"],
                    ["plan OLD NEW", "Show migration plan"],
                    ["apply OLD NEW", "Dry-run migration"],
                    ["quit", "Exit"],
                ],
            )
            continue
        parts = line.split()
        try:
            if parts[0] == "scan":
                _emit(scan_codex(ctx.obj["codex_home"]), False)
            elif parts[0] == "plan" and len(parts) == 3:
                _emit(build_plan(ctx.obj["codex_home"], parts[1], parts[2]), False)
            elif parts[0] == "apply" and len(parts) == 3:
                _emit(apply_migration(ctx.obj["codex_home"], parts[1], parts[2], execute=False), False)
            else:
                skin.error("Unknown command. Type 'help'.")
        except Exception as exc:  # noqa: BLE001
            skin.error(str(exc))


def main() -> int:
    try:
        cli()
        return 0
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
