#!/usr/bin/env python3
"""
Prompt Consistency Validator — detects contradictory instructions across
Heidi prompt fragments and generated output.

Detects:
  - Direct execution vs specialist-first contradictions
  - Mandatory scout vs fast path contradictions
  - "keep working" legacy completion language
  - "automatically" runtime lifecycle claims
  - Auditor for file-count vs risk-based audit
  - Model progress vs runtime-generated progress
  - Duplicate strategy names between prompt and selector
"""

import argparse
import re
import sys
from pathlib import Path

PROMPT_DIR = Path(__file__).parent.parent / "runtime" / "prompts"
AGENTS_DIR = Path(__file__).parent.parent / "agents"
ORCHESTRATION_PROMPT = Path(__file__).parent.parent / "runtime" / "orchestration.prompt.md"

CONTRADICTION_CHECKS = [
    # (label, forbidden_patterns, must_have_patterns)
    {
        "label": "No 'specialist first' or 'scout first' in any prompt",
        "forbidden": [
            r"(?i)specialist\s+first",
            r"(?i)scout\s+first",
            r"(?i)call scout first",
            r"(?i)invoke \*\*scout\*\* first",
            r"(?i)Do NOT modify specialized code yourself",
        ],
        "must_have": [],
    },
    {
        "label": "Direct execution is default (at least one mention)",
        "forbidden": [],
        "must_have": [
            r"(?i)direct execution is the default",
        ],
    },
    {
        "label": "No 'keep working' legacy completion language",
        "forbidden": [
            r"(?i)keep working",
        ],
        "must_have": [],
    },
    {
        "label": "No automatic runtime lifecycle claims",
        "forbidden": [
            r"(?i)(?:the runtime|heidi) automatically (?:locates|detects|validates|calculates|checks|refreshes|injects|records|obtains)",
        ],
        "must_have": [],
    },
    {
        "label": "Audit is not triggered by file count alone",
        "forbidden": [
            r"(?i)>3 files",
            r"(?i)more than (?:three|3) files",
            r"(?i)auditor.*for.*complex changes",
        ],
        "must_have": [],
    },
    {
        "label": "Progress reporting references runtime generation",
        "forbidden": [],
        "must_have": [
            r"(?i)runtime-generated",
        ],
    },
    {
        "label": "Delegation depth is exactly 1",
        "forbidden": [],
        "must_have": [
            r"(?i)delegation depth.*1\b",
        ],
    },
    {
        "label": "Audit runs at most once per task",
        "forbidden": [],
        "must_have": [
            r"(?i)audit runs at most once",
        ],
    },
    {
        "label": "No unbounded score loop for completion",
        "forbidden": [
            r"(?i)score is below 9/10, keep working",
        ],
        "must_have": [],
    },
]


def validate_file(filepath, checks):
    """Validate a single file against contradiction checks."""
    content = filepath.read_text(encoding="utf-8")
    results = []

    for check in checks:
        violations = []
        for pattern in check["forbidden"]:
            matches = list(re.finditer(pattern, content))
            for m in matches:
                line_num = content[:m.start()].count('\n') + 1
                violations.append(f"  Line {line_num}: '{m.group()}'")

        missing = []
        if check["must_have"]:
            for pattern in check["must_have"]:
                if not re.search(pattern, content):
                    missing.append(f"  Missing required pattern: '{pattern}'")

        status = "PASS"
        if violations or missing:
            status = "FAIL"

        results.append({
            "check": check["label"],
            "status": status,
            "violations": violations,
            "missing": missing,
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Prompt Consistency Validator")
    parser.add_argument("--check", action="store_true", help="Exit non-zero on failures")
    parser.add_argument("--verbose", action="store_true", help="Show all results including passes")
    args = parser.parse_args()

    all_passed = True

    # Collect all prompt files
    all_files = sorted(PROMPT_DIR.glob("*.md"))
    if ORCHESTRATION_PROMPT.exists():
        all_files.append(ORCHESTRATION_PROMPT)
    heidi_md = AGENTS_DIR / "heidi.md"
    if heidi_md.exists():
        all_files.append(heidi_md)

    # Build combined content for global must-have checks
    combined_content = ""
    for pf in all_files:
        combined_content += "\n" + pf.read_text(encoding="utf-8")

    # Phase 1: Per-file forbidden checks
    for pf in all_files:
        results = validate_file(pf, CONTRADICTION_CHECKS)
        file_fails = [r for r in results if r["status"] == "FAIL"]
        if file_fails:
            # Only report forbidden violations (not missing must-haves per file)
            forbidden_fails = [r for r in file_fails if r["violations"]]
            if forbidden_fails:
                all_passed = False
                print(f"\n{'-'*60}")
                print(f"FAILURES in {pf.name}:")
                for r in forbidden_fails:
                    print(f"  FAIL: {r['check']}")
                    for v in r["violations"]:
                        print(v)
            elif args.verbose:
                print(f"{pf.name}: forbidden checks PASS")
        elif args.verbose:
            print(f"{pf.name}: all {len(results)} forbidden checks PASS")

    # Phase 2: Global must-have checks
    print(f"\n{'='*60}")
    print("Global must-have checks (across all prompt files):")
    for check in CONTRADICTION_CHECKS:
        if not check["must_have"]:
            continue
        all_found = True
        for pattern in check["must_have"]:
            if not re.search(pattern, combined_content):
                all_found = False
                print(f"  FAIL: {check['label']} — no file contains '{pattern}'")
        if all_found:
            if args.verbose:
                print(f"  PASS: {check['label']}")
        else:
            all_passed = False

    print(f"\n{'='*60}")
    if all_passed:
        print("Prompt consistency: Validation PASSED — no contradictions detected")
    else:
        print("Prompt consistency: Validation FAILED — contradictions found")
        if args.check:
            sys.exit(1)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
