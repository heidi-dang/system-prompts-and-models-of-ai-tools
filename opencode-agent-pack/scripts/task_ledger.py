#!/usr/bin/env python3
"""
Task Ledger — durable task tracking for Heidi agent pack.

Commands:
  init <file>        Create empty task ledger
  start --file <f> --task-name <n> [--branch <b>]  Start a new task
  event --file <f> --task-id <id> [event params]    Record a task event
  finish --file <f> --task-id <id> --status <s> [--score <s>]  Close a task
  report --file <f>                                        Generate metrics report
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

VALID_AGENTS = {"heidi", "scout", "planner", "frontend", "backend", "debugger", "auditor"}
VALID_EVENT_TYPES = {"task_start", "delegation", "tool_result", "test_run", "audit_finding", "memory_candidate", "prompt_proposal", "task_finish", "strategy_selection"}
VALID_STATUS = {"pass", "fail", "blocked", "info", "done"}


def stable_id(*parts):
    raw = ":".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def read_records(path):
    records = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def write_records(path, records):
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".jsonl.tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, sort_keys=True) + "\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def cmd_init(args):
    path = args.file
    if os.path.exists(path):
        print("Already exists (idempotent)")
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write("")
    print(f"Created: {path}")


def cmd_start(args):
    create_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    task_id = stable_id(args.task_name, create_time)
    records = read_records(args.file)
    # Check not already started
    for r in records:
        if r.get("task_id") == task_id and r.get("type") == "task_start":
            print(f"Task already started: {task_id}")
            print(task_id)
            return

    event = {
        "id": stable_id(task_id, "start", create_time),
        "task_id": task_id,
        "created_at": create_time,
        "agent": "heidi",
        "type": "task_start",
        "summary": args.task_name,
        "status": "info",
        "evidence": [],
        "metrics": {"attempts": 0, "files_changed": 0, "tests_passed": 0, "tests_failed": 0},
    }
    if args.branch:
        event["branch"] = args.branch

    records.append(event)
    write_records(args.file, records)
    print(task_id)


def cmd_event(args):
    create_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Use summary in the ID to differentiate same-type events, but deduplicate identical ones
    event_id = stable_id(args.task_id, args.agent, args.type, args.summary)
    records = read_records(args.file)

    # Dedup: skip if same logical event already exists
    existing = {r.get("id") for r in records}
    if event_id in existing:
        print(event_id)
        print("Event already recorded")
        return

    if args.agent not in VALID_AGENTS:
        print(f"Error: invalid agent '{args.agent}'", file=sys.stderr)
        sys.exit(2)
    if args.status not in VALID_STATUS:
        print(f"Error: invalid status '{args.status}'", file=sys.stderr)
        sys.exit(2)
    if args.type not in VALID_EVENT_TYPES:
        print(f"Error: invalid event type '{args.type}'", file=sys.stderr)
        sys.exit(2)

    event = {
        "id": event_id,
        "task_id": args.task_id,
        "created_at": create_time,
        "agent": args.agent,
        "type": args.type,
        "summary": args.summary,
        "status": args.status,
        "evidence": [],
        "metrics": {"attempts": args.attempts or 1, "files_changed": 0, "tests_passed": 0, "tests_failed": 0},
    }
    if hasattr(args, "evidence") and args.evidence:
        event["evidence"] = args.evidence
    records.append(event)
    write_records(args.file, records)
    print(event_id)


def cmd_finish(args):
    create_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    event_id = stable_id(args.task_id, "finish", create_time)
    records = read_records(args.file)

    existing = {r.get("id") for r in records}
    if event_id in existing:
        print(f"Task already finished: {event_id}")
        return

    event = {
        "id": event_id,
        "task_id": args.task_id,
        "created_at": create_time,
        "agent": "heidi",
        "type": "task_finish",
        "summary": f"Task completed with status {args.status}",
        "status": args.status,
        "evidence": [],
        "metrics": {"attempts": 0, "files_changed": 0, "tests_passed": 0, "tests_failed": 0},
    }
    if args.score is not None:
        event["score"] = args.score
    records.append(event)
    write_records(args.file, records)
    print(f"Task {args.task_id} finished: {args.status}")


def cmd_report(args):
    records = read_records(args.file)
    if not records:
        print("No records in ledger.")
        return

    tasks = {}
    events_by_agent = {}
    statuses = {}
    scores = []
    total_failures = 0
    memory_candidates = 0
    prompt_proposals = 0
    total_retries = 0
    event_types = {}

    for r in records:
        tid = r.get("task_id", "?")
        if tid not in tasks:
            tasks[tid] = {"starts": 0, "finishes": 0, "events": 0}
        tasks[tid]["events"] += 1
        if r.get("type") == "task_start":
            tasks[tid]["starts"] += 1
        if r.get("type") == "task_finish":
            tasks[tid]["finishes"] += 1

        agent = r.get("agent", "?")
        events_by_agent[agent] = events_by_agent.get(agent, 0) + 1

        st = r.get("status", "?")
        statuses[st] = statuses.get(st, 0) + 1
        if st in ("fail", "blocked"):
            total_failures += 1

        et = r.get("type", "?")
        event_types[et] = event_types.get(et, 0) + 1

        if r.get("type") == "memory_candidate":
            memory_candidates += 1
        if r.get("type") == "prompt_proposal":
            prompt_proposals += 1

        score = r.get("score")
        if score is not None:
            scores.append(score)
        retries = r.get("metrics", {}).get("attempts", 1)
        if retries > 1:
            total_retries += (retries - 1)

    print("=== Task Ledger Report ===")
    print(f"Total tasks: {len(tasks)}")
    completed = sum(1 for t in tasks.values() if t["finishes"] > 0)
    blocked = sum(1 for t in tasks.values() if t["finishes"] == 0)
    print(f"Completed: {completed}")
    print(f"Active/blocked: {blocked}")
    avg_score = sum(scores) / len(scores) if scores else 0
    print(f"Average score: {avg_score:.1f}")
    print(f"Total failures: {total_failures}")
    print(f"Memory candidates: {memory_candidates}")
    print(f"Prompt proposals: {prompt_proposals}")
    print(f"Total retries: {total_retries}")
    print(f"\nEvents by agent:")
    for k, v in sorted(events_by_agent.items()):
        print(f"  {k}: {v}")
    print(f"\nEvent types:")
    for k, v in sorted(event_types.items()):
        print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Task Ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create empty task ledger")
    p_init.add_argument("file", help="Path to ledger file")

    p_start = sub.add_parser("start", help="Start a new task")
    p_start.add_argument("--file", required=True)
    p_start.add_argument("--task-name", required=True)
    p_start.add_argument("--branch")

    p_event = sub.add_parser("event", help="Record a task event")
    p_event.add_argument("--file", required=True)
    p_event.add_argument("--task-id", required=True)
    p_event.add_argument("--agent", required=True)
    p_event.add_argument("--type", required=True)
    p_event.add_argument("--summary", required=True)
    p_event.add_argument("--status", required=True)
    p_event.add_argument("--attempts", type=int, default=1)

    p_finish = sub.add_parser("finish", help="Close a task")
    p_finish.add_argument("--file", required=True)
    p_finish.add_argument("--task-id", required=True)
    p_finish.add_argument("--status", required=True, choices=VALID_STATUS)
    p_finish.add_argument("--score", type=float)

    p_report = sub.add_parser("report", help="Generate metrics report")
    p_report.add_argument("--file", required=True)

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "start":
        cmd_start(args)
    elif args.command == "event":
        cmd_event(args)
    elif args.command == "finish":
        cmd_finish(args)
    elif args.command == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()
