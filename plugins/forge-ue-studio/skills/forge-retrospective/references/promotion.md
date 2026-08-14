# Learning promotion

Record a claim, observations, confidence, scope, environment fingerprint, counter-evidence, invalidation triggers and promotion state.

Use:

```text
QUARANTINED -> CANDIDATE -> APPROVED
          \-> REJECTED
APPROVED -> STALE -> QUARANTINED after re-probe
```

Require at least two independent successful applications by default. Do not promote a provider globally from one task class, and do not delete failures that explain qualification limits.
