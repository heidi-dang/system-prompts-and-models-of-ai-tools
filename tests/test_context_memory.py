#!/usr/bin/env python3
"""Tests for context_memory.py"""
import json
import os
import shutil
import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "opencode-agent-pack", "scripts", "context_memory.py")

def run(*args):
    proc = subprocess.run(
        [sys.executable, SCRIPT] + list(args),
        capture_output=True, text=True, timeout=30
    )
    return proc.returncode, proc.stdout, proc.stderr

def make_fixture_repo(base):
    (base / "src").mkdir(parents=True, exist_ok=True)
    (base / "tests").mkdir(parents=True, exist_ok=True)
    (base / "docs").mkdir(parents=True, exist_ok=True)
    (base / ".git").mkdir(parents=True, exist_ok=True)
    (base / "node_modules").mkdir(parents=True, exist_ok=True)
    (base / "node_modules" / "dep").mkdir(parents=True, exist_ok=True)

    (base / "src" / "app.py").write_text("print('hello')\n")
    (base / "tests" / "test_app.py").write_text("def test_app(): pass\n")
    (base / "docs" / "README.md").write_text("# Project\n\n## Setup\n\nHello\n")
    (base / "package.json").write_text('{"name":"test","scripts":{"test":"jest","build":"tsc"}}')
    (base / "tsconfig.json").write_text("{}")
    (base / "biome.json").write_text("{}")
    (base / ".heidi").mkdir(exist_ok=True)
    (base / ".heidi" / "rules.md").write_text("# Rules\n- Rule 1\n")
    (base / "node_modules" / "dep" / "index.js").write_text("module.exports = {};")
    (base / ".git" / "config").write_text("[core]\n")


class TestContextMemory(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_init_idempotent(self):
        heidi_dir = self.tmp / ".heidi"
        rc, out, err = run("init", str(heidi_dir))
        self.assertEqual(rc, 0)
        self.assertTrue((heidi_dir / "rules.md").exists())
        self.assertTrue((heidi_dir / "commands.md").exists())
        self.assertTrue((heidi_dir / "memory.jsonl").exists())
        self.assertTrue((heidi_dir / "context-index.json").exists())
        self.assertTrue((heidi_dir / "task-ledger.jsonl").exists())
        # Run again - should be idempotent
        rc2, out2, err2 = run("init", str(heidi_dir))
        self.assertEqual(rc2, 0)
        self.assertIn("idempotent", out2)

    def test_index_excludes_ignored(self):
        make_fixture_repo(self.tmp)
        out_path = self.tmp / "index.json"
        rc, out, err = run("index", "--root", str(self.tmp), "--out", str(out_path))
        self.assertEqual(rc, 0)
        with open(out_path) as f:
            idx = json.load(f)
        paths = [e["path"] for e in idx["files"]]
        for p in paths:
            self.assertNotIn("node_modules", p, f"node_modules not excluded: {p}")
            self.assertNotIn(".git/config", p)

    def test_index_includes_agent_files(self):
        make_fixture_repo(self.tmp)
        (self.tmp / "agents").mkdir(exist_ok=True)
        (self.tmp / "agents" / "heidi.md").write_text("# Agent\n")
        out_path = self.tmp / "index.json"
        run("index", "--root", str(self.tmp), "--out", str(out_path))
        with open(out_path) as f:
            idx = json.load(f)
        agent_paths = [e["path"] for e in idx["files"] if "agents" in e["path"]]
        self.assertTrue(len(agent_paths) > 0)

    def test_index_detects_package_scripts(self):
        make_fixture_repo(self.tmp)
        out_path = self.tmp / "index.json"
        run("index", "--root", str(self.tmp), "--out", str(out_path))
        with open(out_path) as f:
            idx = json.load(f)
        scripts = idx["summary"]["package_scripts"]
        self.assertIn("test", scripts, f"got scripts: {scripts}")
        self.assertIn("build", scripts)

    def test_index_is_deterministic(self):
        make_fixture_repo(self.tmp)
        # Output outside the scanned root so the output files don't affect each other
        outdir = Path(tempfile.mkdtemp())
        try:
            out1 = outdir / "idx1.json"
            out2 = outdir / "idx2.json"
            run("index", "--root", str(self.tmp), "--out", str(out1))
            run("index", "--root", str(self.tmp), "--out", str(out2))
            with open(out1) as f:
                h1 = json.dumps(json.load(f), sort_keys=True)
            with open(out2) as f:
                h2 = json.dumps(json.load(f), sort_keys=True)
            self.assertEqual(h1, h2)
        finally:
            shutil.rmtree(outdir, ignore_errors=True)

    def test_search_returns_matches(self):
        make_fixture_repo(self.tmp)
        out_path = self.tmp / "index.json"
        run("index", "--root", str(self.tmp), "--out", str(out_path))
        rc, out, err = run("search", "--index", str(out_path), "--query", "app.py")
        self.assertIn("app.py", out)

    def test_validate_passes_on_good_fixture(self):
        heidi_dir = self.tmp / ".heidi"
        run("init", str(heidi_dir))
        # Generate index with some files
        make_fixture_repo(self.tmp)
        run("index", "--root", str(self.tmp), "--out", str(heidi_dir / "context-index.json"))
        rc, out, err = run("validate", str(heidi_dir))
        # Index has node_modules in tracked paths? No, because make_fixture doesn't index
        # But the validation checks for ignored dirs in indexed paths
        self.assertEqual(rc, 0, f"validate failed: {err}\n{out}")

    def test_validate_fails_on_duplicate_paths(self):
        heidi_dir = self.tmp / ".heidi"
        heidi_dir.mkdir()
        idx = {"schema_version": "2.0.0", "files": [
            {"path": "src/app.py", "size": 10, "sha256": "aa"},
            {"path": "src/app.py", "size": 10, "sha256": "aa"},
        ]}
        with open(heidi_dir / "context-index.json", "w") as f:
            json.dump(idx, f)
        (heidi_dir / "rules.md").write_text("# Rules\n")
        (heidi_dir / "commands.md").write_text("# Verified Repository Commands\n")
        (heidi_dir / "memory.jsonl").write_text("")
        rc, out, err = run("validate", str(heidi_dir))
        self.assertNotEqual(rc, 0)

    def test_validate_fails_on_absolute_path(self):
        heidi_dir = self.tmp / ".heidi"
        heidi_dir.mkdir()
        idx = {"schema_version": "2.0.0", "files": [
            {"path": "/absolute/path.py", "size": 10, "sha256": "bb"},
        ]}
        with open(heidi_dir / "context-index.json", "w") as f:
            json.dump(idx, f)
        (heidi_dir / "rules.md").write_text("# Rules\n")
        (heidi_dir / "commands.md").write_text("# Verified Repository Commands\n")
        (heidi_dir / "memory.jsonl").write_text("")
        rc, out, err = run("validate", str(heidi_dir))
        self.assertNotEqual(rc, 0)

    def test_validate_fails_on_missing_memory(self):
        heidi_dir = self.tmp / ".heidi"
        heidi_dir.mkdir()
        (heidi_dir / "rules.md").write_text("# Rules\n")
        (heidi_dir / "commands.md").write_text("# Verified Repository Commands\n")
        idx = {"schema_version": "2.0.0", "files": []}
        with open(heidi_dir / "context-index.json", "w") as f:
            json.dump(idx, f)
        rc, out, err = run("validate", str(heidi_dir))
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()


# ── Budget enforcement tests ──────────────────────────────────

class TestContextMemoryBudgetEnforcement(unittest.TestCase):

    def test_retrieve_respects_char_budget(self):
        """Test that retrieve enforces max_chars as a hard stop."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            index_path = tmpdir / "context-index.json"
            files = []
            for i in range(20):
                files.append({
                    "path": f"file_{i}.py",
                    "size": 1000,
                    "sha256": "a" * 64,
                    "language": "Python",
                    "is_test": False,
                    "headings": [f"Heading {i} " * 20],
                })
            index_path.write_text(json.dumps({"schema_version": "2.0.0", "files": files}))

            rc, out, _ = run(
                "retrieve", "--index", str(index_path), "--query", "test",
                "--max-results", "50", "--max-chars", "500", "--format", "runtime",
            )
            self.assertEqual(rc, 0)
            result = json.loads(out)
            total_chars = result.get("total_chars", 0)
            self.assertLessEqual(total_chars, 500,
                f"Context retrieval exceeded char budget: {total_chars} > 500")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_retrieve_empty_results(self):
        """Test retrieval with no matching results."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            index_path = tmpdir / "context-index.json"
            index_path.write_text(json.dumps({"schema_version": "2.0.0", "files": []}))

            rc, out, _ = run(
                "retrieve", "--index", str(index_path), "--query", "nonexistent",
                "--format", "runtime",
            )
            self.assertEqual(rc, 0)
            result = json.loads(out)
            self.assertEqual(len(result["results"]), 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_retrieve_oversized_single_result(self):
        """Test that a single result exceeding the budget is not added."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            index_path = tmpdir / "context-index.json"
            files = [{
                "path": "big_file.py",
                "size": 100000,
                "sha256": "b" * 64,
                "language": "Python",
                "is_test": False,
                "headings": ["X" * 1000],
            }]
            index_path.write_text(json.dumps({"schema_version": "2.0.0", "files": files}))

            rc, out, _ = run(
                "retrieve", "--index", str(index_path), "--query", "big",
                "--max-results", "10", "--max-chars", "100", "--format", "runtime",
            )
            self.assertEqual(rc, 0)
            result = json.loads(out)
            # The single result exceeds the 100-char budget, so it should not be added
            self.assertEqual(len(result["results"]), 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
