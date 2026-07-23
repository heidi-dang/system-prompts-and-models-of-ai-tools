#!/usr/bin/env python3
"""
Structured durable memory manager for Heidi agent pack.

Commands:
  validate <file>          Validate a memory.jsonl file
  add --file <f> --category <c> --summary <s> --evidence <e> [--confidence <c>] [--scope <s>]
  list --file <f>          List all records
"""

import json
import os
import sys
import tempfile
import hashlib
import argparse
from datetime import datetime, timezone

SUPPORTED_CATEGORIES = {"architecture", "command", "bug_gotcha", "user_preference", "workflow"}
SUPPORTED_CONFIDENCE = {"high", "medium", "low"}
DEFAULT_CONFIDENCE = "high"
DEFAULT_SCOPE = "repository"


def stable_id(category, summary, scope):
    """Produce a deterministic stable ID from content."""
    raw = f"{category}:{summary}:{scope}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def read_records(path):
    """Read memory.jsonl, return list of parsed records."""
    records = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Error: line {i}: invalid JSON: {e}", file=sys.stderr)
                sys.exit(3)
            records.append(record)
    return records


def write_records(path, records):
    """Write records atomically to path."""
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".jsonl.tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, sort_keys=True) + "\n")
        os.replace(tmp_path, path)
    except Exception as exc:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        print(f"Error: atomic write failed: {exc}", file=sys.stderr)
        sys.exit(4)


def validate_record(record):
    """Validate a single record, return list of errors."""
    errors = []
    if "id" not in record or not isinstance(record["id"], str):
        errors.append("missing or invalid 'id'")
    if "created_at" not in record:
        errors.append("missing 'created_at'")
    if "category" not in record or record.get("category") not in SUPPORTED_CATEGORIES:
        errors.append(f"unsupported category '{record.get('category')}'. Supported: {SUPPORTED_CATEGORIES}")
    if "summary" not in record or not record.get("summary", "").strip():
        errors.append("missing or empty 'summary'")
    if "evidence" not in record or not isinstance(record.get("evidence"), list) or len(record["evidence"]) == 0:
        errors.append("missing or empty 'evidence' list")
    if "confidence" in record and record["confidence"] not in SUPPORTED_CONFIDENCE:
        errors.append(f"unsupported confidence '{record['confidence']}'. Supported: {SUPPORTED_CONFIDENCE}")
    return errors


def cmd_validate(args):
    """Validate a memory.jsonl file."""
    path = args.file
    records = read_records(path)
    total_errors = 0
    for i, record in enumerate(records, 1):
        errors = validate_record(record)
        if errors:
            print(f"Record {i} ({record.get('id', 'unknown')}): {'; '.join(errors)}")
            total_errors += 1
    if total_errors:
        print(f"Validation FAILED: {total_errors} invalid record(s) in {path}", file=sys.stderr)
        sys.exit(1)
    print(f"Validation PASSED: {len(records)} valid record(s) in {path}")


def cmd_add(args):
    """Add a validated, deduplicated record."""
    path = args.file
    create_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = {
        "id": stable_id(args.category, args.summary, args.scope or DEFAULT_SCOPE),
        "created_at": create_time,
        "category": args.category,
        "summary": args.summary,
        "evidence": [args.evidence] if isinstance(args.evidence, str) else args.evidence if isinstance(args.evidence, list) else [str(args.evidence)],
        "confidence": args.confidence or DEFAULT_CONFIDENCE,
        "scope": args.scope or DEFAULT_SCOPE,
        "status": "verified",
    }

    errors = validate_record(record)
    if errors:
        print(f"Error: invalid record: {'; '.join(errors)}", file=sys.stderr)
        sys.exit(1)

    records = read_records(path)

    # Deduplicate by ID
    existing_ids = {r.get("id") for r in records}
    if record["id"] in existing_ids:
        print(f"Skipped (duplicate): {record['id']}")
        return

    records.append(record)
    write_records(path, records)
    print(f"Added: {record['id']}")


def cmd_list(args):
    """List all records."""
    path = args.file
    records = read_records(path)
    if not records:
        print("No records.")
        return
    for i, record in enumerate(records, 1):
        rid = record.get("id", "?")
        cat = record.get("category", "?")
        summary = record.get("summary", "?")
        conf = record.get("confidence", "?")
        evidence = record.get("evidence", [])
        ev_str = "; ".join(evidence[:3])
        print(f"{i}. [{rid}] ({cat}) {summary} [{conf}]")
        print(f"   Evidence: {ev_str}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Heidi durable memory manager")
    sub = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = sub.add_parser("validate", help="Validate a memory.jsonl file")
    p_val.add_argument("file", help="Path to memory.jsonl")

    # add
    p_add = sub.add_parser("add", help="Add a validated record")
    p_add.add_argument("--file", required=True, help="Path to memory.jsonl")
    p_add.add_argument("--category", required=True, choices=sorted(SUPPORTED_CATEGORIES), help="Record category")
    p_add.add_argument("--summary", required=True, help="Concise summary")
    p_add.add_argument("--evidence", required=True, action="append", help="Evidence reference (repeatable)")
    p_add.add_argument("--confidence", default="high", choices=sorted(SUPPORTED_CONFIDENCE), help="Confidence level")
    p_add.add_argument("--scope", default="repository", help="Scope (default: repository)")

    # list
    p_list = sub.add_parser("list", help="List records")
    p_list.add_argument("--file", required=True, help="Path to memory.jsonl")

    args = parser.parse_args()

    if args.command == "validate":
        cmd_validate(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)


if __name__ == "__main__":
    main()
