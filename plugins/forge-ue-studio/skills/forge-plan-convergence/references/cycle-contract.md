# Review cycle contract

Store `review_id`, target revision, cycle/max cycles, reviewers, source-grounding coverage, current high/actionable counts, findings, closures, uncheckable references, and status.

Use the states:

```text
PENDING -> REVIEWING -> REVISING -> REVIEWING
                         |             |
                         +-> CONVERGED +-> STALLED or ESCALATED
```

Require the reviewer result to include:

```text
CYCLE_SUMMARY: current_high=N current_actionable=M
```

Do not derive current counts by searching accumulated review history. A clean review must state what was checked and what remained uncheckable.
