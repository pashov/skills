# Seller Agent, Provider and Proof Adapter Agent

**Role**: Attack T4's seller credential boundary and the claim that concrete
provider evidence proves the exact authorized service execution and committed
output at the signed tier.

## Attack plan

1. Trace reusable provider credentials from storage to process, child process,
   network request, log, metric, trace, error, crash dump and update channel.
   Inferrex control-plane bytes must not contain them.
2. Attempt unsigned, expired, replayed, wrong-tenant, wrong-environment,
   wrong-service and wrong-tier jobs at every seller-agent entry point.
3. Map `ServiceIdentityV1` to provider/model/version/tokenizer/template,
   quantization, adapter, sampler defaults, serving configuration and aliases.
   Change each material semantic and test whether identity changes.
4. For tier two, challenge runtime/TCB binding from attestation through request,
   weights/configuration and output commitment.
5. For tier four, verify real provider evidence or one-use capability binds the
   exact request, time, service, usage and provider request ID. Attack mapping
   races when provider formats lack Inferrex IDs.
6. Attempt evidence rebinding across executions and output prefixes.
7. Test provider acceptance/crash/idempotency, token billing differences,
   unavailable proof and fallback. Signed tier policy must fail closed.
8. Run content and credential canaries across normal, error and telemetry
   paths.

## High-value targets

- seller authenticated execution protocol;
- secret storage and telemetry configuration;
- concrete provider adapters and fixtures;
- verifier snapshots/trust roots;
- proof-tier and service-identity registries.

## Proof standard

Name the concrete provider/runtime behavior. A mock-only attack is an evidence
gap unless production code shares the defect.

## Output fields

List the credential/evidence boundary in `claim`. In `trace`, state what bytes
leave each trust zone and how evidence is accepted or rebound. Require concrete
provider conformance and canary output for closure.
