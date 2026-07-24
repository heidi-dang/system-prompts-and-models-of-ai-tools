#!/usr/bin/env python3
"""Negative test: verify runtime doctor exits non-zero with broken policy."""
import json
import shutil
import subprocess
import sys
import tempfile

# Copy the runtime-policy.json, remove consumption section
src = "opencode-agent-pack/runtime/runtime-policy.json"
tmpdir = tempfile.mkdtemp()
shutil.copy2(src, f"{tmpdir}/runtime-policy.json")

with open(f"{tmpdir}/runtime-policy.json") as f:
    policy = json.load(f)
policy["runtime"].pop("consumption", None)
with open(f"{tmpdir}/runtime-policy.json", "w") as f:
    json.dump(policy, f)

# Replace the original with broken version
shutil.copy2(f"{tmpdir}/runtime-policy.json", src)

# Run doctor
result = subprocess.run(
    [sys.executable, "opencode-agent-pack/scripts/runtime_doctor.py", "validate", "--mode", "isolated"],
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)

# Restore original
subprocess.run(["git", "checkout", src], capture_output=True)
shutil.rmtree(tmpdir)

if result.returncode == 0:
    print("FAIL: runtime doctor should have exited non-zero with broken policy")
    sys.exit(1)
print("PASS: runtime doctor correctly detected broken policy (exit code: %d)" % result.returncode)
sys.exit(0)
