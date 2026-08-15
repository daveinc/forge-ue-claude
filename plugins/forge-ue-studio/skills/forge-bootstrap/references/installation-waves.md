# Installation waves

All jobs use the canonical IDs pre-registered in `.forge/state/packet-registry.json`. Jobs may be skipped only as `NOT_APPLICABLE` with evidence.

| Wave | Work order | Investigation | Preferred isolated role |
|---:|---|---|---|
| 1 | `FI-HOST` | Host, hardware, permissions, Codex and GSD inventory | researcher/explorer |
| 1 | `FI-UNREAL` | Engine, project, plugin, MCP, live/editor-closed/build routes | gameplay engineer/explorer |
| 1 | `FI-TOOLS` | Blender, image/visual tools, local runtimes and entitled services | capability manager/explorer |
| 1 | `FI-VCS` | Git, LFS/locks, worktrees, DDC/build/platform infrastructure | researcher/explorer |
| 2 | `FI-POLICY` | Conflicts, approvals, secrets and mutation boundaries | capability manager |
| 2 | `FI-CAPABILITY` | Capability contracts and safe known-good/seeded-bad probe plan | capability manager |
| 2 | `FI-PROVIDER` | Per-task provider evaluation against Codex baseline | capability manager |
| 2 | `FI-VISUAL` | Blender versus Unreal asset/rig/animation route plan | visual developer/DCC artist |
| 3 | `FI-COMPILE` | Capability-aware production workflow | studio director |
| 3 | `FI-CONTEXT` | Minimal referrals and worker context budgets | studio director |
| 3 | `FI-SYNTHESIS` | Overlay/state synthesis and unresolved actions | studio director |
| 4 | `FI-ACCEPT` | Independent installation acceptance | independent verifier |
| 4 | `FI-REVIEW` | Fresh-reader reproducibility review | independent verifier |
| 4 | `FI-REPORT` | Final evidence-backed bootstrap report | bootstrap orchestrator |

Read-only jobs can share a wave. Any mutation job requires its own declared lane and approval. The orchestrator waits at each wave boundary, persists results, and never does the same job concurrently with a dispatched agent.

