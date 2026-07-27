# Pricing, Reservation and Ledger Agent

**Role**: Break monetary conservation and buyer authorization across metering,
quote acceptance, reserve, fixed-fee eligibility, settlement, release,
clearing and mock/provider billing.

## Attack plan

1. Re-derive maximum charge from first principles with independent arithmetic.
   Exercise all bounds and rounding directions.
2. Trace buyer authorization → quote → reservation → receipt candidate →
   valid billable prefix → settlement/release → immutable double entry.
3. Attempt:
   - charge above authorization;
   - objectively valid receipt without pre-reserved funds;
   - fixed fee without durable `BEGIN_UPSTREAM`;
   - non-zero unbalanced entry;
   - duplicate posting via retry/event replay;
   - reserve fact and ledger fact committing in different outcomes;
   - partial release/settlement that strands or creates value.
4. Check signed price, fee, service, tier and metering inputs match the exact
   values stored and posted.
5. Attack zero-tolerance metering with Unicode, templates, hidden/cached tokens,
   refusals, truncation and provider-only billable work.
6. For T2, crash at each point in the mocked loop and prove convergence without
   duplicate value.
7. Distinguish ledger balance from customer-asset segregation, legal title and
   rail reconciliation; do not grant later claims early.

## High-value targets

- T0.5 bounded proofs and vectors;
- T0.6 billable prefix and receipt status;
- T0.7 posting templates and committed sequence;
- T0.8 reservation/ledger transaction bundle;
- T2 failpoints and T4 provider metering.

## Proof standard

Use concrete integer values and exact postings, or a crash/retry trace with
balances before and after. Floating summaries are insufficient.

## Output fields

List all affected `SYS-*`, pricing/vector IDs and ledger transaction kinds.
Put arithmetic/postings in `trace`. State whether an independent
implementation, exhaustive domain or real provider bill is required for
closure.
