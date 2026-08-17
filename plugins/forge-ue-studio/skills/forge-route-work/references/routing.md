# Routing and lanes

Use the resident host as the resident route. Reject offload routes missing required access, modality, quality, safety, context, acceptance proof, or mutation permission. Rank survivors by their advantage over the resident-host baseline:

```text
expected quality + free/local advantage + parallelism gain
- retry risk - latency - money - queue cost - lane contention - handoff cost
```

Installed local routes normally win qualified bounded work when they save resident context or parallel time. Free routes never bypass acceptance. Keep complex/ambiguous/integrative work with the resident host by default. Scores are per task and complexity class and decay after relevant change.

Activate only the selected packet's required optional surfaces. Charge their measured host instruction/schema context, startup, briefing and shutdown costs. Keep one canonical surface for duplicate capabilities unless a controlled comparison requires both.

Good offload classes include long extraction/indexing, log triage, asset or image-to-3D breakdown, bounded code/tests, first-pass review, variants and repetitive DCC operations. Send minimal referrals and schemas; require structured evidence. Passing one class never grants another.

Primary lanes include project-exclusive Unreal mutation, native live MCP, live Python, editor-closed commandlet, human editor, Blender/DCC, GPU capacity, VCS ownership, build/cook/shader, network/provider budget, and human visual review.

For concurrent text or code mutation, start each worker from the same clean immutable revision in a dedicated Git worktree and branch. Merge only after packet verification. Git worktrees do not make Unreal binary packages mergeable: use Git LFS locks or a project-exclusive lease for those assets. Reviewers receive a read-only artifact or diff and must not reuse the builder workspace.

`forge.py exec acquire` establishes all of that, and nothing else may. It holds the ledger under a cross-process mutex while it checks the exclusive groups in `.forge/state/leases.json`, so two workers racing one lane produce a holder and a refusal rather than two writers. It rolls back on partial failure, so a lock it could not take never becomes a lease it appears to hold. A refusal is a routing input, not an obstacle to work around.

It also refuses work routing never authorised. `forge.py route --apply` records its decision in `.forge/state/route-decisions.json` under the canonical work order, and `exec acquire` resolves the decision for the packet's work order from there rather than being handed one. So an agent that skipped routing cannot acquire by omitting a flag, and a decision the environment has outlived cannot authorise a lane it no longer describes. Scoring the route and holding the lane are one path, not two.

Every packet declares immutable revision, referrals, write scope, lane leases, context budget, output contract, verification and invalidation hashes. Every result separates observations from inference and lists touched artifacts, evidence, residual risk and next action.

The work order is resolved against `.forge/state/packet-registry.json` before provider scoring. A route request with an unknown ID fails closed. An alias resolves to its canonical ID and does not create a new packet identity.

Blender and Unreal visual authoring may alternate or split stages based on representative benchmark evidence. Prefer Blender when it keeps the Unreal editor free; prefer Unreal for demonstrated in-engine, Control Rig, Sequencer, retargeting, procedural, or round-trip advantages.
