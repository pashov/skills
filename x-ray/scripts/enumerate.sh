#!/bin/bash
# Step 1: Enumerate source files, line counts, nSLOC, test stats, docs, commit, and git history stats
# Usage: enumerate.sh <project-root> <src-dir>
# Output: labeled sections consumed by the x-ray skill

set -e
ROOT="${1:-.}"
SRC="${2:-}"

cd "$ROOT"

detect_source_dirs() {
  if [ -n "$SRC" ]; then
    if [ -d "$SRC" ]; then
      printf '%s\n' "$SRC"
      return 0
    fi
    return 0
  fi

  for candidate in src contracts source main-project/source; do
    if [ -d "$candidate" ]; then
      printf '%s\n' "$candidate"
    fi
  done | awk '!seen[$0]++'
}

SRC_DIRS=()
while IFS= read -r src_dir; do
  [ -n "$src_dir" ] && SRC_DIRS+=("$src_dir")
done < <(detect_source_dirs)

emit_sol_files() {
  if [ "${#SRC_DIRS[@]}" -eq 0 ]; then
    return 0
  fi
  find "${SRC_DIRS[@]}" -name '*.sol' \
    -not -path '*/test/*' -not -path '*/tests/*' -not -path '*/script/*' \
    -not -path '*/lib/*' -not -path '*/node_modules/*' -not -path '*/forge-std/*' \
    -not -path '*/out/*' -not -path '*/broadcast/*' -not -path '*/artifacts/*' \
    -not -path '*/cache/*' 2>/dev/null | sort
}

# ─── Whole-scope folder inventory ────────────────────────────────────────────

echo "=== scope_root ==="
pwd

echo "=== top_level_dirs ==="
find . -mindepth 1 -maxdepth 1 -type d | sort

echo "=== artifact_family_inventory ==="
find . \
  -not -path '*/node_modules/*' \
  -not -path '*/lib/*' \
  -not -path '*/forge-std/*' \
  -not -path '*/out/*' \
  -not -path '*/broadcast/*' \
  -not -path '*/artifacts/*' \
  -not -path '*/cache/*' \
  -not -path '*/dist/*' \
  -not -path '*/build/*' \
  -not -path '*/coverage/*' \
  -type f 2>/dev/null | \
awk '
function family(path) {
  if (path ~ /(^|\/)main-project(\/|$)/) return "main-project";
  if (path ~ /(^|\/)related-contracts(\/|$)/) return "related-contracts";
  if (path ~ /(^|\/)bytecode(\/|$)/) return "bytecode";
  if (path ~ /(^|\/)abi(\/|$)/) return "abi";
  if (path ~ /(^|\/)decompiled(\/|$)/) return "decompiled";
  if (path ~ /(^|\/)live-source(\/|$)/) return "live-source";
  if (path ~ /(^|\/)x-ray(\/|$)/) return "x-ray";
  if (path ~ /(^|\/)test(s)?(\/|$)/) return "tests";
  if (path ~ /(^|\/)docs?(\/|$)/) return "docs";
  if (path ~ /(^|\/)contracts(\/|$)/ || path ~ /(^|\/)src(\/|$)/) return "source-tree";
  return "other";
}
function kind(path) {
  if (path ~ /\.sol$/) return "sol";
  if (path ~ /\.json$/) return "json";
  if (path ~ /\.md$/) return "md";
  if (path ~ /\.abi$/) return "abi";
  if (path ~ /\.txt$/) return "txt";
  return "other";
}
{
  key = family($0) "|" kind($0);
  c[key]++
}
END {
  for (k in c) print k ": " c[k]
}' | sort

echo "=== runtime_metadata_files ==="
find . \
  -not -path '*/node_modules/*' \
  -not -path '*/lib/*' \
  -not -path '*/forge-std/*' \
  \( -name 'project.json' -o -name 'contract-list.json' -o -name 'contract-variables.json' -o -name 'index.json' \) \
  -type f 2>/dev/null | sort

echo "=== runtime_artifact_dirs ==="
find . \
  -not -path '*/node_modules/*' \
  -not -path '*/lib/*' \
  -not -path '*/forge-std/*' \
  \( -type d \( -name 'main-project' -o -name 'related-contracts' -o -name 'abi' -o -name 'bytecode' -o -name 'decompiled' -o -name 'live-source' \) \) \
  2>/dev/null | sort

# ─── Toolchain ────────────────────────────────────────────────────────────────

echo "=== Toolchain ==="
if [ -f foundry.toml ]; then echo "foundry"
elif [ -f hardhat.config.js ] || [ -f hardhat.config.ts ]; then echo "hardhat"
else echo "unknown"; fi

# ─── Source files with line counts ────────────────────────────────────────────

echo "=== Source (with line counts) ==="
emit_sol_files | xargs wc -l 2>/dev/null

# ─── nSLOC (non-blank, non-comment lines) per file ───────────────────────────

echo "=== nSLOC ==="
sum=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  t=$(awk 'NF{c++} END{print c+0}' "$f")
  c=$(awk '/^[[:space:]]*(\/\/|\/\*|\*|\*\/)/{c++} END{print c+0}' "$f")
  n=$((t - c))
  printf "%s: %d\n" "$f" "$n"
  sum=$((sum + n))
done < <(emit_sol_files)
echo "TOTAL: $sum"

# ─── NatSpec ──────────────────────────────────────────────────────────────────

echo "=== NatSpec ==="
SRC_PATHS="$(printf '%s\n' "${SRC_DIRS[@]}")" python3 - <<'PY'
from pathlib import Path
import os
import re
pat = re.compile(r'@notice|@dev|@param|@return')
count = 0
for raw in os.environ.get("SRC_PATHS", "").splitlines():
    if not raw:
        continue
    src = Path(raw)
    if not src.exists():
        continue
    for f in src.rglob("*.sol"):
        try:
            if pat.search(f.read_text(errors="ignore")):
                count += 1
        except Exception:
            pass
print(count)
PY

# ─── Tests ────────────────────────────────────────────────────────────────────

echo "=== test_files ==="
python3 - <<'PY'
from pathlib import Path
SKIP = {"node_modules","lib","forge-std","out","artifacts","cache","dist","build","coverage"}
EXTS = {".sol",".js",".ts",".mjs",".cjs"}
count = 0
for f in Path(".").rglob("*"):
    if not f.is_file() or f.suffix not in EXTS:
        continue
    parts = set(f.parts)
    if parts & SKIP:
        continue
    if any(p.startswith("typechain") for p in f.parts):
        continue
    if any("test" in p.lower() for p in f.parts):
        count += 1
print(count)
PY

echo "=== test_functions ==="
python3 - <<'PY'
from pathlib import Path
import re
SKIP = {"node_modules","lib","forge-std","out","artifacts","cache","dist","build","coverage"}
sol_pat = re.compile(r'\bfunction\s+test')
js_pat = re.compile(r'^\s*it(\.(only|skip))?\s*\(', re.M)
total = 0
for f in Path(".").rglob("*"):
    if not f.is_file():
        continue
    parts = set(f.parts)
    if parts & SKIP:
        continue
    if any(p.startswith("typechain") for p in f.parts):
        continue
    text = ""
    try:
        text = f.read_text(errors="ignore")
    except Exception:
        continue
    path_lower = str(f).lower()
    if f.suffix == ".sol" and any(tag in path_lower for tag in ("/test","/tests","/invariant","/echidna","/medusa","/halmos","/fuzz")):
        total += len(sol_pat.findall(text))
    elif f.suffix in {".js",".ts",".mjs",".cjs"} and any(tag in path_lower for tag in ("/test","/tests","/spec","/specs")):
        total += len(js_pat.findall(text))
print(total)
PY

# ── Stateless Fuzz (Foundry) ──
echo "=== stateless_fuzz ==="
python3 - <<'PY'
from pathlib import Path
import re
pat = re.compile(r'\bfunction\s+testFuzz')
count = 0
for f in Path(".").rglob("*.sol"):
    if any(p in {"node_modules","lib","forge-std","out","artifacts","cache"} for p in f.parts):
        continue
    try:
        count += len(pat.findall(f.read_text(errors="ignore")))
    except Exception:
        pass
print(count)
PY

# ── Stateful Fuzz: Foundry invariant tests ──
echo "=== foundry_invariant ==="
python3 - <<'PY'
from pathlib import Path
import re
pat = re.compile(r'\bfunction\s+invariant_')
count = 0
for f in Path(".").rglob("*.sol"):
    if any(p in {"node_modules","lib","forge-std","out","artifacts","cache"} for p in f.parts):
        continue
    try:
        count += len(pat.findall(f.read_text(errors="ignore")))
    except Exception:
        pass
print(count)
PY

# ── Stateful Fuzz: Echidna ──
echo "=== echidna ==="
ECHIDNA_FUNCS=$(python3 - <<'PY'
from pathlib import Path
import re
pat = re.compile(r'\bfunction\s+echidna_')
count = 0
for f in Path(".").rglob("*.sol"):
    if any(p in {"node_modules","lib","forge-std","out","artifacts","cache"} for p in f.parts):
        continue
    try:
        count += len(pat.findall(f.read_text(errors="ignore")))
    except Exception:
        pass
print(count)
PY
)
ECHIDNA_CONFIGS=$(find . -maxdepth 3 \( -name 'echidna.yaml' -o -name 'echidna_config.yaml' -o -name 'echidna.config.yaml' \) 2>/dev/null | wc -l)
echo "${ECHIDNA_FUNCS}:${ECHIDNA_CONFIGS}"

# ── Stateful Fuzz: Medusa ──
echo "=== medusa ==="
MEDUSA_FUNCS=$(python3 - <<'PY'
from pathlib import Path
import re
pat = re.compile(r'\bfunction\s+(property_|fuzz_)')
count = 0
for f in Path(".").rglob("*.sol"):
    if any(p in {"node_modules","lib","forge-std","out","artifacts","cache"} for p in f.parts):
        continue
    try:
        count += len(pat.findall(f.read_text(errors="ignore")))
    except Exception:
        pass
print(count)
PY
)
MEDUSA_CONFIGS=$(find . -maxdepth 3 \( -name 'medusa.json' \) 2>/dev/null | wc -l)
echo "${MEDUSA_FUNCS}:${MEDUSA_CONFIGS}"

# ── Hardhat Fuzz ──
echo "=== hardhat_fuzz ==="
if [ -f package.json ]; then
  python3 - <<'PY'
from pathlib import Path
import re
text = Path("package.json").read_text(errors="ignore")
print(1 if re.search(r'"@chainlink/hardhat-fuzz"|"hardhat-fuzz"|"@openzeppelin/hardhat-fuzz"', text) else 0)
PY
else
  echo "0"
fi

# ── Fork Tests ──
echo "=== fork ==="
python3 - <<'PY'
from pathlib import Path
import re
pat = re.compile(r'vm\.createFork|createSelectFork|hardhat_reset|FORKING_URL|forking.*url')
count = 0
for f in Path(".").rglob("*"):
    if not f.is_file() or f.suffix not in {".sol",".ts",".js",".mjs",".cjs"}:
        continue
    if any(p in {"node_modules","lib","forge-std","out","artifacts","cache"} for p in f.parts):
        continue
    try:
        count += len(pat.findall(f.read_text(errors="ignore")))
    except Exception:
        pass
print(count)
PY

# ── Formal Verification: Certora ──
echo "=== certora ==="
CERTORA_SPECS=$(find . \( -name '*.spec' -o -name '*.cvl' \) 2>/dev/null | \
  grep -v node_modules | grep -v '/lib/' | wc -l)
CERTORA_CONF=$(find . -maxdepth 3 \( -name '*.conf' -path '*/certora/*' -o -name 'certora.conf' \) 2>/dev/null | wc -l)
echo "${CERTORA_SPECS}:${CERTORA_CONF}"

# ── Formal Verification: Halmos ──
echo "=== halmos ==="
HALMOS_FUNCS=$(python3 - <<'PY'
from pathlib import Path
import re
pat = re.compile(r'\bfunction\s+check_')
count = 0
for f in Path(".").rglob("*.sol"):
    if any(p in {"node_modules","lib","forge-std","out","artifacts","cache"} for p in f.parts):
        continue
    try:
        count += len(pat.findall(f.read_text(errors="ignore")))
    except Exception:
        pass
print(count)
PY
)
HALMOS_CONF=$(find . -maxdepth 3 -name 'halmos.toml' 2>/dev/null | wc -l)
echo "${HALMOS_FUNCS}:${HALMOS_CONF}"

# ── Formal Verification: HEVM ──
echo "=== hevm ==="
python3 - <<'PY'
from pathlib import Path
import re
pat = re.compile(r'\bfunction\s+prove_')
count = 0
for f in Path(".").rglob("*.sol"):
    if any(p in {"node_modules","lib","forge-std","out","artifacts","cache"} for p in f.parts):
        continue
    try:
        count += len(pat.findall(f.read_text(errors="ignore")))
    except Exception:
        pass
print(count)
PY

# ─── Docs ─────────────────────────────────────────────────────────────────────

echo "=== docs ==="
ls -d README.md README* docs/ doc/ whitepapers/ whitepaper/ spec/ specs/ paper/ papers/ 2>/dev/null || true

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "=== commit ==="
  git rev-parse --short HEAD 2>/dev/null || echo "unknown"

  # ─── Git history stats ──────────────────────────────────────────────────────

  echo "=== git_unique_authors ==="
  git log --format='%aN' | sort -u | wc -l

  echo "=== git_contributors ==="
  git log --format='%aN' | sort | uniq -c | sort -rn

  echo "=== git_source_contributors ==="
  git log --numstat --format='COMMIT_BY:%aN' -- "$SRC" | \
    awk '/^COMMIT_BY:/{a=substr($0,11);next} NF==3 && $1~/[0-9]/{add[a]+=$1;del[a]+=$2} END{for(a in add)printf "%d\t%d\t%s\n",add[a],del[a],a}' | sort -rn

  echo "=== git_repo_age ==="
  git log --reverse --format='%aI' | head -1
  git log -1 --format='%aI'

  echo "=== git_total_commits ==="
  git rev-list --count HEAD

  echo "=== git_merge_count ==="
  git log --merges --oneline | wc -l

  echo "=== git_hotspots ==="
  git log --name-only --format='' -- "$SRC" | sort | uniq -c | sort -rn | head -15

  echo "=== git_recent_30d ==="
  git log --since='30 days ago' --oneline -- "$SRC" | head -20

  echo "=== git_large_diffs ==="
  git log --format='COMMIT:%h %aN %s' --numstat -- "$SRC" | \
    awk '/^COMMIT:/{if(c && s>0)print s,c;c=$0;s=0;next} NF>=2 && $1~/[0-9]/{s+=$1+$2} END{if(c && s>0)print s,c}' | sort -rn | head -10
else
  echo "=== commit ==="
  echo "unknown"
  echo "=== git_unique_authors ==="
  echo "git unavailable for target root"
  echo "=== git_contributors ==="
  echo "git unavailable for target root"
  echo "=== git_source_contributors ==="
  echo "git unavailable for target root"
  echo "=== git_repo_age ==="
  echo "git unavailable for target root"
  echo "git unavailable for target root"
  echo "=== git_total_commits ==="
  echo "git unavailable for target root"
  echo "=== git_merge_count ==="
  echo "git unavailable for target root"
  echo "=== git_hotspots ==="
  echo "git unavailable for target root"
  echo "=== git_recent_30d ==="
  echo "git unavailable for target root"
  echo "=== git_large_diffs ==="
  echo "git unavailable for target root"
fi
