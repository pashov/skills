#!/usr/bin/env bash
# ensure_foundry.sh — Ensure Foundry (forge), foundry.toml, and forge-std are available.
# Usage: ensure_foundry.sh [PROJECT_ROOT]
# Exit 0 on success, exit 1 with guidance if not.

set -euo pipefail

PROJECT_ROOT="${1:-.}"

if [ ! -d "$PROJECT_ROOT" ]; then
    echo "ERROR: project root does not exist: $PROJECT_ROOT"
    exit 1
fi

# 1. Check forge is installed
if ! command -v forge &>/dev/null; then
    echo "ERROR: forge not found in PATH."
    echo ""
    echo "Install Foundry:"
    echo "  curl -L https://foundry.paradigm.xyz | bash"
    echo "  foundryup"
    echo ""
    echo "Or see: https://www.getfoundry.sh/introduction/installation"
    exit 1
fi

FORGE_VERSION=$(forge --version 2>&1 | head -1)
echo "Foundry detected: $FORGE_VERSION"

# 2. Create a compatible foundry.toml if missing
if [ ! -f "$PROJECT_ROOT/foundry.toml" ]; then
    echo "foundry.toml not found — creating one in $PROJECT_ROOT ..."
    cd "$PROJECT_ROOT"
    HH_CONFIG=""
    if [ -f "hardhat.config.ts" ]; then
        HH_CONFIG="hardhat.config.ts"
    elif [ -f "hardhat.config.js" ]; then
        HH_CONFIG="hardhat.config.js"
    fi

    if [ -n "$HH_CONFIG" ]; then
        echo "Hardhat project detected — writing a Foundry-compatible config..."

        # Hardhat-compatible layout per Foundry docs.
        SRC_DIR=$(grep -oP "sources\s*:\s*['\"]?\K[^'\"',}]+" "$HH_CONFIG" 2>/dev/null | head -1 || true)
        SRC_DIR="${SRC_DIR#./}"
        if [ -z "$SRC_DIR" ]; then
            if [ -d "contracts" ]; then
                SRC_DIR="contracts"
            elif [ -d "src" ]; then
                SRC_DIR="src"
            else
                SRC_DIR="contracts"
            fi
        fi

        ARTIFACTS_DIR=$(grep -oP "artifacts\s*:\s*['\"]?\K[^'\"',}]+" "$HH_CONFIG" 2>/dev/null | head -1 || true)
        ARTIFACTS_DIR="${ARTIFACTS_DIR#./}"
        if [ -z "$ARTIFACTS_DIR" ]; then
            ARTIFACTS_DIR="out"
        fi

        SOLC_VERSION=$(perl -0ne 'print "$1\n" if /version\s*:\s*["'"'"']([^"'"'"']+)["'"'"']/s' "$HH_CONFIG" 2>/dev/null | head -1 || true)
        OPTIMIZER_ENABLED=$(perl -0ne 'print "$1\n" if /optimizer\s*:\s*\{.*?enabled\s*:\s*(true|false)/s' "$HH_CONFIG" 2>/dev/null | head -1 || true)
        OPTIMIZER_RUNS=$(perl -0ne 'print "$1\n" if /optimizer\s*:\s*\{.*?runs\s*:\s*(\d+)/s' "$HH_CONFIG" 2>/dev/null | head -1 || true)
        EVM_VERSION=$(perl -0ne 'print "$1\n" if /evmVersion\s*:\s*["'"'"']([^"'"'"']+)["'"'"']/s' "$HH_CONFIG" 2>/dev/null | head -1 || true)

        LIBS="[\"node_modules\", \"lib\"]"

        REMAPPINGS=""
        if [ -d "node_modules/@openzeppelin/contracts" ]; then
            REMAPPINGS="$REMAPPINGS\"@openzeppelin/contracts/=node_modules/@openzeppelin/contracts/\","
        fi
        if [ -d "node_modules/@openzeppelin/contracts-upgradeable" ]; then
            REMAPPINGS="$REMAPPINGS\"@openzeppelin/contracts-upgradeable/=node_modules/@openzeppelin/contracts-upgradeable/\","
        fi

        cat > foundry.toml <<EOF
[profile.default]
src = "${SRC_DIR}"
out = "${ARTIFACTS_DIR}"
libs = ${LIBS}
EOF

        if [ -n "$SOLC_VERSION" ]; then
            echo "solc = \"${SOLC_VERSION}\"" >> foundry.toml
        fi
        if [ -n "$OPTIMIZER_ENABLED" ]; then
            echo "optimizer = ${OPTIMIZER_ENABLED}" >> foundry.toml
        fi
        if [ -n "$OPTIMIZER_RUNS" ]; then
            echo "optimizer_runs = ${OPTIMIZER_RUNS}" >> foundry.toml
        fi
        if [ -n "$EVM_VERSION" ]; then
            echo "evm_version = \"${EVM_VERSION}\"" >> foundry.toml
        fi
        if [ -n "$REMAPPINGS" ]; then
            REMAPPINGS="${REMAPPINGS%,}"
            echo "remappings = [${REMAPPINGS}]" >> foundry.toml
        fi

        echo "foundry.toml configured for Hardhat layout (src=${SRC_DIR}, out=${ARTIFACTS_DIR}, libs=node_modules+lib)."
    else
        echo "Non-Hardhat project detected — writing a default Foundry config..."
        cat > foundry.toml <<EOF
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
EOF
    fi
else
    echo "foundry.toml detected."
fi

# 3. Check forge-std is installed (required by FoundryTester.sol)
if [ ! -d "$PROJECT_ROOT/lib/forge-std" ]; then
    echo "forge-std not found — installing..."
    cd "$PROJECT_ROOT"
    forge install foundry-rs/forge-std
    echo "forge-std installed."
else
    echo "forge-std detected."
fi
exit 0
