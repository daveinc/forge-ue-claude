---
name: forge-gameplay-gauntlet
description: Run a bounded adversarial gameplay and presentation improvement loop against a named reference, target feel, or acceptance rubric using playable builds, in-engine frames, fan-out variants, harsh critique, and blind comparison. Use for vertical slices, combat feel, traversal, readability, encounter pacing, UI feedback, or reference-quality gap closure after a playable loop exists.
---

# Forge Gameplay Gauntlet

Improve the playable game rather than optimizing disconnected assets.

## Workflow

1. Require a runnable loop, named target/reference, comparison dimensions, fixed capture conditions, current baseline and human-owned stop/feel gate.
2. Freeze the comparison rubric and choose one bottleneck. Keep unrelated systems outside the round.
3. Fan out independent, bounded alternatives with disjoint write scopes when useful. Use placeholders or targeted visual production to close only gaps that affect the current comparison.
4. Build and capture the alternatives under the same camera, input, hardware and content conditions.
5. Have `gameplay-critic` score play evidence and in-engine frames harshly against the rubric, isolated from the agents that built the alternatives. Run blind A/B when labels could bias judgment.
6. Integrate only the winning change, run regression and performance checks, and record the attempt result.
7. Stop when the human owner accepts the feel, the bounded round limit is reached, or improvement stalls. Escalate unresolved tradeoffs; never invent an automatic quality threshold.

Read [round-contract.md](references/round-contract.md) before starting a round.
