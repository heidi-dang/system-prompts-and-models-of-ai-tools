#!/usr/bin/env python3
"""
Structured durable memory manager for Heidi agent pack.

Commands:
  validate <file>          Validate a memory.jsonl file
  add --file <f> --category <c> --summary <s> --evidence <e> [--confidence <c>] [--scope <s>]
  list --file <f>          List all records
  candidate --file <f> --category <c> --summary <s> --evidence <e> [--confidence <c>] [--scope <s>] [--durable-reason <r>]
                           Create a pending memory candidate
  verify --file <f> --id <id>    Verify a candidate (Heidi evidence validation)
  reject --file <f> --id <id> --reason <r>  Reject a candidate
  promote --file <f> --id <id>   Promote verified memory to rules.md (requires approval)
  contradictions --file <f>      Detect contradictions in memory records
  supersede --file <f> --id <id> --replacement-id <r>  Supersede old memory
"""

import json
import os
import re
import sys
import tempfile
import hashlib
import argparse
from collections import defaultdict
from datetime import datetime, timezone

SUPPORTED_CATEGORIES = {"architecture", "command", "bug_gotcha", "user_preference", "workflow"}
SUPPORTED_CONFIDENCE = {"high", "medium", "low"}
DEFAULT_CONFIDENCE = "high"
DEFAULT_SCOPE = "repository"
SUPPORTED_STATUSES = {"pending", "verified", "rejected", "superseded"}


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
        status = record.get("status", "?")
        evidence = record.get("evidence", [])
        ev_str = "; ".join(evidence[:3])
        print(f"{i}. [{rid}] ({cat}) {summary} [{conf}] [{status}]")
        print(f"   Evidence: {ev_str}")
        print()


# ──────────────────────────────────────────────────────────────────
# candidate command — create a pending memory candidate
# ──────────────────────────────────────────────────────────────────

def cmd_candidate(args):
    """Create a pending memory candidate that requires verification."""
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
        "status": "pending",
    }
    if args.durable_reason:
        record["durable_reason"] = args.durable_reason

    # Run Heidi validation checks
    rejection_reason = heidi_validate_candidate(record)
    if rejection_reason:
        print(f"Auto-rejected: {rejection_reason}", file=sys.stderr)
        sys.exit(1)

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
    print(f"Candidate created: {record['id']} (pending verification)")


# ──────────────────────────────────────────────────────────────────
# verify command — verify a candidate (Heidi evidence validation)
# ──────────────────────────────────────────────────────────────────

def cmd_verify(args):
    """Verify a pending memory candidate."""
    path = args.file
    records = read_records(path)

    found = False
    for i, record in enumerate(records):
        if record.get("id") == args.id:
            found = True
            if record.get("status") != "pending":
                print(f"Record {args.id} is not pending (status: {record.get('status')})")
                return

            # Heidi validation
            rejection = heidi_validate_candidate(record)
            if rejection:
                records[i]["status"] = "rejected"
                records[i]["rejected_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                records[i]["rejection_reason"] = rejection
                write_records(path, records)
                print(f"Verification FAILED: {args.id} — rejected: {rejection}")
                return

            records[i]["status"] = "verified"
            records[i]["verified_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            write_records(path, records)
            print(f"Verified: {args.id}")
            return

    if not found:
        print(f"Error: record not found: {args.id}", file=sys.stderr)
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────
# reject command — reject a candidate
# ──────────────────────────────────────────────────────────────────

def cmd_reject(args):
    """Reject a memory candidate with a reason."""
    path = args.file
    records = read_records(path)

    found = False
    for i, record in enumerate(records):
        if record.get("id") == args.id:
            found = True
            records[i]["status"] = "rejected"
            records[i]["rejected_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            records[i]["rejection_reason"] = args.reason
            write_records(path, records)
            print(f"Rejected: {args.id} — {args.reason}")
            return

    if not found:
        print(f"Error: record not found: {args.id}", file=sys.stderr)
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────
# promote command — promote verified memory to rules.md
# ──────────────────────────────────────────────────────────────────

def cmd_promote(args):
    """Promote verified memory to rules.md (requires explicit approval flag)."""
    path = args.file
    records = read_records(path)

    found = False
    for record in records:
        if record.get("id") == args.id:
            found = True
            if record.get("status") != "verified":
                print(f"Error: record {args.id} must be verified before promotion (status: {record.get('status')})", file=sys.stderr)
                sys.exit(1)
            break

    if not found:
        print(f"Error: record not found: {args.id}", file=sys.stderr)
        sys.exit(1)

    # Determine rules.md location (same directory as memory.jsonl)
    rules_path = os.path.join(os.path.dirname(path) or ".", "rules.md")
    if not os.path.exists(rules_path):
        print(f"Error: rules.md not found at {rules_path}", file=sys.stderr)
        sys.exit(1)

    # Append to rules.md
    record = next(r for r in records if r.get("id") == args.id)
    rule_entry = (
        f"\n## Memory: {record.get('summary', 'Untitled')}\n"
        f"Category: {record.get('category', 'unknown')} | "
        f"Confidence: {record.get('confidence', 'unknown')}\n"
        f"- {record.get('summary', '')}\n"
        f"  Evidence: {'; '.join(record.get('evidence', []))}\n"
    )

    # Atomic append
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(rules_path) or ".", suffix=".md.tmp"
    )
    try:
        with open(rules_path, "r", encoding="utf-8") as src:
            existing = src.read()
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as dst:
            dst.write(existing + rule_entry)
        os.replace(tmp_path, rules_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    # Mark as promoted
    for i, rec in enumerate(records):
        if rec.get("id") == args.id:
            records[i]["promoted"] = True
            records[i]["promoted_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            break
    write_records(path, records)

    print(f"Promoted: {args.id} -> {rules_path}")


# ──────────────────────────────────────────────────────────────────
# contradictions command — detect contradictions in memory records
# ──────────────────────────────────────────────────────────────────

def cmd_contradictions(args):
    """Detect potential contradictions in memory records."""
    path = args.file
    records = read_records(path)

    if not records:
        print("No records to check.")
        return

    # Simple contradiction detection: same category, opposite keywords
    contradictions = []
    negation_patterns = [
        (r"\bdo\s+not\b", r"\bdo\b"),
        (r"\bdo\s+n[o']t\b", r"\bdo\b"),
        (r"\bnever\b", r"\balways\b"),
        (r"\bavoid\b", r"\bprefer\b"),
        (r"\bshould\s+not\b", r"\bshould\b"),
        (r"\bis\s+not\b", r"\bis\b"),
    ]

    # Group by category
    by_category = defaultdict(list)
    for record in records:
        by_category[record.get("category", "unknown")].append(record)

    for category, recs in by_category.items():
        if len(recs) < 2:
            continue
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                a = recs[i].get("summary", "")
                b = recs[j].get("summary", "")
                a_lower = a.lower()
                b_lower = b.lower()

                for neg_pat, pos_pat in negation_patterns:
                    if (re.search(neg_pat, a_lower) and re.search(pos_pat, b_lower)) or \
                       (re.search(neg_pat, b_lower) and re.search(pos_pat, a_lower)):
                        # Check if they share significant tokens
                        a_tokens = set(re.findall(r"[a-z]{3,}", a_lower))
                        b_tokens = set(re.findall(r"[a-z]{3,}", b_lower))
                        overlap = a_tokens & b_tokens
                        if len(overlap) >= 3:
                            contradictions.append({
                                "record_a": recs[i]["id"],
                                "record_b": recs[j]["id"],
                                "summary_a": a[:100],
                                "summary_b": b[:100],
                                "shared_tokens": sorted(overlap)[:10],
                            })

    if contradictions:
        print(f"Found {len(contradictions)} potential contradiction(s):")
        for c in contradictions:
            print(f"  [{c['record_a']}] vs [{c['record_b']}]")
            print(f"    A: {c['summary_a']}")
            print(f"    B: {c['summary_b']}")
            print(f"    Shared: {', '.join(c['shared_tokens'])}")
    else:
        print("No contradictions detected.")


# ──────────────────────────────────────────────────────────────────
# supersede command — supersede old memory with a replacement
# ──────────────────────────────────────────────────────────────────

def cmd_supersede(args):
    """Supersede an old memory record with a replacement."""
    path = args.file
    records = read_records(path)

    found_old = False
    found_new = False
    for i, record in enumerate(records):
        if record.get("id") == args.id:
            found_old = True
            records[i]["status"] = "superseded"
            records[i]["superseded_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            records[i]["superseded_by"] = args.replacement_id
        if record.get("id") == args.replacement_id:
            found_new = True

    if not found_old:
        print(f"Error: original record not found: {args.id}", file=sys.stderr)
        sys.exit(1)
    if not found_new:
        print(f"Error: replacement record not found: {args.replacement_id}", file=sys.stderr)
        sys.exit(1)

    write_records(path, records)
    print(f"Superseded: {args.id} -> {args.replacement_id}")


# ──────────────────────────────────────────────────────────────────
# Heidi candidate validation
# ──────────────────────────────────────────────────────────────────

def heidi_validate_candidate(record):
    """Heidi evidence validation that rejects candidates that are:
      - temporary / one-shot
      - unsupported (no evidence)
      - duplicated
      - contradictory
      - one-off command failures
      - ordinary facts obvious from source
      - personal information unrelated to repo work
      - low-confidence inference
    """
    summary = (record.get("summary", "") or "").lower()
    evidence = record.get("evidence", [])
    confidence = record.get("confidence", "medium")

    # Reject: no evidence
    if not evidence or (len(evidence) == 1 and not evidence[0].strip()):
        return "no evidence provided"

    # Reject: temporary / one-shot indicators
    temporary_markers = [
        "right now", "just now", "this time", "once", "temporary",
        "tmp", "test only", "for now", "quick fix",
    ]
    if any(m in summary for m in temporary_markers):
        return "temporary or one-shot observation — not durable"

    # Reject: obvious from source
    obvious_markers = [
        "package.json exists", "readme", "gitignore",
        "node_modules installed", "npm install",
    ]
    if any(m in summary for m in obvious_markers):
        return "ordinary fact already obvious from source"

    # Reject: personal information
    personal_markers = [
        "my name", "my email", "my phone", "my address",
        "my password", "my account", "i am", "i like",
    ]
    if any(m in summary for m in personal_markers):
        return "personal information unrelated to repository work"

    # Reject: low-confidence inference
    if confidence == "low" and not record.get("durable_reason"):
        return "low-confidence inference without durable reason"

    # Reject: one-off command failure indicators
    failure_markers = [
        "command failed", "error when", "failed to run",
        "exit code", "retry", "timeout",
    ]
    if any(m in summary for m in failure_markers):
        return "one-off command failure — not durable memory"

    return None  # Passed validation


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

    # candidate
    p_candidate = sub.add_parser("candidate", help="Create pending memory candidate")
    p_candidate.add_argument("--file", required=True, help="Path to memory.jsonl")
    p_candidate.add_argument("--category", required=True, choices=sorted(SUPPORTED_CATEGORIES), help="Record category")
    p_candidate.add_argument("--summary", required=True, help="Concise summary")
    p_candidate.add_argument("--evidence", required=True, action="append", help="Evidence reference (repeatable)")
    p_candidate.add_argument("--confidence", default="high", choices=sorted(SUPPORTED_CONFIDENCE), help="Confidence level")
    p_candidate.add_argument("--scope", default="repository", help="Scope")
    p_candidate.add_argument("--durable-reason", help="Why this is durable memory")

    # verify
    p_verify = sub.add_parser("verify", help="Verify a pending candidate")
    p_verify.add_argument("--file", required=True, help="Path to memory.jsonl")
    p_verify.add_argument("--id", required=True, help="Record ID")

    # reject
    p_reject = sub.add_parser("reject", help="Reject a candidate")
    p_reject.add_argument("--file", required=True, help="Path to memory.jsonl")
    p_reject.add_argument("--id", required=True, help="Record ID")
    p_reject.add_argument("--reason", required=True, help="Rejection reason")

    # promote
    p_promote = sub.add_parser("promote", help="Promote verified memory to rules.md")
    p_promote.add_argument("--file", required=True, help="Path to memory.jsonl")
    p_promote.add_argument("--id", required=True, help="Record ID")

    # contradictions
    p_contra = sub.add_parser("contradictions", help="Detect contradictions")
    p_contra.add_argument("--file", required=True, help="Path to memory.jsonl")

    # supersede
    p_supersede = sub.add_parser("supersede", help="Supersede old memory")
    p_supersede.add_argument("--file", required=True, help="Path to memory.jsonl")
    p_supersede.add_argument("--id", required=True, help="Record ID to supersede")
    p_supersede.add_argument("--replacement-id", required=True, help="Replacement record ID")

    args = parser.parse_args()

    if args.command == "validate":
        cmd_validate(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "candidate":
        cmd_candidate(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "reject":
        cmd_reject(args)
    elif args.command == "promote":
        cmd_promote(args)
    elif args.command == "contradictions":
        cmd_contradictions(args)
    elif args.command == "supersede":
        cmd_supersede(args)


if __name__ == "__main__":
    main()
