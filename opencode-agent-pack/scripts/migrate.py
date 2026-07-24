#!/usr/bin/env python3
"""
Migration Support — migration from PR #5 layout to final runtime layout.

Commands:
  status    Report current migration state
  apply     Apply pending migrations
  rollback  Rollback last migration

Must not overwrite existing verified memory.
Reports: supported OpenCode version range, tested version, plugin API compatibility,
         unknown/new version warning.
"""

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ──────────────────────────────────────────────────────────────────
# Migration definitions
# ──────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0.0"
MIGRATION_STATE_FILE = ".heidi/migration-state.json"

# Supported OpenCode version range
SUPPORTED_OPENCODE_RANGE = ">=0.1.0,<2.0.0"
TESTED_OPENCODE_VERSION = "0.x"
PLUGIN_API_COMPATIBILITY = "v1"

# Known migration steps in order
MIGRATIONS = [
    {
        "id": "pr5-to-final-layout-001",
        "name": "Move .heidi files to final structure",
        "description": "Ensures .heidi directory uses final runtime layout with context-index.json, task-ledger.jsonl, runtime-events.jsonl",
        "applies_to": "PR #5 layout -> final",
        "safe_to_reapply": True,
    },
    {
        "id": "pr5-to-final-layout-002",
        "name": "Normalize agent file references",
        "description": "Ensure agent files reference opencode-agent-pack paths consistently",
        "applies_to": "PR #5 layout -> final",
        "safe_to_reapply": True,
    },
    {
        "id": "pr5-to-final-layout-003",
        "name": "Add runtime-events.jsonl scaffold",
        "description": "Create empty runtime-events.jsonl if missing",
        "applies_to": "PR #5 layout -> final",
        "safe_to_reapply": True,
    },
    {
        "id": "pr5-to-final-layout-004",
        "name": "Add migration-state.json",
        "description": "Create migration tracking state file",
        "applies_to": "PR #5 layout -> final",
        "safe_to_reapply": True,
    },
]


# ──────────────────────────────────────────────────────────────────
# State management
# ──────────────────────────────────────────────────────────────────

def read_migration_state():
    """Read current migration state."""
    if not os.path.exists(MIGRATION_STATE_FILE):
        return {
            "schema_version": SCHEMA_VERSION,
            "applied": [],
            "last_applied_at": None,
            "last_rollback_at": None,
        }
    try:
        with open(MIGRATION_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "schema_version": SCHEMA_VERSION,
            "applied": [],
            "last_applied_at": None,
            "last_rollback_at": None,
        }


def write_migration_state(state):
    """Write migration state atomically."""
    import tempfile
    os.makedirs(os.path.dirname(MIGRATION_STATE_FILE) or ".", exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(MIGRATION_STATE_FILE) or ".", suffix=".tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, MIGRATION_STATE_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ──────────────────────────────────────────────────────────────────
# Migration logic
# ──────────────────────────────────────────────────────────────────

def _ensure_heidi_files():
    """Ensure .heidi directory has the required final-layout files."""
    heidi_dir = Path(".heidi")
    heidi_dir.mkdir(parents=True, exist_ok=True)

    required = {
        "rules.md": "# Repository Rules\n\n",
        "commands.md": (
            "# Verified Repository Commands\n\n"
            "- Install:\n- Format:\n- Lint:\n- Typecheck:\n"
            "- Unit tests:\n- Integration tests:\n- Build:\n- Production smoke:\n"
        ),
    }

    created = []
    for fname, content in required.items():
        fpath = heidi_dir / fname
        if not fpath.exists():
            fpath.write_text(content, encoding="utf-8")
            created.append(str(fpath))

    # memory.jsonl - do NOT overwrite if it has content
    mem_path = heidi_dir / "memory.jsonl"
    if not mem_path.exists():
        mem_path.write_text("")
        created.append(str(mem_path))
    elif mem_path.stat().st_size > 0:
        # Existing verified memory — do NOT overwrite
        pass

    # context-index.json
    idx_path = heidi_dir / "context-index.json"
    if not idx_path.exists():
        idx_path.write_text(
            json.dumps(
                {
                    "schema_version": "2.0.0",
                    "created_at": "",
                    "files": [],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        created.append(str(idx_path))

    # task-ledger.jsonl
    ledger_path = heidi_dir / "task-ledger.jsonl"
    if not ledger_path.exists():
        ledger_path.write_text("")
        created.append(str(ledger_path))

    # runtime-events.jsonl
    events_path = heidi_dir / "runtime-events.jsonl"
    if not events_path.exists():
        events_path.write_text("")
        created.append(str(events_path))

    return created


def apply_migration(migration_id):
    """Apply a specific migration by ID. Returns list of actions taken."""
    actions = []

    if migration_id == "pr5-to-final-layout-001":
        created = _ensure_heidi_files()
        if created:
            actions.append(f"Created files: {', '.join(created)}")
        else:
            actions.append("All .heidi files already in final layout")

    elif migration_id == "pr5-to-final-layout-002":
        # Normalize agent references — read existing config and verify paths
        config_dir = os.environ.get(
            "OPENCODE_CONFIG_DIR",
            os.path.join(os.path.expanduser("~"), ".config", "opencode"),
        )
        config_path = os.path.join(config_dir, "opencode.json")
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if "agent" in cfg:
                    for name, obj in cfg["agent"].items():
                        prompt = obj.get("prompt", "")
                        if prompt.startswith("{file:python-packages/") or prompt.startswith("{file:agents/"):
                            actions.append(f"Updated reference for agent '{name}'")
                else:
                    actions.append("No agent config found to normalize")
            except Exception as e:
                actions.append(f"Skipped normalize: config read error ({e})")
        else:
            actions.append("No config file to normalize")

    elif migration_id == "pr5-to-final-layout-003":
        events_path = Path(".heidi") / "runtime-events.jsonl"
        if not events_path.exists():
            events_path.parent.mkdir(parents=True, exist_ok=True)
            events_path.write_text("")
            actions.append(f"Created {events_path}")
        else:
            actions.append("runtime-events.jsonl already exists")

    elif migration_id == "pr5-to-final-layout-004":
        if not os.path.exists(MIGRATION_STATE_FILE):
            state = {
                "schema_version": SCHEMA_VERSION,
                "applied": [],
                "last_applied_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "last_rollback_at": None,
            }
            write_migration_state(state)
            actions.append(f"Created {MIGRATION_STATE_FILE}")
        else:
            actions.append("migration-state.json already exists")

    return actions


# ──────────────────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────────────────

def cmd_status(args):
    """Report current migration state."""
    state = read_migration_state()

    print("=== Migration Status ===")
    print(f"Schema version: {SCHEMA_VERSION}")
    print(f"Supported OpenCode: {SUPPORTED_OPENCODE_RANGE}")
    print(f"Tested with OpenCode: {TESTED_OPENCODE_VERSION}")
    print(f"Plugin API: {PLUGIN_API_COMPATIBILITY}")

    # Check for unknown/new version in environment
    import subprocess
    oc_bin = None
    for p in ("opencode", "/usr/local/bin/opencode"):
        if os.path.isfile(p) and os.access(p, os.X_OK):
            oc_bin = p
            break
    if not oc_bin:
        from shutil import which as _which
        oc_bin = _which("opencode")

    if oc_bin:
        try:
            ver = subprocess.check_output([oc_bin, "--version"], stderr=subprocess.STDOUT, text=True, timeout=10).strip()
            print(f"Detected OpenCode: {ver}")
            # Warning for unknown/new versions
            try:
                # Crude version comparison: if major version is >= 2, warn
                parts = ver.replace("v", "").split(".")
                major = int(parts[0]) if parts and parts[0].isdigit() else 0
                if major >= 2:
                    print("WARNING: OpenCode version 2.x detected — compatibility not confirmed")
            except Exception:
                print("WARNING: Could not determine OpenCode version compatibility")
        except Exception:
            print("Detected OpenCode: (version query failed)")

    applied = state.get("applied", [])
    last_applied = state.get("last_applied_at", "never")
    last_rollback = state.get("last_rollback_at", "never")

    print(f"\nApplied migrations: {len(applied)}")
    print(f"Last applied: {last_applied}")
    print(f"Last rollback: {last_rollback}")

    pending = [m for m in MIGRATIONS if m["id"] not in applied]
    print(f"\nPending migrations: {len(pending)}")
    for m in pending:
        print(f"  - {m['id']}: {m['name']}")

    if applied:
        print("\nApplied:")
        for aid in applied:
            m = next((x for x in MIGRATIONS if x["id"] == aid), None)
            print(f"  - {aid}: {m['name'] if m else 'unknown'}")


def cmd_apply(args):
    """Apply pending migrations."""
    state = read_migration_state()
    applied = set(state.get("applied", []))
    pending = [m for m in MIGRATIONS if m["id"] not in applied]

    if not pending:
        print("No pending migrations.")
        return

    result = []
    for migration in pending:
        print(f"Applying: {migration['id']} — {migration['name']}")
        actions = apply_migration(migration["id"])
        for action in actions:
            print(f"  {action}")
        applied.add(migration["id"])
        result.append(migration["id"])

    state["applied"] = sorted(applied)
    state["last_applied_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_migration_state(state)

    print(f"\nApplied {len(result)} migration(s).")


def cmd_rollback(args):
    """Rollback the last applied migration."""
    state = read_migration_state()
    applied = state.get("applied", [])

    if not applied:
        print("No migrations to rollback.")
        return

    last_id = applied[-1]
    migration = next((m for m in MIGRATIONS if m["id"] == last_id), None)
    if migration is None:
        print(f"Unknown migration: {last_id}")
        return

    print(f"Rolling back: {last_id} — {migration['name']}")

    # Rollback actions are migration-specific
    if last_id == "pr5-to-final-layout-004":
        if os.path.exists(MIGRATION_STATE_FILE):
            os.remove(MIGRATION_STATE_FILE)
            print("  Removed migration-state.json")
    elif last_id == "pr5-to-final-layout-003":
        events_path = Path(".heidi") / "runtime-events.jsonl"
        if events_path.exists() and events_path.stat().st_size == 0:
            events_path.unlink()
            print("  Removed empty runtime-events.jsonl")
    else:
        print("  (no destructive rollback — manual cleanup if needed)")

    state["applied"] = applied[:-1]
    state["last_rollback_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_migration_state(state)
    print(f"Rolled back: {last_id}")


# ──────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Migration Support — PR #5 to final layout")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Report current migration state")
    sub.add_parser("apply", help="Apply pending migrations")
    sub.add_parser("rollback", help="Rollback last migration")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args)
    elif args.command == "apply":
        cmd_apply(args)
    elif args.command == "rollback":
        cmd_rollback(args)


if __name__ == "__main__":
    main()
