# ERC1155 Attack Vectors

10 attack vectors specific to ERC1155 tokens. For each: detection pattern (what to look for in code) and false-positive signals (what makes it NOT a vulnerability even if the pattern matches).

---

**1. ERC1155 totalSupply Inflation via Reentrancy Before Supply Update**

- **Detect:** Contract extends `ERC1155Supply` (or custom supply tracking) and increments `totalSupply[id]` AFTER calling `_mint`, which triggers the `onERC1155Received` callback on the recipient. During the callback, `totalSupply[id]` has not yet been updated. Any governance, reward, or share-price formula that reads `totalSupply[id]` inside the callback (directly or via a re-entrant call to the same contract) observes an artificially low total, inflating the caller's computed share. OZ pre-4.3.2 `ERC1155Supply` had exactly this ordering — supply updated post-callback. Real finding: ChainSecurity disclosure, OZ advisory GHSA-9c22-pwxw-p6hx (2021).
- **FP:** OZ ≥ 4.3.2 used — supply incremented before the mint callback in patched versions. `nonReentrant` on all mint functions. No totalSupply-dependent logic is callable from within a mint callback path.

**2. ERC1155 safeBatchTransferFrom with Unchecked Mismatched Array Lengths**

- **Detect:** Custom ERC1155 overrides `_safeBatchTransferFrom` or iterates `ids` and `amounts` arrays in a loop without first asserting `require(ids.length == amounts.length)`. A caller passes `ids = [1, 2, 3]` and `amounts = [100]` — the loop processes only as many iterations as the shorter array (Solidity reverts on OOB access in 0.8+, but a `for (uint i = 0; i < ids.length; i++)` loop that reads `amounts[i]` will revert mid-batch rather than rejecting cleanly). In assembly-optimized or unchecked implementations, the shorter array access silently reads uninitialized memory or produces wrong transfers.
- **FP:** OZ ERC1155 base used without overriding batch transfer — OZ checks `ids.length == amounts.length` at the start and reverts with `ERC1155InvalidArrayLength`. Custom override explicitly asserts equal lengths as its first statement before any transfer logic.

**3. ERC1155 onERC1155Received Return Value Not Validated**

- **Detect:** Custom ERC1155 implementation calls `IERC1155Receiver(to).onERC1155Received(operator, from, id, value, data)` when transferring to a contract address, but does not check that the returned `bytes4` equals `IERC1155Receiver.onERC1155Received.selector` (`0xf23a6e61`). A recipient contract that returns any other value (including `bytes4(0)` or nothing) should cause the transfer to revert per EIP-1155, but without the check the transfer silently succeeds. Tokens are permanently locked in a contract that cannot handle them.
- **FP:** OZ ERC1155 used as base — it validates the selector and reverts with `ERC1155InvalidReceiver` on mismatch. Custom implementation explicitly checks: `require(retval == IERC1155Receiver.onERC1155Received.selector, "ERC1155: rejected")`.

**4. ERC1155 setApprovalForAll Grants All-Token-All-ID Operator Access**

- **Detect:** Protocol requires `setApprovalForAll(protocol, true)` to enable deposits, staking, or settlement across a user's ERC1155 holdings. Unlike ERC20 allowances (per token, per amount) or ERC721 single-token approve, ERC1155 has no per-ID or per-amount approval granularity — `setApprovalForAll` is an all-or-nothing grant covering every token ID the user holds and any they acquire in the future. A single compromised or malicious operator can call `safeTransferFrom(victim, attacker, anyId, fullBalance, "")` for every ID in one or more transactions, draining everything. Pattern: protocol documents "approve all tokens to use our platform" as a required first step.
- **FP:** Protocol uses individual `safeTransferFrom(from, to, id, amount, data)` calls that each require the user as `msg.sender` directly. Operator is a formally verified immutable contract whose only transfer logic routes tokens to the protocol's own escrow. Users are prompted to revoke approval via `setApprovalForAll(protocol, false)` after each session.

**5. ERC1155 Batch Transfer Partial-State Callback Window**

- **Detect:** Custom ERC1155 batch mint or transfer processes IDs in a loop — updating `_balances[id][to]` one ID at a time and calling `onERC1155Received` per iteration, rather than committing all balance updates first and then calling the single `onERC1155BatchReceived` hook once. During the per-ID callback, later IDs in the batch have not yet been credited. A re-entrant call from the callback can read stale balances for uncredited IDs, enabling double-counting or theft of not-yet-transferred amounts. Pattern: `for (uint i; i < ids.length; i++) { _balances[ids[i]][to] += amounts[i]; _doSafeTransferAcceptanceCheck(...); }`.
- **FP:** All balance updates for the entire batch are committed before any callback fires — mirroring OZ's approach: update all balances in one loop, then call `_doSafeBatchTransferAcceptanceCheck` once. `nonReentrant` applied to all transfer and mint entry points.

**6. ERC1155 Fungible / Non-Fungible Token ID Collision**

- **Detect:** Protocol uses ERC1155 to represent both fungible tokens (specific IDs with `supply > 1`) and unique items (other IDs with intended `supply == 1`), relying only on convention rather than enforcement. No `require(totalSupply(id) == 0)` before minting an "NFT" ID, or no check that prevents minting additional copies of an ID already at supply 1. An attacker who can call the public mint function mints a second copy of an "NFT" ID, breaking uniqueness. Or role tokens (e.g., `ROLE_ID = 1`) are fungible and freely tradeable, undermining access control that is gated on `balanceOf(user, ROLE_ID) > 0`.
- **FP:** Contract explicitly enforces `require(totalSupply(id) + amount <= maxSupply(id))` with `maxSupply` set to 1 for NFT IDs at creation time. Fungible and non-fungible ranges are disjoint and enforced with `require(id < FUNGIBLE_CUTOFF || id >= NFT_START)`. Role tokens are non-transferable (transfer overrides revert for role IDs).

**7. ERC1155 uri() Missing {id} Substitution Causes Metadata Collapse**

- **Detect:** `uri(uint256 id)` returns a fully resolved URL (e.g., `"https://api.example.com/token/42"`) instead of a template containing the literal `{id}` placeholder as required by EIP-1155. Clients and marketplaces that follow the standard substitute the zero-padded 64-character hex token ID for `{id}` client-side — returning a fully resolved URL breaks this substitution, pointing all IDs to the same metadata endpoint or creating malformed double-substituted URLs. Additionally, if `uri(id)` returns an empty string or a hardcoded static value identical for all IDs, off-chain systems treat all tokens as identical, destroying per-token metadata and market value.
- **FP:** `uri(id)` returns a string containing the literal `{id}` substring per EIP-1155 spec, and clients substitute the hex-encoded token ID. Protocol overrides `uri(id)` to return a fully unique per-ID on-chain URI (e.g., full base64-encoded JSON) and explicitly documents deviation from the `{id}` substitution requirement.

**8. Missing onERC1155BatchReceived Causes Token Lock on Batch Transfer**

- **Detect:** Receiving contract implements `IERC1155Receiver.onERC1155Received` (for single transfers) but not `IERC1155Receiver.onERC1155BatchReceived` (for batch transfers), or implements the latter returning a wrong selector. `safeBatchTransferFrom` to such a contract reverts on the callback check, permanently preventing batch delivery. Protocol that accepts individual deposits from users but attempts batch settlement or batch reward distribution internally will be permanently stuck if the recipient is one of these incomplete receivers. Pattern: `onERC1155BatchReceived` is absent, `returns (bytes4(0))`, or reverts unconditionally.
- **FP:** Contract implements both `onERC1155Received` and `onERC1155BatchReceived` returning the correct selectors, or inherits from OZ `ERC1155Holder` which provides both. Protocol's internal settlement exclusively uses single-item `safeTransferFrom` and is documented to never issue batch calls to contract recipients.

**9. ERC1155 Custom Burn Without Caller Authorization Check**

- **Detect:** Custom `burn(address from, uint256 id, uint256 amount)` or `burnBatch(address from, ...)` function is callable by any address without verifying that `msg.sender == from` or that `msg.sender` is an approved operator for `from`. Any caller can burn another user's tokens by passing their address as `from`. Pattern: `function burn(address from, uint256 id, uint256 amount) external { _burn(from, id, amount); }` with no authorization guard. Distinct from OZ's `_burn` (which is internal) — the risk is in public wrappers that expose it without access control.
- **FP:** Burn function requires `require(from == msg.sender || isApprovedForAll(from, msg.sender), "not authorized")` before calling `_burn`. OZ's `ERC1155Burnable` extension used — it includes the owner/operator check. Burn is restricted to a privileged role (admin/governance) and the `from` address is not user-supplied.

**10. ERC1155 ID-Based Role Access Control With Publicly Mintable Role Tokens**

- **Detect:** Protocol implements access control by checking ERC1155 token balance: `require(balanceOf(msg.sender, ADMIN_ROLE_ID) > 0)` or `require(balanceOf(msg.sender, MINTER_ROLE_ID) >= 1)`. The role token IDs (`ADMIN_ROLE_ID`, `MINTER_ROLE_ID`) are public constants. If the ERC1155 `mint` function for those IDs is not separately access-controlled — e.g., it's callable by any holder of a lower-tier token, or via a public presale — any attacker can acquire the role token and gain elevated privileges. Role tokens are also transferable by default, creating a secondary market for protocol permissions.
- **FP:** Minting of all role-designated token IDs is gated behind a separate access control system (e.g., OZ `AccessControl` with `MINTER_ROLE` on the ERC1155 contract itself). Role tokens for privileged IDs are non-transferable: `_beforeTokenTransfer` reverts for those IDs when `from != address(0) && to != address(0)`. Protocol uses a dedicated non-token access control system rather than ERC1155 balances for privilege gating.

