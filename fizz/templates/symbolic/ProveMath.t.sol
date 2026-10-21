// SPDX-License-Identifier: MIT
pragma solidity >=0.6.2 <0.9.0;

// Skeleton for Echidna verification mode (Step 10.5). PLACEHOLDER — it does not
// compile as shipped: replace {Target}/{target} and the example bodies with the
// real contract and properties, and delete what you do not use.
//
// This harness is deliberately SEPARATE from the stateful fizz suite. Verification
// mode reasons about ONE symbolic transaction after the constructor, so the split
// between handlers (which call) and property_* functions (which assert with no
// arguments) makes FuzzTester a useless target: each half is trivially verified and
// nothing is proven. Here, one function takes symbolic inputs, calls, and asserts.
//
// Read fizz/references/symbolic-verification.md before editing. The two rules that
// matter most:
//   * only `verified` means proven; `passed` means "no counterexample, some SMT
//     queries unknown";
//   * under symExecAbstractArith, a counterexample is NOT sound — reproduce it
//     concretely before reporting it as a bug.

import {Target} from "../../../src/Target.sol";

contract ProveMath {
    Target target;

    // Runs concretely before symbolic exploration begins. Keep it minimal: every
    // extra contract and every mapping write becomes solver work, and a setup the
    // engine cannot finish kills every property in the file.
    function setUp() public {
        target = new Target();
    }

    // ─────────────────────────── The uint128 budget ───────────────────────────
    // Every symbolic input (and any derived sum the property depends on, e.g.
    // totalAssets()) carries the same bound. It is the arithmetic abstraction's
    // operand budget: two uint128 factors cannot overflow 256 bits. ~3e20 tokens at
    // 18 decimals — far past any real supply, but a REAL assumption that must be
    // stated wherever the result is reported.

    // ── Pattern A: promote an existing stateless test ─────────────────────────
    // Preferred when the repo already has testFuzz_* over this math. Inherit the
    // repo's own test contract instead of this one and delegate, so the assertion
    // stays the original and cannot drift:
    //
    //   contract ProveConversions is ExistingConversionTests {
    //       function prove_convertToShares(uint256 amount) public {
    //           require(amount <= type(uint128).max);
    //           testFuzz_convertToShares(amount);   // unmodified
    //       }
    //   }

    // ── Pattern B: relational properties written for the prover ───────────────
    // Use these when the exact closed form is out of reach. They are genuine safety
    // properties, not consolation prizes.

    /// more in never yields less out — blocks split/reorder value extraction
    function prove_example_monotonic(uint256 a, uint256 b) public view {
        require(a <= b && b <= type(uint128).max);
        assert(target.convertToShares(a) <= target.convertToShares(b));
    }

    /// value -> shares -> value never grows — blocks first-depositor inflation
    function prove_example_roundtrip(uint256 v) public view {
        require(v <= type(uint128).max);
        assert(target.convertToAssets(target.convertToShares(v)) <= v);
    }

    /// round-up and round-down never differ by more than one wei
    function prove_example_rounding_tight(uint256 x) public view {
        require(x <= type(uint128).max);
        assert(target.previewRoundUp(x) - target.previewRoundDown(x) <= 1);
    }

    // ────────────────────────────── The setup wall ────────────────────────────
    // If a property reads balances through a mapping-based ERC20, the keccak-indexed
    // read nested in abstracted arithmetic usually puts the query past the solver.
    // The only sound workaround is a token whose balanceOf is a SINGLE STORAGE SLOT,
    // and only when the property reads each token at exactly one holder and never
    // moves tokens. If it deposits, transfers, or involves two holders, that model is
    // wrong — leave the property to the fuzz campaign and record it as out of reach.
}
