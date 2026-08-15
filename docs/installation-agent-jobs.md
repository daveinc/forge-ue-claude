# Installation agent jobs

Deterministic probes run first. Agents interpret bounded artifacts rather than rediscovering the machine through chat.

These jobs are executed by `$forge-bootstrap`; this table is not merely advisory. The overlay is installed first, then the workflow stops so a fresh project task can load `AGENTS.md`, project-local agents, and directives. `$forge-next` detects the incomplete bootstrap and routes to `$forge-bootstrap --resume`; applicable jobs are compiled into `.forge/state/install-jobs.json`, dispatched by wave, independently verified, and summarized in `.forge/state/bootstrap-report.json`. A host that cannot dispatch agents records `DEGRADED_INLINE` rather than silently collapsing the jobs into the orchestrator.

| Wave | Agent job | Output |
|---:|---|---|
| 1 | Host/config investigator | OS, hardware, Codex/GSD and write-boundary snapshot |
| 1 | Unreal investigator | Engine/project/plugin/build route inventory |
| 1 | Tool/model investigator | Codex resident capabilities, Blender, MCPs, VibeUE, installed local runtimes, entitled services, approved remote APIs, and provider inventory |
| 1 | VCS/infrastructure investigator | Revision, locks, DDC, build and platform readiness |
| 2 | Conflict/policy analyst | Safe merge and approval proposals |
| 2 | Capability profiler | Contracts and known-good/known-bad probe results |
| 2 | Provider evaluator | Codex baseline plus per-task local-offload quality, context, cost, latency and contention scores |
| 2 | Visual route evaluator | Blender versus Unreal asset/rig/animation benchmarks |
| 3 | Workflow compiler | Capability-aware playable and visual DAGs |
| 3 | Context router | Minimal work packets/referrals that let local workers process heavy sources without inheriting resident chat context |
| 3 | Project synthesizer | Overlay, roles, lanes and acceptance registry |
| 4 | Acceptance workers | Independent bounded suite evidence |
| 4 | Fresh-reader reviewer | Cold-start reproducibility verdict |
| 4 | Install reporter | Verified, assumed, unavailable and proposed state |

Bootstrap extractors for Unreal API, craft sources, project knowledge and live tools use the same Research absorption contract during first installation and later updates.

GSD itself uses a deterministic bootstrap before these jobs: preview the exact pinned package, obtain separate approval for the external install, install its Codex integration, inventory the resulting runtime/skills/agents, then verify Forge/GSD coexistence in a new task. Detection is not qualification; a failed or partial GSD install leaves the workflow visibly blocking instead of being silently assumed.

The deterministic installer also writes `.forge/capabilities/detected.json`. This is a detection profile, not a qualification grant. Capability Admin records consent and task-specific evaluation separately, then activates only the phase surfaces needed by compiled work packets.

Bootstrap completion writes `$forge-next` as its handoff and stops. Forge Next then selects Forge Init only for a true greenfield project; existing documents, Unreal/code, or GSD state route through ingestion, onboarding, or GSD's exact smart-entry action instead.
