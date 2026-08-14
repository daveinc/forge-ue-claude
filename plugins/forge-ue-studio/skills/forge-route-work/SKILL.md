---
name: forge-route-work
description: Use Codex as resident supervisor while compiling, ranking, and dispatching bounded game-production work across qualified local/remote models, Unreal routes, Blender, research, build, and QA lanes. Use when choosing work batches, parallelizing departments, offloading context-heavy tasks, minimizing token/tool cost, recovering attempts, or adapting after capability changes.
---

# Forge Route Work

Use Codex as the resident occupant and supervisor. Select optional local/remote occupants per bounded attempt; do not assign a department to a provider or serialize independent departments.

## Dispatch workflow

1. Load the approved GDD decision IDs, dependency DAG, current revision, capability/qualification/activation registries, lane leases, budgets, and acceptance registry.
2. Finish or unblock in-flight work before opening avoidable new work.
3. Find ready work with satisfied hard prerequisites and disjoint write sets.
4. Keep design, gameplay, visual, audio, research, and QA lanes concurrent once their contracts exist.
5. Decide whether the task is safely decomposable. Keep unresolved design, novel architecture, cross-system integration, delicate mutation and final synthesis on Codex by default.
6. For bounded work, apply hard filters and rank offload routes using [routing.md](references/routing.md). Prefer qualified free/local/already-installed workers when resident-context, time or lane savings exceed handoff and verification cost.
7. Select isolation before dispatch: use a clean-base Git worktree for concurrent text/code writers, an LFS lock or project-exclusive lease for binary assets, and read-only isolation for reviewers. Never let two workers share an undeclared write surface.
8. Activate only the packet's required optional surfaces and acquire declared resources atomically. Every Unreal package writer shares the project super-lock; editor-open, editor-closed, and human routes are mutually exclusive.
9. Compile an immutable minimal work packet with revision, task/complexity class, objective, non-goals, referrals, inputs, exact write scope, isolation, leases, capabilities, context budget, output contract, acceptance, verification, evidence, and invalidation hashes. Do not forward the full GDD or resident conversation.
10. Dispatch independent packets concurrently. Give the verifier the requirement, artifact/diff, acceptance, and evidence, not builder reasoning.
11. Require a structured attempt result that separates observed facts, inferences, findings, touched artifacts, evidence, verification, residual risk and next action.
12. On failure, inspect actual artifacts before retry. Substitute a second occupant before changing competence scores when the brief or tool may be defective. Use `$forge-retrospective` for inconsistent or repeated failures.
13. Persist transitions, deactivate packet-only surfaces and release leases. Resume from state, never chat memory.

Use `$forge-capability-admin` to qualify or activate routes and `$forge-research` if no verified capability closes a required step. Block only that step when no fallback exists.
