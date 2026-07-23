#!/usr/bin/env python3
"""
Context Memory v2 — repository context index for Heidi agent pack.

Commands:
  init <dir>          Create .heidi directory with needed files
  index --root <r> --out <f>  Generate context-index.json
  search --index <f> --query <q>  Search context index
  validate <dir>      Validate .heidi directory contents
"""

import argparse
import hashlib
import json
import os
import re
import sys
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "2.0.0"

# Directories and file patterns to ignore
IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".pytest_cache",
    ".venv", "venv", ".tox", "dist", "build", ".next",
    "target", ".turbo", ".cache", "coverage", ".nyc_output",
}

IGNORE_FILE_PATTERNS = [
    r"\.bak\.",
    r"\.tmp$",
    r"\.pyc$",
    r"\.pyo$",
    r"\.o$",
    r"\.so$",
    r"\.dll$",
    r"\.exe$",
    r"\.bin$",
    r"\.png$",
    r"\.jpg$",
    r"\.jpeg$",
    r"\.gif$",
    r"\.ico$",
    r"\.woff2?$",
    r"\.ttf$",
    r"\.eot$",
    r"^\.DS_Store$",
    r"^Thumbs\.db$",
]

TEST_FILE_PATTERNS = [
    r"^test_", r"_test\.", r"\.test\.", r"\.spec\.", r"/tests?/",
    r"__tests__", r"\.bats$",
]

CONFIG_FILE_NAMES = {
    "package.json", "tsconfig.json", "jsconfig.json",
    "vite.config.js", "vite.config.ts", "next.config.js", "next.config.ts",
    "pyproject.toml", "Cargo.toml", "go.mod", "Makefile",
    "biome.json", ".eslintrc.js", ".eslintrc.json", ".eslintrc.cjs",
    ".prettierrc", "ruff.toml", ".editorconfig",
    "schema.prisma", "drizzle.config.ts", "alembic.ini",
    "docker-compose.yml", "docker-compose.yaml",
    "jest.config.js", "jest.config.ts", "vitest.config.ts",
    "pytest.ini", "setup.cfg", "tox.ini",
}

DOC_FILE_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}

KNOWN_FILE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".css": "CSS",
    ".scss": "SCSS",
    ".html": "HTML",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".sh": "Shell",
    ".bash": "Shell",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".sql": "SQL",
    ".prisma": "Prisma",
    ".md": "Markdown",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "INI",
    ".env": "Env",
    ".gitignore": "Gitignore",
    ".dockerfile": "Dockerfile",
}

MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)

def is_binary(filepath):
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(1024)
        return b"\0" in chunk
    except Exception:
        return True

def is_ignored(relpath):
    name = os.path.basename(relpath)
    for d in IGNORE_DIRS:
        if d in relpath.split(os.sep):
            return True
    for pat in IGNORE_FILE_PATTERNS:
        if re.search(pat, name):
            return True
    return False

def detect_language(ext):
    return KNOWN_FILE_EXTENSIONS.get(ext.lower(), "Unknown")

def is_test_file(relpath):
    for pat in TEST_FILE_PATTERNS:
        if re.search(pat, relpath):
            return True
    return False

def extract_heading_keywords(filepath, ext):
    if ext.lower() != ".md":
        return []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(50000)
        return [m.group(1).strip() for m in MARKDOWN_HEADING_RE.finditer(content)]
    except Exception:
        return []

def extract_package_scripts(filepath):
    if os.path.basename(filepath) != "package.json":
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        scripts = data.get("scripts", {})
        return dict(scripts)
    except Exception:
        return {}


def cmd_init(args):
    target = Path(args.dir)
    target.mkdir(parents=True, exist_ok=True)

    files_created = []
    for name, content in [
        ("rules.md", "# Repository Rules\n\n"),
        ("commands.md", "# Verified Repository Commands\n\n- Install:\n- Format:\n- Lint:\n- Typecheck:\n- Unit tests:\n- Integration tests:\n- Build:\n- Production smoke:\n"),
    ]:
        path = target / name
        if not path.exists():
            path.write_text(content)
            files_created.append(str(path))

    mem_path = target / "memory.jsonl"
    if not mem_path.exists():
        mem_path.write_text("")
        files_created.append(str(mem_path))

    idx_path = target / "context-index.json"
    if not idx_path.exists():
        idx_path.write_text("""{
  "schema_version": "2.0.0",
  "created_at": "",
  "files": []
}\n""")
        files_created.append(str(idx_path))

    ledger_path = target / "task-ledger.jsonl"
    if not ledger_path.exists():
        ledger_path.write_text("")
        files_created.append(str(ledger_path))

    if files_created:
        for f in sorted(files_created):
            print(f"Created: {f}")
    else:
        print("All .heidi files already exist (idempotent)")


def cmd_index(args):
    root = Path(args.root).resolve()
    out_path = Path(args.out).resolve()
    # Exclude the output file itself from the scan
    try:
        out_rel = os.path.relpath(out_path, root)
    except ValueError:
        out_rel = None

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files_list = []
    total_size = 0
    languages = {}
    config_files = []
    test_files = []
    agent_files_list = []
    docs_files = []
    package_scripts = {}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        dirnames.sort()

        for fname in sorted(filenames):
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root)

            if is_ignored(rel_path):
                continue
            if out_rel and rel_path == out_rel:
                continue
            if is_binary(full_path):
                continue

            try:
                fsize = os.path.getsize(full_path)
                sha = hashlib.sha256()
                with open(full_path, "rb") as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        sha.update(chunk)
                sha_hex = sha.hexdigest()
            except OSError:
                continue

            ext = os.path.splitext(fname)[1]
            lang = detect_language(ext)
            languages[lang] = languages.get(lang, 0) + 1
            total_size += fsize

            headings = extract_heading_keywords(full_path, ext)
            is_test = is_test_file(rel_path)

            entry = {
                "path": rel_path,
                "size": fsize,
                "sha256": sha_hex,
                "language": lang,
                "is_test": is_test,
            }
            if headings:
                entry["headings"] = headings[:20]

            files_list.append(entry)

            if is_test:
                test_files.append(rel_path)

            if fname in CONFIG_FILE_NAMES or fname.endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".cfg")):
                if not is_test:
                    config_files.append(rel_path)

            if ext in DOC_FILE_EXTENSIONS and not is_test:
                docs_files.append(rel_path)

            if fname == "package.json" and not ("scripts" in str(Path(rel_path).parent)):
                scripts = extract_package_scripts(full_path)
                if scripts:
                    package_scripts.update(scripts)

            if "/agents/" in rel_path and rel_path.endswith(".md"):
                agent_files_list.append(rel_path)

    index = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created,
        "repository_root": str(root),
        "summary": {
            "total_files": len(files_list),
            "total_size_bytes": total_size,
            "languages": dict(sorted(languages.items())),
            "config_files": sorted(config_files),
            "test_files": sorted(test_files),
            "agent_files": sorted(agent_files_list),
            "docs_files": sorted(docs_files),
            "package_scripts": package_scripts,
        },
        "files": files_list,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"Indexed {len(files_list)} files to {out_path}")


def cmd_search(args):
    with open(args.index, "r", encoding="utf-8") as f:
        index = json.load(f)

    query = args.query.lower()
    results = []
    for entry in index.get("files", []):
        path_low = entry["path"].lower()
        headings_low = " ".join(entry.get("headings", [])).lower()
        lang_low = entry.get("language", "").lower()
        score = 0
        if query in path_low:
            score += 3
        if query in headings_low:
            score += 2
        if query in lang_low:
            score += 1
        if score:
            results.append((score, entry))

    results.sort(key=lambda x: (-x[0], x[1]["path"]))
    print(f"Results for '{args.query}':")
    for score, entry in results[:20]:
        print(f"  [{entry.get('language', '?')}] {entry['path']} (size={entry['size']}, score={score})")
    if not results:
        print("  (no matches)")


def cmd_validate(args):
    target = Path(args.dir)
    errors = []

    # Check required files
    for name in ["rules.md", "commands.md", "memory.jsonl", "context-index.json"]:
        if not (target / name).exists():
            errors.append(f"Missing: {name}")

    # Validate memory.jsonl
    mem_path = target / "memory.jsonl"
    if mem_path.exists():
        try:
            with open(mem_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if "id" not in record:
                            errors.append(f"memory.jsonl line {i}: missing id")
                        if "evidence" not in record:
                            errors.append(f"memory.jsonl line {i}: missing evidence")
                    except json.JSONDecodeError as e:
                        errors.append(f"memory.jsonl line {i}: invalid JSON: {e}")
        except Exception as e:
            errors.append(f"memory.jsonl: read error: {e}")

    # Validate context-index.json
    idx_path = target / "context-index.json"
    if idx_path.exists():
        try:
            with open(idx_path, "r", encoding="utf-8") as f:
                idx = json.load(f)
            if "schema_version" not in idx:
                errors.append("context-index.json: missing schema_version")
            paths_seen = set()
            for entry in idx.get("files", []):
                p = entry.get("path", "")
                if not p:
                    errors.append("context-index.json: entry with no path")
                elif p.startswith("/"):
                    errors.append(f"context-index.json: absolute path: {p}")
                elif p in paths_seen:
                    errors.append(f"context-index.json: duplicate path: {p}")
                else:
                    paths_seen.add(p)
                # Check for ignored directories
                for d in IGNORE_DIRS:
                    if d in p.split(os.sep):
                        errors.append(f"context-index.json: ignored directory '{d}' in path: {p}")
                        break
        except json.JSONDecodeError as e:
            errors.append(f"context-index.json: invalid JSON: {e}")
        except Exception as e:
            errors.append(f"context-index.json: read error: {e}")

    # commands.md check
    cmd_path = target / "commands.md"
    if cmd_path.exists():
        content = cmd_path.read_text(encoding="utf-8")
        if "Verified Repository Commands" not in content:
            errors.append("commands.md: missing expected header")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)
    else:
        print(f"Validation PASSED: {target}")


def main():
    parser = argparse.ArgumentParser(description="Context Memory v2")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create .heidi directory files")
    p_init.add_argument("dir", help="Target directory (.heidi)")

    p_index = sub.add_parser("index", help="Generate context index")
    p_index.add_argument("--root", required=True, help="Repository root")
    p_index.add_argument("--out", required=True, help="Output path")

    p_search = sub.add_parser("search", help="Search context index")
    p_search.add_argument("--index", required=True, help="Index file")
    p_search.add_argument("--query", required=True, help="Search query")

    p_val = sub.add_parser("validate", help="Validate .heidi directory")
    p_val.add_argument("dir", help="Path to .heidi directory")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "index":
        cmd_index(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "validate":
        cmd_validate(args)


if __name__ == "__main__":
    main()
