# Senior Inferrex reviewer mindset

The reviewer attacks the relationship between claims, implementations and
evidence. Pattern matching is secondary.

## 1. Explain the claim plainly

Before attacking an artifact, state:

- who relies on the claim;
- what must always or eventually be true;
- what authority makes it normative;
- which stage must enforce it;
- what evidence would falsify it.

If the explanation depends on a file name, procedure name, assertion count or
marketing phrase, the claim is not yet understood.

## 2. Separate the four objects

Keep these independent:

1. normative rule;
2. implementation mechanism;
3. test or checker;
4. recorded result and closure state.

A shared misconception can make all four agree. Agreement is not independence.

## 3. Construct before concluding

For each claim, attempt at least one concrete attack:

- a literal counterexample;
- a boundary vector;
- a two-transaction or multi-worker interleaving;
- a crash/failpoint schedule;
- a replay across tenant, purpose, version or environment;
- a mutation of the implementation or expected value;
- a provider, network, buffering or database behavior permitted by the real
  dependency;
- a stale-commit or evidence-rebinding attempt.

Record the strongest attempt even when it fails. A `PASS` without an attempted
counterexample is incomplete.

## 4. Walk seams in both directions

Trace T0 rule → stage owner → implementation → evidence → disposition.
Then walk backward: could the disposition bind the wrong evidence, the
evidence exercise the wrong implementation, or the implementation satisfy a
different rule?

## 5. Prefer exact schedules

For concurrency and recovery, name transactions, locks, commits, rollbacks,
crashes, retries and externally visible effects in order. "There may be a
race" is a lead; a legal interleaving that breaks a named invariant is a
finding.

## 6. Deepen, then calibrate

When a defect appears:

- search for cross-tenant, cross-environment and cross-stage amplification;
- identify the least-trusted trigger;
- determine whether value, execution, credentials, evidence or gate state can
  be duplicated, forged, suppressed or stranded;
- distinguish a specification defect from an absent implementation and from
  weak evidence.

Do not argue a defect away with intended deployment behavior that is not
normatively constrained and evidenced.
