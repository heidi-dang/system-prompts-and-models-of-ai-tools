#!/usr/bin/env python3
"""
Runtime Event Stream — local runtime event management for Heidi agent pack.

Events are written to .heidi/runtime-events.jsonl (JSON Lines, append-only).

Valid event types:
  runtime_start, native_prompt_composed, context_retrieved, strategy_selected,
  fast_path_started, delegation_started, delegation_finished, test_completed,
  audit_completed, memory_candidate_processed, proposal_evaluated, task_finished,
  circuit_breaker_opened

Commands:
  event --file <f> --type <t> --task-id <id> --data <json>
  validate <file>
  report <file>

Requirements:
  - schema version in each event
  - stable event ID (SHA256)
  - timestamp (ISO 8601 UTC)
  - task ID
  - event type
  - concise metadata (no secrets, no raw prompts)
  - atomic append (temp file + os.replace)
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

# ──────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0.0"

VALID_EVENT_TYPES = {
    "runtime_start",
    "native_prompt_composed",
    "context_retrieved",
    "strategy_selected",
    "fast_path_started",
    "delegation_started",
    "delegation_finished",
    "test_completed",
    "audit_completed",
    "memory_candidate_processed",
    "proposal_evaluated",
    "task_finished",
    "circuit_breaker_opened",
}

# Fields that must never appear in event data (security)
SECRET_KEYWORDS = {
    "api_key", "apikey", "password", "secret", "token", "authorization",
    "credential", "private_key", "access_key", "jwt",
}


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def stable_event_id(event_type, task_id, timestamp, metadata_hash):
    """Produce a deterministic stable event ID from contents."""
    raw = f"{SCHEMA_VERSION}:{event_type}:{task_id}:{timestamp}:{metadata_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def scrub_secrets(data):
    """Recursively remove secret-like keys from metadata dict."""
    if not isinstance(data, dict):
        return data
    result = {}
    for k, v in data.items():
        k_lower = k.lower().replace("_", "").replace("-", "")
        if any(secret in k_lower for secret in SECRET_KEYWORDS):
            result[k] = "[REDACTED]"
        elif isinstance(v, dict):
            result[k] = scrub_secrets(v)
        elif isinstance(v, list):
            result[k] = [scrub_secrets(item) if isinstance(item, dict) else item for item in v]
        else:
            result[k] = v
    return result


def read_events(path):
    """Read all events from a JSONL file."""
    events = []
    if not os.path.exists(path):
        return events
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: line {i}: invalid JSON: {e}", file=sys.stderr)
    return events


def atomic_append(path, event):
    """Atomically append an event to a JSONL file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    # Read existing, append new record, write atomically
    records = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if line.strip():
                    records.append(line)

    event_line = json.dumps(event, sort_keys=True)

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(path) or ".", suffix=".jsonl.tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            for existing_line in records:
                f.write(existing_line + "\n")
            f.write(event_line + "\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ──────────────────────────────────────────────────────────────────
# event command
# ──────────────────────────────────────────────────────────────────

def cmd_event(args):
    """Record a runtime event."""
    if args.type not in VALID_EVENT_TYPES:
        print(f"Error: invalid event type '{args.type}'", file=sys.stderr)
        print(f"Valid types: {', '.join(sorted(VALID_EVENT_TYPES))}", file=sys.stderr)
        sys.exit(2)

    # Parse metadata
    try:
        metadata = json.loads(args.data) if args.data else {}
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON data: {e}", file=sys.stderr)
        sys.exit(2)

    if not isinstance(metadata, dict):
        print("Error: data must be a JSON object", file=sys.stderr)
        sys.exit(2)

    # Scrub secrets
    metadata = scrub_secrets(metadata)

    # Generate event
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    metadata_hash = hashlib.sha256(
        json.dumps(metadata, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]

    event = {
        "schema_version": SCHEMA_VERSION,
        "id": stable_event_id(args.type, args.task_id, timestamp, metadata_hash),
        "timestamp": timestamp,
        "task_id": args.task_id,
        "type": args.type,
        "metadata": metadata,
    }

    # Ensure metadata stays concise
    metadata_json = json.dumps(metadata, sort_keys=True)
    if len(metadata_json) > 4096:
        print(f"Warning: metadata size ({len(metadata_json)} bytes) exceeds recommended limit; truncating", file=sys.stderr)
        metadata = {"_truncated": True, "_original_size": len(metadata_json)}
        event["metadata"] = metadata

    atomic_append(args.file, event)
    print(event["id"])


# ──────────────────────────────────────────────────────────────────
# validate command
# ──────────────────────────────────────────────────────────────────

def cmd_validate(args):
    """Validate a runtime events file."""
    path = args.file
    if not os.path.exists(path):
        print(f"Validation PASSED: 0 event(s) in {path} (file does not exist)")
        return

    errors = []
    events = read_events(path)

    for i, event in enumerate(events, 1):
        # Required fields
        for field in ("schema_version", "id", "timestamp", "task_id", "type"):
            if field not in event:
                errors.append(f"line {i}: missing '{field}'")

        # Valid event type
        etype = event.get("type", "")
        if etype and etype not in VALID_EVENT_TYPES:
            errors.append(f"line {i}: invalid event type '{etype}'")

        # Schema version check
        sv = event.get("schema_version", "")
        if sv and sv != SCHEMA_VERSION:
            errors.append(f"line {i}: schema version mismatch (expected {SCHEMA_VERSION}, got {sv})")

        # ID format check
        eid = event.get("id", "")
        if eid and len(eid) != 64:
            errors.append(f"line {i}: unexpected ID format (expected 64-char hex)")

        # Timestamp format check
        ts = event.get("timestamp", "")
        if ts and not ts.endswith("Z"):
            errors.append(f"line {i}: timestamp not UTC (missing 'Z' suffix)")

        # Task ID presence
        tid = event.get("task_id", "")
        if tid and not isinstance(tid, str):
            errors.append(f"line {i}: task_id is not a string")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)
    print(f"Validation PASSED: {len(events)} event(s) in {path}")


# ──────────────────────────────────────────────────────────────────
# report command
# ──────────────────────────────────────────────────────────────────

def cmd_report(args):
    """Generate a summary report from runtime events."""
    path = args.file
    if not os.path.exists(path):
        print("No events file found.")
        return

    events = read_events(path)
    if not events:
        print("No events in file.")
        return

    type_counts = {}
    task_ids = set()
    date_range = [None, None]

    for event in events:
        etype = event.get("type", "unknown")
        type_counts[etype] = type_counts.get(etype, 0) + 1

        tid = event.get("task_id", "")
        if tid:
            task_ids.add(tid)

        ts = event.get("timestamp", "")
        if ts:
            if date_range[0] is None or ts < date_range[0]:
                date_range[0] = ts
            if date_range[1] is None or ts > date_range[1]:
                date_range[1] = ts

    print("=== Runtime Events Report ===")
    print(f"Total events: {len(events)}")
    print(f"Unique task IDs: {len(task_ids)}")
    print(f"Date range: {date_range[0] or 'N/A'} to {date_range[1] or 'N/A'}")
    print()

    print("Event type distribution:")
    for etype in sorted(type_counts.keys()):
        print(f"  {etype}: {type_counts[etype]}")

    # Circuit breaker events
    cb_events = [e for e in events if e.get("type") == "circuit_breaker_opened"]
    if cb_events:
        print(f"\nCircuit breaker openings: {len(cb_events)}")
        for e in cb_events:
            print(f"  {e.get('id', '?')} at {e.get('timestamp', '?')}")

    # Error/warning events (events with error metadata)
    error_events = [e for e in events if (e.get("metadata") or {}).get("error")]
    if error_events:
        print(f"\nError events: {len(error_events)}")


# ──────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Runtime Event Stream")
    sub = parser.add_subparsers(dest="command", required=True)

    p_event = sub.add_parser("event", help="Record a runtime event")
    p_event.add_argument("--file", required=True, help="Path to events file (.jsonl)")
    p_event.add_argument("--type", required=True, help="Event type")
    p_event.add_argument("--task-id", required=True, help="Task ID")
    p_event.add_argument("--data", default="{}", help="JSON metadata (no secrets)")

    p_val = sub.add_parser("validate", help="Validate an events file")
    p_val.add_argument("file", help="Path to events file")

    p_report = sub.add_parser("report", help="Generate report from events")
    p_report.add_argument("file", help="Path to events file")

    args = parser.parse_args()

    if args.command == "event":
        cmd_event(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()
