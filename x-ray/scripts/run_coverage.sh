#!/bin/bash
# Runs bundle-local coverage only when the target root has a local harness.
# Prevents extracted bundles from accidentally inheriting the parent workspace.

set -euo pipefail

ROOT="${1:-.}"

cd "$ROOT"

count_local_tests() {
  python3 - <<'PY'
from pathlib import Path
EXTS = {".sol",".js",".ts",".mjs",".cjs"}
SKIP = {"node_modules","lib","forge-std","out","artifacts","cache","dist","build","coverage"}
count = 0
for f in Path(".").rglob("*"):
    if not f.is_file() or f.suffix not in EXTS:
        continue
    if set(f.parts) & SKIP:
        continue
    path_lower = str(f).lower()
    if "/test/" in path_lower or "/tests/" in path_lower or path_lower.startswith("test/") or path_lower.startswith("tests/"):
        count += 1
print(count)
PY
}

LOCAL_TEST_FILES="$(count_local_tests)"

HAS_LOCAL_FOUNDRY=0
HAS_LOCAL_HARDHAT=0
HAS_LOCAL_PACKAGE=0

[ -f "foundry.toml" ] && HAS_LOCAL_FOUNDRY=1
{ [ -f "hardhat.config.js" ] || [ -f "hardhat.config.ts" ] || [ -f "hardhat.config.cjs" ] || [ -f "hardhat.config.mjs" ]; } && HAS_LOCAL_HARDHAT=1 || true
[ -f "package.json" ] && HAS_LOCAL_PACKAGE=1

if [ "$LOCAL_TEST_FILES" = "0" ]; then
  echo "COVERAGE_UNAVAILABLE: no local test harness under target root"
  exit 0
fi

if [ "$HAS_LOCAL_FOUNDRY" = "1" ]; then
  forge coverage --root . 2>&1 || (echo "RETRYING_WITH_IR_MINIMUM" && forge coverage --root . --ir-minimum 2>&1)
  exit 0
fi

if [ "$HAS_LOCAL_HARDHAT" = "1" ] && [ "$HAS_LOCAL_PACKAGE" = "1" ]; then
  npx hardhat coverage 2>&1
  exit 0
fi

echo "COVERAGE_UNAVAILABLE: local tests exist but no local foundry.toml or hardhat config under target root"

