# Forge Gameplay Gauntlet — workflow

## Workflow

1. Require a runnable loop, named target or reference, comparison dimensions, fixed capture conditions, current baseline, and a human-owned stop gate.
2. Freeze the comparison rubric and choose one bottleneck. Keep unrelated systems outside the round.
3. Fan out independent bounded alternatives with disjoint write scopes. Use placeholders or targeted visual production to close only gaps affecting the current comparison.
4. Build and capture every alternative under the same camera, input, hardware, and content conditions.
5. Have `gameplay-critic` score play evidence and in-engine frames harshly against the rubric, isolated from the agents that built the alternatives. Run blind A/B whenever labels could bias judgment.
6. Integrate only the winning change, then run regression and performance checks and record the attempt result.
7. Stop when the human owner accepts the feel, the round limit is reached, or improvement stalls. Escalate unresolved tradeoffs; never invent an automatic quality threshold.
