# Forge Retrospective — workflow

## Workflow

1. Freeze repair work. Inspect revision history, work orders, attempts, leases, capability snapshots, review cycles, phase artifacts, acceptance evidence, tool outputs, and filesystem state read-only.
2. Detect stuck loops, missing artifacts, partial-plan drift, abandoned work, interruption, scope drift, undeclared writes, stale capability evidence, test regression, and broken handoffs.
3. Ground every anomaly in specific evidence. Mark a root cause as a hypothesis when proof is incomplete. Redact secrets.
4. Write a forensic report with evidence summary, confidence, likely cause, ruled-out causes, untested explanations, and recommended actions. Give the pass to `forensic-investigator`, never to the agent that produced the work under investigation. Never repair during the forensic pass.
5. Contain GSD's `extract-learnings.md` after an accepted phase or resolved incident, then shape its result into atomic learning records using [promotion.md](../skills/forge-retrospective/references/promotion.md). Own the forensic pass natively; delegate only the extraction.
6. Quarantine new records. Promote a recipe only after repeated independent success under a declared scope, and retain failed attempts and contradictory evidence.
7. Invalidate learning after a relevant environment, engine, provider, schema, hardware, or workflow change.
8. Keep production metrics in canonical JSON. Generate a derived XLSX or CSV scorecard on request and verify it visually; never make the spreadsheet the source of truth.
