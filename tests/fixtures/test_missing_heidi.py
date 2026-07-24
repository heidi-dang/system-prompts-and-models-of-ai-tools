#!/usr/bin/env python3
"""Negative test: verify runtime doctor exits non-zero without .heidi."""
import subprocess
import sys
import tempfile
import os

tmpdir = tempfile.mkdtemp()
os.chdir(tmpdir)

result = subprocess.run(
    [sys.executable, os.path.join(os.path.dirname(__file__), "..", "..",
     "opencode-agent-pack/scripts/runtime_doctor.py"), "validate", "--mode", "isolated"],
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)

os.chdir(os.path.dirname(__file__))
import shutil
shutil.rmtree(tmpdir)

if result.returncode == 0:
    print("FAIL: runtime doctor should have exited non-zero without .heidi")
    sys.exit(1)
print("PASS: runtime doctor correctly detected missing .heidi (exit code: %d)" % result.returncode)
sys.exit(0)
