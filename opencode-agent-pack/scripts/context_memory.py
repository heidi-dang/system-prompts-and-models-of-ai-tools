#!/usr/bin/env python3
"""
Context Memory v2 — repository context index for Heidi agent pack.

Commands:
  init <dir>          Create .heidi directory with needed files
  index --root <r> --out <f>  Generate context-index.json
  search --index <f> --query <q>  Search context index
  retrieve --index <f> --query <q> [--max-results auto] [--max-chars auto] [--format runtime]
      Enhanced search with BM25-style scoring
  fingerprint --root <r>  Compute repository fingerprint
  stale --index <f> --root <r>  Check if index is stale
  refresh --root <r> --out <f>  Conditionally refresh only when stale
  validate <dir>      Validate .heidi directory contents
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import mimetypes
from collections import Counter
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

# ── Retrieval weighting constants ──────────────────────────────────
HEADING_WEIGHT = 2.5
EXACT_PATH_MATCH_WEIGHT = 6.0
TOKEN_MATCH_WEIGHT = 1.0
FILE_TYPE_WEIGHTS = {
    ".py": 1.2, ".js": 1.1, ".ts": 1.15, ".tsx": 1.1, ".jsx": 1.05,
    ".md": 1.3, ".json": 0.9, ".yaml": 0.95, ".yml": 0.95, ".toml": 0.95,
    ".sh": 1.15, ".rs": 1.1, ".go": 1.1, ".sql": 1.05, ".prisma": 1.2,
    ".css": 0.85, ".scss": 0.85, ".html": 0.9,
    ".dockerfile": 1.0, ".env": 0.8, ".gitignore": 0.7,
}
RECENT_CHANGE_WEIGHT = 1.3
RULES_WEIGHT = 1.5
COMMANDS_WEIGHT = 1.4
MEMORY_EVIDENCE_WEIGHT = 1.25
EXCLUDE_PATTERNS = [
    r"\.lock$", r"\.min\.", r"\.bundle\.", r"\.generated\.",
    r"/dist/", r"/build/", r"/\.next/", r"/node_modules/",
    r"\.pyc$", r"\.pyo$", r"\.o$", r"\.so$", r"\.dll$", r"\.exe$",
    r"\.bin$", r"\.png$", r"\.jpg$", r"\.jpeg$", r"\.gif$",
    r"/private/", r"/secrets/", r"\.env$",
]

# ── Default retrieval configuration ───────────────────────────────
DEFAULT_MAX_RESULTS = 10
DEFAULT_MAX_CHARS = 8000
MAX_RESULTS_CAP = 50
MAX_CHARS_CAP = 50000


def is_excluded_path(relpath):
    """Check if path matches any exclusion pattern."""
    for pat in EXCLUDE_PATTERNS:
        if re.search(pat, relpath):
            return True
    return False


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


# ──────────────────────────────────────────────────────────────────
# retrieve command — enhanced BM25-style search
# ──────────────────────────────────────────────────────────────────

def _bm25_score(term_count, doc_freq, doc_count, doc_length, avg_doc_length, k1=1.2, b=0.75):
    """Simplified BM25-like scoring for term matching."""
    idf = math.log(1 + (doc_count - doc_freq + 0.5) / (doc_freq + 0.5))
    tf = (term_count * (k1 + 1)) / (term_count + k1 * (1 - b + b * doc_length / max(avg_doc_length, 1)))
    return idf * tf


def _tokenize(text):
    """Simple tokenizer: lowercase, split on non-alphanumeric."""
    return re.findall(r"[a-z0-9_]+", text.lower())


def _resolve_auto(value, default):
    """Resolve 'auto' to configured defaults."""
    if value is None or value == "auto":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def cmd_retrieve(args):
    """Enhanced search with BM25-style scoring, weighted by multiple signals."""
    # Load index
    with open(args.index, "r", encoding="utf-8") as f:
        index = json.load(f)

    max_results = min(_resolve_auto(args.max_results, DEFAULT_MAX_RESULTS), MAX_RESULTS_CAP)
    max_chars = min(_resolve_auto(args.max_chars, DEFAULT_MAX_CHARS), MAX_CHARS_CAP)
    query = args.query

    # Also load memory for evidence weighting
    memory_path = os.path.join(os.path.dirname(args.index), "memory.jsonl")
    memory_terms = set()
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        for ev in rec.get("evidence", []):
                            memory_terms.update(_tokenize(str(ev)))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

    # Preprocess files
    files = index.get("files", [])
    doc_count = len(files)
    all_terms = []
    query_terms = set(_tokenize(query))
    headings_cache = {}

    for entry in files:
        path_terms = set(_tokenize(entry.get("path", "")))
        heading_terms = set()
        for h in entry.get("headings", []):
            heading_terms.update(_tokenize(h))
        headings_cache[entry.get("path", "")] = heading_terms
        combined = path_terms | heading_terms
        all_terms.append(combined)

    avg_doc_terms = sum(len(t) for t in all_terms) / max(doc_count, 1) if doc_count else 1

    # Compute global doc frequency for each query term
    doc_freqs = {}
    for qt in query_terms:
        doc_freqs[qt] = sum(1 for terms in all_terms if qt in terms)

    # Score each file
    results = []
    for entry in files:
        relpath = entry.get("path", "")
        if is_excluded_path(relpath):
            continue

        path_lower = relpath.lower()
        ext = os.path.splitext(relpath)[1].lower()
        heading_terms = headings_cache.get(relpath, set())
        path_terms = set(_tokenize(relpath))

        score = 0.0

        # Exact path match (highest priority)
        query_lower = query.lower()
        if query_lower in path_lower:
            score += EXACT_PATH_MATCH_WEIGHT
        # Partial path match
        for qt in query_terms:
            if any(qt in pt for pt in path_terms):
                score += 0.5

        # Token matching with BM25-like scoring
        doc_terms = path_terms | heading_terms
        doc_length = len(doc_terms)
        for qt in query_terms:
            tf = sum(1 for t in doc_terms if qt in t)  # substring match in tokens
            df = doc_freqs.get(qt, 0)
            score += _bm25_score(tf, df, doc_count, doc_length, avg_doc_terms) * TOKEN_MATCH_WEIGHT

        # Weighted heading bonus
        for qt in query_terms:
            for ht in heading_terms:
                if qt in ht:
                    score += HEADING_WEIGHT / (max(doc_count, 1))

        # File-type weighting
        score *= FILE_TYPE_WEIGHTS.get(ext, 1.0)

        # Recent-change weighting (stub: use mod time if available)
        # We don't have mtime in the index currently, so skip

        # Rules/commands weighting
        if "rules" in path_lower or "commands" in path_lower:
            score *= RULES_WEIGHT if "rules" in path_lower else COMMANDS_WEIGHT

        # Memory evidence weighting
        for qt in query_terms:
            if qt in memory_terms:
                score *= MEMORY_EVIDENCE_WEIGHT
                break

        if score > 0:
            results.append((score, entry))

    # Sort by score descending
    results.sort(key=lambda x: -x[0])

    # Apply max_results, then apply character budget
    selected = []
    total_chars = 0
    for score, entry in results:
        if len(selected) >= max_results:
            break
        selected.append(entry)
        # Estimate char consumption: path + headings
        entry_chars = len(entry.get("path", "")) + sum(len(h) for h in entry.get("headings", []))
        total_chars += entry_chars

    # Output
    if args.format == "runtime":
        print(json.dumps({"results": selected}, indent=2, sort_keys=True))
    else:
        print(f"Results for '{query}' ({len(selected)} results, ~{min(total_chars, max_chars)} chars):")
        for entry in selected:
            hdr = ", ".join(entry.get("headings", [])[:3])
            print(f"  [{entry.get('language', '?')}] {entry['path']} (size={entry['size']}, headings=[{hdr}])")

    if not selected:
        print(f"(no matches for '{query}')")


# ──────────────────────────────────────────────────────────────────
# fingerprint command
# ──────────────────────────────────────────────────────────────────

def cmd_fingerprint(args):
    """Compute repository fingerprint from file hashes."""
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"Error: root directory not found: {root}", file=sys.stderr)
        sys.exit(1)

    hasher = hashlib.sha256()
    file_list = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        for fname in sorted(filenames):
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root)

            if is_ignored(rel_path):
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
                file_list.append((rel_path, sha.hexdigest(), fsize))
            except OSError:
                continue

    # Sort for deterministic output
    file_list.sort(key=lambda x: x[0])

    for path, sha_hex, size in file_list:
        hasher.update(f"{path}:{sha_hex}:{size}\n".encode("utf-8"))

    fingerprint = hasher.hexdigest()
    result = {
        "fingerprint": fingerprint,
        "total_files": len(file_list),
        "root": str(root),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


# ──────────────────────────────────────────────────────────────────
# stale command
# ──────────────────────────────────────────────────────────────────

def cmd_stale(args):
    """Check if the context index is stale compared to current repo state."""
    index_path = Path(args.index)
    root = Path(args.root).resolve()

    if not index_path.exists():
        print(json.dumps({"stale": True, "reason": "index not found"}, sort_keys=True))
        return

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except Exception as e:
        print(json.dumps({"stale": True, "reason": f"index read error: {e}"}, sort_keys=True))
        return

    indexed_files = {entry.get("path"): entry.get("sha256") for entry in index.get("files", [])}

    # Walk current repo and compare
    stale = False
    reasons = []
    current_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        for fname in sorted(filenames):
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root)

            if is_ignored(rel_path):
                continue
            if is_binary(full_path):
                continue

            current_count += 1

            if rel_path not in indexed_files:
                stale = True
                reasons.append(f"new file: {rel_path}")
                continue

            try:
                sha = hashlib.sha256()
                with open(full_path, "rb") as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        sha.update(chunk)
                if sha.hexdigest() != indexed_files[rel_path]:
                    stale = True
                    reasons.append(f"changed: {rel_path}")
            except OSError:
                stale = True
                reasons.append(f"unreadable: {rel_path}")

    # Check for removed files
    indexed_count = len(indexed_files)
    if current_count != indexed_count:
        stale = True
        reasons.append(f"file count mismatch: {current_count} current vs {indexed_count} indexed")

    result = {
        "stale": stale,
        "reason": "; ".join(reasons[:10]) if reasons else "index is up to date",
        "current_files": current_count,
        "indexed_files": indexed_count,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


# ──────────────────────────────────────────────────────────────────
# refresh command
# ──────────────────────────────────────────────────────────────────

def cmd_refresh(args):
    """Conditionally refresh context index only when stale."""
    index_path = Path(args.out).resolve()
    root = Path(args.root).resolve()

    # Check staleness first
    if index_path.exists():
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        except Exception:
            index = None

        if index:
            indexed_files = {entry.get("path"): entry.get("sha256") for entry in index.get("files", [])}
            stale = False
            current_count = 0

            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
                for fname in sorted(filenames):
                    full_path = os.path.join(dirpath, fname)
                    rel_path = os.path.relpath(full_path, root)

                    if is_ignored(rel_path):
                        continue
                    if is_binary(full_path):
                        continue

                    current_count += 1

                    if rel_path not in indexed_files:
                        stale = True
                        break

                    try:
                        sha = hashlib.sha256()
                        with open(full_path, "rb") as f:
                            while True:
                                chunk = f.read(8192)
                                if not chunk:
                                    break
                                sha.update(chunk)
                        if sha.hexdigest() != indexed_files[rel_path]:
                            stale = True
                            break
                    except OSError:
                        stale = True
                        break

            if current_count != len(indexed_files):
                stale = True

            if not stale:
                print("Index is current. No refresh needed.")
                return

    # Stale or missing — reindex
    print("Index is stale or missing. Refreshing...")
    # Simulate args for cmd_index
    class IndexArgs:
        pass
    idx_args = IndexArgs()
    idx_args.root = str(root)
    idx_args.out = str(index_path)
    cmd_index(idx_args)


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

    p_retrieve = sub.add_parser("retrieve", help="Enhanced retrieval with BM25 scoring")
    p_retrieve.add_argument("--index", required=True, help="Index file")
    p_retrieve.add_argument("--query", required=True, help="Search query")
    p_retrieve.add_argument("--max-results", default="auto", help="Max results or 'auto'")
    p_retrieve.add_argument("--max-chars", default="auto", help="Max character budget or 'auto'")
    p_retrieve.add_argument("--format", default="text", choices=["text", "runtime"], help="Output format")

    p_fingerprint = sub.add_parser("fingerprint", help="Compute repository fingerprint")
    p_fingerprint.add_argument("--root", required=True, help="Repository root")

    p_stale = sub.add_parser("stale", help="Check if index is stale")
    p_stale.add_argument("--index", required=True, help="Index file")
    p_stale.add_argument("--root", required=True, help="Repository root")

    p_refresh = sub.add_parser("refresh", help="Conditionally refresh stale index")
    p_refresh.add_argument("--root", required=True, help="Repository root")
    p_refresh.add_argument("--out", required=True, help="Output path for index")

    p_val = sub.add_parser("validate", help="Validate .heidi directory")
    p_val.add_argument("dir", help="Path to .heidi directory")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "index":
        cmd_index(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "retrieve":
        cmd_retrieve(args)
    elif args.command == "fingerprint":
        cmd_fingerprint(args)
    elif args.command == "stale":
        cmd_stale(args)
    elif args.command == "refresh":
        cmd_refresh(args)
    elif args.command == "validate":
        cmd_validate(args)


if __name__ == "__main__":
    main()
