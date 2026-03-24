#!/bin/bash
# Step 1: Enumerate source files, line counts, nSLOC, test stats, docs, commit, and git history stats
# Usage: enumerate.sh <project-root> <src-dir>
# Output: labeled sections consumed by the x-ray skill

set -e
ROOT="${1:-.}"
SRC="${2:-src}"

cd "$ROOT"

# ─── Toolchain ────────────────────────────────────────────────────────────────

echo "=== Toolchain ==="
if [ -f foundry.toml ]; then echo "foundry"
elif [ -f hardhat.config.js ] || [ -f hardhat.config.ts ]; then echo "hardhat"
else echo "unknown"; fi

# ─── Source files with line counts ────────────────────────────────────────────

echo "=== Source (with line counts) ==="
find "$SRC" -name '*.sol' \
  -not -path '*/test/*' -not -path '*/tests/*' -not -path '*/script/*' \
  -not -path '*/lib/*' -not -path '*/node_modules/*' -not -path '*/forge-std/*' \
  -not -path '*/out/*' -not -path '*/broadcast/*' -not -path '*/artifacts/*' \
  -not -path '*/cache/*' 2>/dev/null | sort | xargs wc -l 2>/dev/null

# ─── nSLOC (non-blank, non-comment lines) per file ───────────────────────────

echo "=== nSLOC ==="
sum=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  t=$(grep -cP '\S' "$f" || true)
  c=$(grep -cP '^\s*(//|/\*|\*|\*/)' "$f" || true)
  n=$((t - c))
  printf "%s: %d\n" "$f" "$n"
  sum=$((sum + n))
done < <(find "$SRC" -name '*.sol' \
  -not -path '*/test/*' -not -path '*/tests/*' \
  -not -path '*/script/*' -not -path '*/lib/*' \
  -not -path '*/node_modules/*' -not -path '*/forge-std/*' \
  -not -path '*/out/*' -not -path '*/broadcast/*' \
  -not -path '*/artifacts/*' -not -path '*/cache/*' 2>/dev/null | sort)
echo "TOTAL: $sum"

# ─── NatSpec ──────────────────────────────────────────────────────────────────

echo "=== NatSpec ==="
grep -rcP '@notice|@dev|@param|@return' "$SRC" --include='*.sol' 2>/dev/null | wc -l

# ─── Tests ────────────────────────────────────────────────────────────────────

echo "=== test_files ==="
find . -name '*.sol' -path '*/test*' \
  -not -path '*/node_modules/*' -not -path '*/lib/*' -not -path '*/forge-std/*' \
  -not -path '*/out/*' -not -path '*/artifacts/*' -not -path '*/cache/*' 2>/dev/null | wc -l || echo "0"

echo "=== test_functions ==="
grep -rcP 'function test' . --include='*.sol' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=artifacts --exclude-dir=cache 2>/dev/null | \
  grep -iP '/(test|tests|invariant|echidna|medusa|halmos|fuzz)/' | awk -F: '{s+=$NF}END{print s+0}'

# ── Stateless Fuzz (Foundry) ──
echo "=== stateless_fuzz ==="
grep -rcP 'function\s+testFuzz' . --include='*.sol' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=artifacts --exclude-dir=cache 2>/dev/null | awk -F: '{s+=$NF}END{print s+0}'

# ── Stateful Fuzz: Foundry invariant tests ──
echo "=== foundry_invariant ==="
grep -rcP 'function\s+invariant_' . --include='*.sol' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=artifacts --exclude-dir=cache 2>/dev/null | awk -F: '{s+=$NF}END{print s+0}'

# ── Stateful Fuzz: Echidna ──
echo "=== echidna ==="
ECHIDNA_FUNCS=$(grep -rcP 'function\s+echidna_' . --include='*.sol' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=artifacts --exclude-dir=cache 2>/dev/null | awk -F: '{s+=$NF}END{print s+0}')
ECHIDNA_CONFIGS=$(find . -maxdepth 3 \( -name 'echidna.yaml' -o -name 'echidna_config.yaml' -o -name 'echidna.config.yaml' \) 2>/dev/null | wc -l)
echo "${ECHIDNA_FUNCS}:${ECHIDNA_CONFIGS}"

# ── Stateful Fuzz: Medusa ──
echo "=== medusa ==="
MEDUSA_FUNCS=$(grep -rcP 'function\s+(property_|fuzz_)' . --include='*.sol' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=artifacts --exclude-dir=cache 2>/dev/null | awk -F: '{s+=$NF}END{print s+0}')
MEDUSA_CONFIGS=$(find . -maxdepth 3 \( -name 'medusa.json' \) 2>/dev/null | wc -l)
echo "${MEDUSA_FUNCS}:${MEDUSA_CONFIGS}"

# ── Hardhat Fuzz ──
echo "=== hardhat_fuzz ==="
if [ -f package.json ]; then
  grep -cP '"@chainlink/hardhat-fuzz"|"hardhat-fuzz"|"@openzeppelin/hardhat-fuzz"' package.json 2>/dev/null || echo "0"
else
  echo "0"
fi

# ── Fork Tests ──
echo "=== fork ==="
grep -rcP 'vm\.createFork|createSelectFork|hardhat_reset|FORKING_URL|forking.*url' . --include='*.sol' --include='*.ts' --include='*.js' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=artifacts --exclude-dir=cache 2>/dev/null | awk -F: '{s+=$NF}END{print s+0}'

# ── Formal Verification: Certora ──
echo "=== certora ==="
CERTORA_SPECS=$(find . \( -name '*.spec' -o -name '*.cvl' \) 2>/dev/null | \
  grep -v node_modules | grep -v '/lib/' | wc -l)
CERTORA_CONF=$(find . -maxdepth 3 \( -name '*.conf' -path '*/certora/*' -o -name 'certora.conf' \) 2>/dev/null | wc -l)
echo "${CERTORA_SPECS}:${CERTORA_CONF}"

# ── Formal Verification: Halmos ──
echo "=== halmos ==="
HALMOS_FUNCS=$(grep -rcP 'function\s+check_' . --include='*.sol' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=artifacts --exclude-dir=cache 2>/dev/null | awk -F: '{s+=$NF}END{print s+0}')
HALMOS_CONF=$(find . -maxdepth 3 -name 'halmos.toml' 2>/dev/null | wc -l)
echo "${HALMOS_FUNCS}:${HALMOS_CONF}"

# ── Formal Verification: HEVM ──
echo "=== hevm ==="
grep -rcP 'function\s+prove_' . --include='*.sol' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=artifacts --exclude-dir=cache 2>/dev/null | awk -F: '{s+=$NF}END{print s+0}'

# ── Scribble Annotations ──
echo "=== scribble ==="
SCRIBBLE_ANNOTATIONS=$(grep -rcP '///\s*#if_succeeds|///\s*#if_updated|///\s*#invariant|///\s*#if_assigned' . --include='*.sol' \
  --exclude-dir=node_modules --exclude-dir=lib --exclude-dir=forge-std \
  --exclude-dir=out --exclude-dir=artifacts --exclude-dir=cache 2>/dev/null | awk -F: '{s+=$NF}END{print s+0}')
SCRIBBLE_CONF=$(find . -maxdepth 3 \( -name '.scribble.config.json' -o -name 'scribble.config.json' \) 2>/dev/null | wc -l)
echo "${SCRIBBLE_ANNOTATIONS}:${SCRIBBLE_CONF}"

# ─── Docs ─────────────────────────────────────────────────────────────────────

echo "=== docs ==="
ls -d README.md README* docs/ doc/ whitepapers/ whitepaper/ spec/ specs/ paper/ papers/ 2>/dev/null || true

echo "=== commit ==="
git rev-parse --short HEAD 2>/dev/null || echo "unknown"

# ─── Git history stats ────────────────────────────────────────────────────────

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
