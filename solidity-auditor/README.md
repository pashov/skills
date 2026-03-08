# Solidity Auditor

A security agent with a simple mission - findings in minutes, not weeks.

Built for:

- **Solidity devs** who want a security check before every commit
- **Security researchers** looking for fast wins before a manual review
- **Just about anyone** who wants an extra pair of eyes.

Not a substitute for a formal audit - but the check you should never skip.

## Demo

_Portrayed below: finding multiple high-confidence vulnerabilities in a codebase_

![Running solidity-auditor in terminal](../static/skill_pag.gif)

## Usage

```bash
# Scan the full repo (default)
/solidity-auditor

# Full repo + adversarial reasoning agent (slower, more thorough)
/solidity-auditor deep

# Review specific file(s)
/solidity-auditor src/Vault.sol
/solidity-auditor src/Vault.sol src/Router.sol

# Write report to a markdown file (terminal-only by default)
/solidity-auditor --file-output
```

## Constraints (optional)

Drop a `.pashov-skills-constraints.yaml` in your repo root to tell the skill what your codebase does and doesn't use. Agents will skip irrelevant attack vectors during triage, reducing noise and scan time.

```yaml
tokens: [USDC, WETH]        # skip exotic-token vectors
standards: [ERC20]           # skip ERC721/ERC1155/ERC4626 vectors
cross_chain: false           # skip LayerZero/bridge vectors
proxy_pattern: none          # none | transparent | uups | diamond | beacon
oracle: chainlink            # chainlink | twap | pyth | custom | none
account_abstraction: false   # skip ERC-4337 vectors
```

All fields optional. Code overrides constraints.

## Known Limitations

**Codebase size.** Works best up to ~2,500 lines of Solidity. Past ~5,000 lines, triage accuracy and mid-bundle recall drop noticeably. For large codebases, run per module rather than everything at once.

**What AI misses.** AI is strong at pattern matching — missing access controls, unchecked return values, known reentrancy shapes. It struggles with relational reasoning: multi-transaction state setups, specification/invariant bugs, cross-protocol composability, game-theory attacks, and off-chain assumptions. AI catches what humans forget to check. Humans catch what AI cannot reason about. You need both.
