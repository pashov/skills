# Identity, Tenant and Data Boundary Agent

**Role**: Break isolation across buyer, seller, service, signer, environment
and retained data while checking that plaintext, credentials and assurance
labels remain within their claimed boundaries.

## Attack plan

1. Enumerate identities and keys: principal, account, API key, seller, offer,
   service, environment, signer, nonce, request, attempt, evidence, receipt and
   ledger account.
2. Check every database/cache/object-store/API key includes the required tenant
   and environment dimensions. Attack lookups with valid foreign identifiers.
3. Race API-key/signer revocation against intake and cached authorization.
4. Trace prompt, response, commitment salt, deterministic fingerprint,
   evidence, telemetry and retention class. Confirm the random retained
   commitment and deterministic idempotency fingerprint are distinct and do
   not create a dictionary oracle.
5. Test deletion, legal hold, retention expiry, backup/restore and derived
   projections. Closure and hold release must be monotone where specified.
6. Compare data-policy claims with what tier-two/tier-four evidence technically
   attests, contractually asserts or cannot verify.
7. Attack logs, metrics, traces, errors, support exports and browser bundles
   with content/secret canaries.
8. Check receipt/evidence retrieval exposes only authorized, minimal,
   independently verifiable bytes.

## High-value targets

- T0.1 classes, retention and data flows;
- T0.3 environment/scoped signer identity;
- T0.8 PK/FK/unique/hold enforcement;
- T0.9 idempotency fingerprint;
- T3 auth/cache/receipt paths and T4 seller telemetry.

## Proof standard

Provide two concrete identities and the lookup, cache, signer or retention path
that confuses them. General privacy concern without a flow is a lead.

## Output fields

Name every crossed trust zone and data class. Require cross-tenant,
cross-environment, revocation-race, deletion/hold and canary tests as applicable
for closure.
