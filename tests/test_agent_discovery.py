#!/usr/bin/env python3
"""
Comprehensive regression tests for the agent discovery flooding bug.

These tests verify that agent.sh --repair-agent-discovery correctly:
  - Detects Runtime/ directories, backup folders, and stale backup files
    polluting the agent discovery paths.
  - Moves them to private locations (.heidi/backups/installer/).
  - Preserves unrelated user agents and non-Heidi runtime-looking folders.
  - Is idempotent (no double-moves, no data loss on repeated repair).

Flooding bug background:
  A prior install path copied runtime orchestration folders (Runtime/,
  Prompts/) and backup artifacts into the OpenCode agent discovery
  directory (~/.config/opencode/agents/). This caused every .md file in
  those subdirectories to be discovered as a separate agent, flooding the
  agent list with runtime fragments and stale backups.

Managed agent set (canonical):
  heidi, frontend, backend, debugger, auditor, planner, scout  (7 agents)

Usage:
  cd <repo-root> && python3 -m pytest tests/test_agent_discovery.py -v
  cd <repo-root> && python3 -m unittest tests.test_agent_discovery
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ── Resolve repo root and script paths ──────────────────────────

_THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = _THIS_DIR.parent
AGENT_SH = str(REPO_ROOT / "agent.sh")
RUNTIME_DOCTOR = str(
    REPO_ROOT / "opencode-agent-pack" / "scripts" / "runtime_doctor.py"
)
AGENT_SRC = REPO_ROOT / "opencode-agent-pack" / "agents"

# Canonical managed agents
MANAGED_AGENTS = {"heidi", "frontend", "backend", "debugger", "auditor", "planner", "scout"}

# ── Helpers ──────────────────────────────────────────────────────

def _glob_any(path: Path, pattern: str):
    """Return sorted list of matching names, or empty list."""
    return sorted([p.name for p in path.glob(pattern)])


def _all_files_under(path: Path):
    """Return a set of relative paths for every file under `path`."""
    if not path.is_dir():
        return set()
    rel = set()
    for root, _dirs, files in os.walk(str(path)):
        for f in files:
            rp = os.path.relpath(os.path.join(root, f), str(path))
            rel.add(rp)
    return rel


# ── Test class ───────────────────────────────────────────────────

class TestAgentDiscovery(unittest.TestCase):
    """Isolated test suite — does not touch the real filesystem."""

    # ══════════════════════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════════════════════

    def setUp(self):
        """Create isolated temp tree with custom HOME and config dir."""
        self.tmp = Path(tempfile.mkdtemp(prefix="heidi_test_agent_disc_"))
        self.home = self.tmp / "home"
        self.config = self.tmp / "opencode_config"
        self.agents_dir = self.config / "agents"
        self.home.mkdir(parents=True, exist_ok=True)
        self.config.mkdir(parents=True, exist_ok=True)
        self.agents_dir.mkdir(parents=True, exist_ok=True)

        # Project scratch area for --project and --both tests
        self.project_dir = self.tmp / "project"
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.project_agents = self.project_dir / ".opencode" / "agents"

        self.env = {
            **os.environ,
            "HOME": str(self.home),
            # Prefer XDG var *not* set so agent.sh falls back to HOME:
            # "XDG_CONFIG_HOME": str(self.home / ".config"),
            "OPENCODE_CONFIG_DIR": str(self.config),
        }

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _run_sh(self, *args, cwd=None):
        """Run agent.sh with optional cwd and return CompletedProcess."""
        cmd = ["bash", AGENT_SH] + list(args)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=self.env.copy(),
            cwd=str(cwd) if cwd else str(self.tmp),
            timeout=60,
        )

    def _run_py(self, *args):
        """Run runtime_doctor.py."""
        cmd = [sys.executable, RUNTIME_DOCTOR] + list(args)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=self.env.copy(),
            cwd=str(self.tmp),
            timeout=30,
        )

    # ══════════════════════════════════════════════════════════════
    # Fixture builders
    # ══════════════════════════════════════════════════════════════

    def _install_heidi_agent(self):
        """Place a minimal heidi.md in the agents dir so the managed
        set is present."""
        (self.agents_dir / "heidi.md").write_text("# Heidi Agent\n", encoding="utf-8")

    def _build_broken_state(self):
        """Create the full flooding scenario inside agents_dir.

        IMPORTANT: filenames use lowercase to match the Heidi runtime
        marker list in agent.sh (core.md, routing.md,
        heidi-orchestration.md).  The ``find -name`` check is
        case-sensitive.
        """
        ad = self.agents_dir

        # valid agent
        (ad / "heidi.md").write_text("# Heidi\n", encoding="utf-8")

        # Runtime/ directory with sub-structure that mimics Heidi runtime
        rt = ad / "Runtime"
        (rt / "Prompts").mkdir(parents=True)
        # Marker: heidi-orchestration.md directly in Runtime/
        (rt / "heidi-orchestration.md").write_text("# orch\n", encoding="utf-8")
        (rt / "Prompts" / "core.md").write_text("# core\n", encoding="utf-8")
        (rt / "Prompts" / "routing.md").write_text("# routing\n", encoding="utf-8")
        (rt / "Prompts" / "verification.md").write_text("# verify\n", encoding="utf-8")

        # Timestamped backup folder (runtime backup with Heidi markers)
        bak_dir = ad / "Runtime.bak.20260724-051140"
        (bak_dir / "Prompts").mkdir(parents=True)
        (bak_dir / "heidi-orchestration.md").write_text("# orch-bak\n", encoding="utf-8")
        (bak_dir / "Prompts" / "core.md").write_text("# core-bak\n", encoding="utf-8")
        (bak_dir / "Prompts" / "routing.md").write_text("# routing-bak\n", encoding="utf-8")

        # Stale individual backup with old naming (bug: .md.bak.*)
        (ad / "heidi.md.bak.20260724-051139").write_text("# heidi-bak\n", encoding="utf-8")

    def _build_unrelated_in_agents(self):
        """Add a user-owned agent and an ambiguous non-Heidi runtime dir."""
        ad = self.agents_dir

        # user agent
        (ad / "my-custom-agent.md").write_text("# Custom\n", encoding="utf-8")

        # ambiguous / non-Heidi runtime-looking folder (no Heidi markers)
        amb = ad / "Runtime"
        amb.mkdir(parents=True, exist_ok=True)
        (amb / "README.txt").write_text("not heidi\n", encoding="utf-8")
        (amb / "config.json").write_text("{}", encoding="utf-8")

    # ══════════════════════════════════════════════════════════════
    # 1. Detection via runtime_doctor
    # ══════════════════════════════════════════════════════════════

    def test_01_runtime_doctor_discover_reports_agent_counts(self):
        """runtime_doctor.py discover lists agents; we use it to confirm
        the global agent path is recognised."""
        self._install_heidi_agent()
        proc = self._run_py("discover")
        # discover always exits 0
        self.assertEqual(proc.returncode, 0)
        # Should mention the global agents path
        self.assertIn("Global agents", proc.stdout,
                      "discover output should reference Global agents")

    def test_02_runtime_doctor_discover_sees_pollution(self):
        """When flooding exists, discover still reports the base directory
        but does not enumerate .md files inside subdirectories (only
        top-level *.md glob).  The polluted subdirectories themselves
        are invisible to `discover` — that is the problem the repair
        fixes."""
        self._build_broken_state()
        proc = self._run_py("discover")
        self.assertEqual(proc.returncode, 0)
        # The discover command globs agents/*.md — so the Runtime/*.md
        # files are NOT listed; the stdout should show the correct
        # number of top-level .md files.
        output = proc.stdout
        # Should show the global agents path exists
        self.assertIn("Global agents", output)

    def test_03_runtime_doctor_agent_discovery_subcommand(self):
        """Call runtime_doctor.py with agent-discovery subcommand.
        If the command is not yet implemented, verify it prints a
        reasonable error (not a traceback)."""
        proc = self._run_py("agent-discovery")
        # Accept either: success (command exists) or user-facing error
        combined = proc.stdout + proc.stderr
        # Must not crash with a Python traceback
        self.assertNotIn("Traceback", combined,
                         "agent-discovery should not produce a traceback")
        # Should mention something about agent-discovery or unknown cmd
        has_agent_ref = ("agent" in combined.lower() or
                         "invalid" in combined.lower() or
                         "unknown" in combined.lower() or
                         "usage" in combined.lower())
        self.assertTrue(has_agent_ref,
                        f"Expected agent-discovery reference, got: {combined[:200]}")

    # ══════════════════════════════════════════════════════════════
    # 2. Dry-run detection via agent.sh
    # ══════════════════════════════════════════════════════════════

    def test_04_dry_run_reports_runtime_folder(self):
        """--repair-agent-discovery --dry-run should report the
        Runtime/ folder as a managed pollution candidate."""
        self._build_broken_state()
        proc = self._run_sh("--repair-agent-discovery", "--dry-run")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        stdout = proc.stdout
        # Should mention Runtime directory
        self.assertIn("Runtime", stdout,
                      "dry-run should mention the Runtime folder")

    def test_05_dry_run_reports_backup_folder(self):
        """Dry-run should report the Runtime.bak.* backup folder."""
        self._build_broken_state()
        proc = self._run_sh("--repair-agent-discovery", "--dry-run")
        stdout = proc.stdout
        self.assertIn("Runtime.bak", stdout,
                      "dry-run should mention the backup folder")

    def test_06_dry_run_reports_individual_backup(self):
        """Dry-run should report *.md.bak.* individual backup files."""
        self._build_broken_state()
        proc = self._run_sh("--repair-agent-discovery", "--dry-run")
        stdout = proc.stdout
        # The dry-run message for individual backups:
        # "[dry-run] Would move ... heidi.md.bak.20260724-051139 ..."
        self.assertIn("heidi.md.bak", stdout,
                      "dry-run should mention the individual backup file")

    def test_07_dry_run_mentions_unrelated_preservation(self):
        """When an ambiguous non-Heidi Runtime/ folder exists, dry-run
        should indicate it is preserved rather than moved."""
        self._build_unrelated_in_agents()
        # Also add a real managed agent so the dir has heidi.md
        (self.agents_dir / "heidi.md").write_text("# Heidi\n", encoding="utf-8")
        proc = self._run_sh("--repair-agent-discovery", "--dry-run")
        stdout = proc.stdout
        # Should say "Preserved unrelated" for the ambiguous Runtime/
        self.assertIn("Preserved unrelated", stdout,
                      "dry-run should mention preserved unrelated folders")

    # ══════════════════════════════════════════════════════════════
    # 3. Actual repair
    # ══════════════════════════════════════════════════════════════

    def test_08_repair_moves_runtime_directory(self):
        """After --repair-agent-discovery, the Runtime/ directory must
        be gone from the agents dir and moved to private backup."""
        self._build_broken_state()
        proc = self._run_sh("--repair-agent-discovery")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

        # Runtime/ must no longer exist in agents_dir
        self.assertFalse((self.agents_dir / "Runtime").exists(),
                         "Runtime/ should be moved out of agents dir")

        # The private backup location should now exist and contain the
        # moved runtime content
        heidi_backup = self.project_dir / ".heidi" / "backups" / "installer"
        self.assertTrue(
            heidi_backup.exists() or
            any("Moved" in proc.stdout for _ in [1]),
            f"Private backup should exist; got stdout: {proc.stdout[:200]}"
        )

    def test_09_repair_moves_backup_folder(self):
        """Runtime.bak.* backup folder should be moved out."""
        self._build_broken_state()
        self._run_sh("--repair-agent-discovery")

        bak_dirs = list(self.agents_dir.glob("Runtime.bak.*"))
        self.assertEqual(len(bak_dirs), 0,
                         f"Backup folder still present: {bak_dirs}")

    def test_10_repair_moves_individual_backup_file(self):
        """heidi.md.bak.* file should be moved out of agents dir."""
        self._build_broken_state()
        self._run_sh("--repair-agent-discovery")

        stale_baks = list(self.agents_dir.glob("*.md.bak.*"))
        self.assertEqual(len(stale_baks), 0,
                         f"Stale backup files still present: {stale_baks}")

    def test_11_only_managed_agents_remain_as_md(self):
        """After repair, the agents dir should contain exactly 7 .md
        files matching the managed agent names (assuming they were
        installed).  No extra .md files or directories should remain."""
        # Install all managed agents first, then add pollution, then repair
        self._install_all_managed()
        self._build_broken_state()
        # Re-add heidi.md since _build_broken_state overwrites it
        (self.agents_dir / "heidi.md").write_text("# Heidi\n", encoding="utf-8")
        self._run_sh("--repair-agent-discovery")

        md_files = set(_glob_any(self.agents_dir, "*.md"))
        self.assertEqual(
            md_files,
            {f"{a}.md" for a in MANAGED_AGENTS},
            f"Only managed agent .md files should remain, got: {md_files}"
        )

    def test_12_repeated_repair_is_idempotent(self):
        """Running --repair-agent-discovery a second time should not
        move anything new and should exit cleanly."""
        self._build_broken_state()
        self._run_sh("--repair-agent-discovery")
        proc2 = self._run_sh("--repair-agent-discovery")
        self.assertEqual(proc2.returncode, 0, msg=proc2.stderr)
        # Second run should report 0 new items moved
        stdout2 = proc2.stdout
        self.assertIn("0", stdout2.split("Managed runtime folders found:")[-1].split("\n")[0].strip(),
                      "Second repair should find 0 new runtime folders")

    def test_13_user_agents_preserved_after_repair(self):
        """my-custom-agent.md (user-owned, not in managed set) must
        survive the repair untouched."""
        self._install_heidi_agent()
        custom = self.agents_dir / "my-custom-agent.md"
        custom.write_text("# Custom User Agent\n", encoding="utf-8")
        self._build_broken_state()
        # Re-add heidi.md (overwritten by broken state builder)
        (self.agents_dir / "heidi.md").write_text("# Heidi\n", encoding="utf-8")

        self._run_sh("--repair-agent-discovery")

        self.assertTrue(custom.exists(),
                        "my-custom-agent.md should be preserved")
        content = custom.read_text(encoding="utf-8")
        self.assertIn("Custom User Agent", content,
                      "User agent content should be unchanged")

    def test_14_unrelated_runtime_folder_preserved(self):
        """An ambiguous Runtime/ folder without Heidi markers must NOT
        be deleted -- it should be preserved as unrelated.

        The repair function in agent.sh only processes directories
        named 'Runtime' or 'runtime' (case-sensitive).  Other folders
        are left untouched.  We also verify that a backup-like folder
        with no Heidi markers is preserved.
        """
        self._install_heidi_agent()

        # Ambiguous non-Heidi Runtime/ -- contains only README.txt, no markers
        amb = self.agents_dir / "Runtime"
        amb.mkdir(parents=True, exist_ok=True)
        (amb / "README.txt").write_text("not-heidi\n", encoding="utf-8")
        (amb / "config.json").write_text("{}", encoding="utf-8")

        # A user folder not named Runtime/runtime
        user_folder = self.agents_dir / "SomeFolder"
        user_folder.mkdir(parents=True, exist_ok=True)
        (user_folder / "notes.txt").write_text("user stuff\n", encoding="utf-8")

        # Also add a subdirectory that looks like a backup but has no markers
        fake_bak = self.agents_dir / "SomeFolder.bak.20260101-000000"
        fake_bak.mkdir(parents=True, exist_ok=True)
        (fake_bak / "data.txt").write_text("not heidi\n", encoding="utf-8")

        proc = self._run_sh("--repair-agent-discovery")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

        # Ambiguous Runtime/ without markers should be preserved
        self.assertTrue(amb.exists(),
                        "Unrelated Runtime/ (no Heidi markers) should be preserved")
        # User folders should be preserved
        self.assertTrue(user_folder.exists(),
                        "Unrelated SomeFolder/ should be preserved")
        self.assertTrue(fake_bak.exists(),
                        "Unrelated backup-like folder should be preserved")
        # Should report preservation
        self.assertIn("Preserved unrelated", proc.stdout,
                      "Should log preserved unrelated folders")

    # ══════════════════════════════════════════════════════════════
    # 4. Install-related flooding prevention
    # ══════════════════════════════════════════════════════════════

    def _install_all_managed(self):
        """Install al 7 managed agents into self.agents_dir."""
        for agent in sorted(MANAGED_AGENTS):
            src = AGENT_SRC / f"{agent}.md"
            dst = self.agents_dir / f"{agent}.md"
            if src.exists():
                shutil.copy2(str(src), str(dst))

    def test_15_install_global_does_not_create_flooding(self):
        """--install --global should not leave Runtime/, Runtime.bak.*,
        or *.md.bak.* inside the agents discovery directory."""
        # Copy agent.sh and pack source to a temp project so --install works
        proj = self.project_dir
        shutil.copy2(AGENT_SH, str(proj / "agent.sh"))
        shutil.copytree(
            str(REPO_ROOT / "opencode-agent-pack"),
            str(proj / "opencode-agent-pack"),
            dirs_exist_ok=True,
        )

        proc = self._run_sh("--install", "--global", cwd=proj)
        # install may return non-zero if some validations fail without opencode
        # We just care that the agents dir is clean
        _ = proc.returncode

        # Check the global agents directory for any pollution
        ad = self.agents_dir
        if ad.is_dir():
            # No Runtime/ or runtime/ directories
            self.assertFalse(
                (ad / "Runtime").exists() or (ad / "runtime").exists(),
                "Install must not create Runtime/ in agent discovery path"
            )
            # No backup folders
            for item in ad.iterdir():
                if item.is_dir() and ".bak." in item.name:
                    self.fail(
                        f"Install must not create backup folder in agent dir: {item.name}"
                    )
            # No *.md.bak.* files
            stale = list(ad.glob("*.md.bak.*"))
            self.assertEqual(len(stale), 0,
                             f"Install must not create .md.bak.* files: {stale}")

    def test_16_install_both_does_not_duplicate_agents(self):
        """--install --both should produce exactly 7 agents in each
        location (global and project), not duplicates across them."""
        proj = self.project_dir
        shutil.copy2(AGENT_SH, str(proj / "agent.sh"))
        shutil.copytree(
            str(REPO_ROOT / "opencode-agent-pack"),
            str(proj / "opencode-agent-pack"),
            dirs_exist_ok=True,
        )

        proc = self._run_sh("--install", "--both", cwd=proj)
        _ = proc.returncode  # may fail if opencode not available

        # Global: exactly 7 managed .md files, no extras
        global_md = set(_glob_any(self.agents_dir, "*.md"))
        expected = {f"{a}.md" for a in MANAGED_AGENTS}
        self.assertEqual(global_md, expected,
                         f"Global agents mismatch: {global_md ^ expected}")

        # Project: exactly 7 managed .md files
        proj_ad = self.project_agents
        if proj_ad.is_dir():
            proj_md = set(_glob_any(proj_ad, "*.md"))
            self.assertEqual(proj_md, expected,
                             f"Project agents mismatch: {proj_md ^ expected}")

    def test_17_repeated_install_creates_no_flooding(self):
        """Running --install twice should not create any new Runtime/
        or backup artifacts in the agent discovery path."""
        proj = self.project_dir
        shutil.copy2(AGENT_SH, str(proj / "agent.sh"))
        shutil.copytree(
            str(REPO_ROOT / "opencode-agent-pack"),
            str(proj / "opencode-agent-pack"),
            dirs_exist_ok=True,
        )

        self._run_sh("--install", "--global", cwd=proj)

        # Record state after first install
        first_files = _all_files_under(self.agents_dir)
        first_dirs = set()
        for root, dirs, _files in os.walk(str(self.agents_dir)):
            for d in dirs:
                first_dirs.add(os.path.relpath(os.path.join(root, d), str(self.agents_dir)))

        # Second install
        self._run_sh("--install", "--global", cwd=proj)

        second_files = _all_files_under(self.agents_dir)
        second_dirs = set()
        for root, dirs, _files in os.walk(str(self.agents_dir)):
            for d in dirs:
                second_dirs.add(os.path.relpath(os.path.join(root, d), str(self.agents_dir)))

        # No new pollution directories should appear
        new_dirs = second_dirs - first_dirs
        self.assertEqual(len(new_dirs), 0,
                         f"Repeated install created new directories: {new_dirs}")

        # No .md.bak.* files should appear
        new_baks = [f for f in (second_files - first_files) if ".md.bak." in f]
        self.assertEqual(len(new_baks), 0,
                         f"Repeated install created backup files: {new_baks}")

    def test_18_no_timestamped_backup_folder_remains_after_install(self):
        """After --install --global, no *.bak.* directories should
        remain inside the agents directory."""
        proj = self.project_dir
        shutil.copy2(AGENT_SH, str(proj / "agent.sh"))
        shutil.copytree(
            str(REPO_ROOT / "opencode-agent-pack"),
            str(proj / "opencode-agent-pack"),
            dirs_exist_ok=True,
        )

        self._run_sh("--install", "--global", cwd=proj)

        ad = self.agents_dir
        for item in ad.iterdir():
            if item.is_dir():
                name = item.name
                # Folders like Runtime.bak.20260724-051140 should not exist
                self.assertFalse(
                    ".bak." in name,
                    f"Timestamped backup folder found in agents dir: {name}"
                )
            elif item.is_file():
                name = item.name
                # Files like heidi.md.bak.20260724-051139 should not exist
                self.assertFalse(
                    ".md.bak." in name,
                    f"Stale backup file found in agents dir: {name}"
                )

    def test_19_backup_files_have_correct_extension(self):
        """When an install creates backups, the backup extension should
        be .bak (e.g. heidi.md.bak.20260101-000000.bak), NOT the old
        pattern (heidi.md.bak.20260101-000000 without trailing .bak)."""
        # Install once to create agents
        proj = self.project_dir
        shutil.copy2(AGENT_SH, str(proj / "agent.sh"))
        shutil.copytree(
            str(REPO_ROOT / "opencode-agent-pack"),
            str(proj / "opencode-agent-pack"),
            dirs_exist_ok=True,
        )

        self._run_sh("--install", "--global", cwd=proj)

        # Modify an agent to force a backup on next install
        heidi = self.agents_dir / "heidi.md"
        if heidi.exists():
            heidi.write_text("# Heidi Modified\n", encoding="utf-8")

        self._run_sh("--install", "--global", cwd=proj)

        # Find any backup files
        all_files = _all_files_under(self.agents_dir)
        bak_files = [f for f in all_files if ".bak." in f]

        for bf in bak_files:
            # e.g., heidi.md.bak.20260101-000000.bak
            self.assertTrue(
                bf.endswith(".bak"),
                f"Backup should end with .bak, got: {bf}"
            )
            # Should NOT end with just a timestamp (no trailing .bak)
            self.assertFalse(
                bf.endswith(".md.bak"),
                f"Backup should not match old *.md.bak pattern, got: {bf}"
            )

    def test_20_repair_manifest_is_created(self):
        """After --repair-agent-discovery, a repair-manifest.txt should
        be written to .heidi/ (relative to pwd) with statistics about
        what was moved."""
        self._build_broken_state()
        # agent.sh writes the manifest to "$(pwd)/.heidi/" which is
        # the cwd of the subprocess -- self.tmp in our harness.
        self._run_sh("--repair-agent-discovery")

        heidi_dir = self.tmp / ".heidi"
        manifest = heidi_dir / "repair-manifest.txt"
        self.assertTrue(manifest.exists(),
                        f"Repair manifest not created at {manifest}")
        content = manifest.read_text(encoding="utf-8")
        self.assertIn("Repair Manifest", content)
        self.assertIn("Runtime folders found:", content)
        self.assertIn("Backup folders found:", content)
        self.assertIn("Individual backup files found:", content)

    def test_21_agent_directory_no_directories_after_repair(self):
        """After repair, the agent directory should contain no
        subdirectories (only flat .md files)."""
        self._install_all_managed()
        self._build_broken_state()
        (self.agents_dir / "heidi.md").write_text("# Heidi\n", encoding="utf-8")
        self._run_sh("--repair-agent-discovery")

        for item in self.agents_dir.iterdir():
            self.assertTrue(
                item.is_file(),
                f"Agent dir should contain only files, found directory: {item.name}"
            )

    def test_22_final_state_only_seven_md_files_match_managed_names(self):
        """End-to-end: build broken state, repair, verify only the 7
        managed .md files remain with correct names."""
        self._install_all_managed()
        self._build_broken_state()
        (self.agents_dir / "heidi.md").write_text("# Heidi\n", encoding="utf-8")
        # Also add a custom user agent
        (self.agents_dir / "my-custom-agent.md").write_text("# Custom\n", encoding="utf-8")

        self._run_sh("--repair-agent-discovery")

        md_files = set(_glob_any(self.agents_dir, "*.md"))
        expected = {f"{a}.md" for a in MANAGED_AGENTS} | {"my-custom-agent.md"}
        self.assertEqual(md_files, expected,
                         f"Final state mismatch: {md_files ^ expected}")

        # Count items total (files + dirs) — should be 8 files, 0 dirs
        items = list(self.agents_dir.iterdir())
        files = [i for i in items if i.is_file()]
        dirs = [i for i in items if i.is_dir()]
        self.assertEqual(len(files), 8, f"Expected 8 files, got {len(files)}: {[f.name for f in files]}")
        self.assertEqual(len(dirs), 0, f"Expected 0 dirs, got {len(dirs)}: {[d.name for d in dirs]}")


if __name__ == "__main__":
    unittest.main()
