# Eval Runner

Run the solidity-auditor skill against benchmark repos and compare results to ground truth.

## Usage

```
claude "read evals/runner.md and run all benchmarks"
claude "read evals/runner.md and run dodo"
```

## Setup

Resolve paths, create the plugin symlink, get the commit hash, and generate a timestamp.

`SKILL_DIR` is the `solidity-auditor/` directory (parent of `evals/`). `REPO_ROOT` is its parent (the git repo root). Both must be absolute paths.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
SKILL_DIR="$REPO_ROOT/solidity-auditor"
mkdir -p /tmp/audit-plugin/skills && ln -sfn "$SKILL_DIR" /tmp/audit-plugin/skills/solidity-auditor
COMMIT=$(git -C "$REPO_ROOT" rev-parse --short=7 HEAD)
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
echo "commit=$COMMIT timestamp=$TIMESTAMP"
```

## Run

Each `.md` file in `evals/benchmarks/` is a benchmark with frontmatter: `repo_url`, `repo_ref` (optional), `contracts_dir` (optional). Run all unless the user named specific ones.

For each benchmark, clone the repo (shallow, skip if `/tmp/eval-{name}` exists) and create `{run_dir}` at `evals/results/{name}/{timestamp}-{commit}`.

Run benchmarks **sequentially** in this fixed order: **pooltogether → dodo → megapot**. Each run gets a fresh `claude` process so context does not carry over between benchmarks.

The `--plugin-dir /tmp/audit-plugin` flag is **required** — it makes the skill discoverable via the symlink created in Setup. Without it, `claude` will report "Unknown skill: solidity-auditor".

```bash
BENCHMARKS_DIR="$SKILL_DIR/evals/benchmarks"
RESULTS_DIR="$SKILL_DIR/evals/results"

for name in pooltogether dodo megapot; do
  BENCH="$BENCHMARKS_DIR/$name.md"
  [ -f "$BENCH" ] || continue

  # Read contracts_dir from frontmatter (optional, defaults to repo root)
  CONTRACTS_DIR=$(grep '^contracts_dir:' "$BENCH" | sed 's/contracts_dir: *//' || true)
  WORK_DIR="/tmp/eval-$name${CONTRACTS_DIR:+/$CONTRACTS_DIR}"
  RUN_DIR="$RESULTS_DIR/$name/$TIMESTAMP-$COMMIT"

  echo "=== Starting $name ==="
  mkdir -p "$RUN_DIR" && \
  cd "$WORK_DIR" && mkdir -p assets/audit-logs && \
  claude --print --plugin-dir /tmp/audit-plugin --dangerously-skip-permissions \
    "run solidity auditor skill with --log-output" 2>&1 | tee "$RUN_DIR/full-output.txt" && \
  cp -r "$(ls -dt assets/audit-logs/*/ | head -1)"* "$RUN_DIR/" 2>/dev/null; \
  cp "$BENCH" "$RUN_DIR/ground-truth.md"
  echo "=== Finished $name ==="
done
echo "All benchmarks complete."
```

After all complete, for each `{run_dir}`: read `evals/compare.md`, compare `{run_dir}/ground-truth.md` against `{run_dir}/final-report.md`, write `summary.md` to `{run_dir}/`. Print each summary and `=== All done. {count} benchmarks. ===`
