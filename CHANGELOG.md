# Changelog

Every section below is dated from the tag that released it. One tag is not a release: `v0.1.0` pins the exact tree an external architecture review read, so that its assessment can be reproduced. The work it marks shipped in 0.2.0, and there is no 0.1.0 section for it — the `0.1.0` heading at the bottom is the original release of 2026-08-14.

## 0.7.0 - 2026-08-18

### An order that finished says so

- `.forge/state/work-orders.json` declared four states an order may stop at — `ACCEPTED`, `REJECTED`, `CANCELLED`, `SUPERSEDED` — and **no code wrote any of them**. `dispatch` wrote `DISPATCHED` and nothing ever moved it, so by the schema's own rule that an order resting outside a terminal state is still in flight, every order Forge had ever written was permanently in flight. Resume reads this file rather than conversation memory, which made finished work indistinguishable from work still running.
- `exec release --outcome passed|failed` is where work ends, so that is where the order ends: `passed` records `ACCEPTED`, `failed` records `REJECTED`. The row is updated rather than replaced, so the revision, route source and lanes dispatch recorded survive alongside the outcome and the lease status it closed with.
- `CANCELLED` and `SUPERSEDED` are **deleted**. Neither had an honest trigger, and inventing a verb to justify a declared state is the same defect as declaring one nothing writes. `derived_from` in the packet registry is provenance for packet identity, not a signal that an order in flight was replaced.
- The terminal states are now named once, in code, and the shipped template is checked against that list — the split between a value declared in JSON and a value the code knows is what let four of them go unwritten in the first place.
- `BLOCKED` stays deliberately non-terminal. A blocked lane is resumable, and the record exists so the next session can resume it.
- `record_dispatch` kept its own copy of the ledger write and seeded no `terminal_states`, so a dispatch into a fresh project wrote a document that failed its own required schema. Both writers go through one path now.

### An undetermined lane is diagnosed, then decided under a posture

- Ownership answered `UNDETERMINED` and stopped there, and the two functions that could have explained it were wired only into the MCP route's own handshake. Forge held a reader for the project's `ModelContextProtocolSettings` and never consulted it when deciding whether an editor was live.
- The ownership decision now reads those settings. Silence from a server whose `bAutoStartServer` is off is reported as **proving nothing**, rather than counted as evidence that no editor is running — an open, healthy editor answers nothing until the server is started. And an answer arriving from an endpoint the project's editor is not configured to serve no longer contradicts an empty process table: it is not that editor, so the lane is `FREE` rather than undecidable.
- `_run_probe` swallowed `OSError`, a timeout and any non-zero exit into one `None` and discarded stderr, so a permission denial, a missing binary and a hung mechanism were indistinguishable. Each now names itself, and an unresolved table carries the attempts that failed. An agent cannot attempt a resolution it cannot name.

### What Forge does with a lane it cannot settle is now the project's decision

- `blocked_lane` in `route-policy.json` decides. `posture: autonomous`, the default, diagnoses, warns, and enters the lane anyway; `posture: fail-closed` refuses and hands it back, which is 0.6.0's behaviour. Dialling back is one key, not a release.
- Autonomy is bounded three ways, because an unstable editor is what turns one fault into a loop. A countdown of `interrupt_seconds` offers a human the lane back before Forge takes it. A lane whose diagnosis fails `consecutive_failure_limit` times running stops being entered until a clean acquire resets the count. And every outcome — refused, intervened, or entered — is written to `.forge/state/work-orders.json` as a `BLOCKED` order, which finally gives that ledger's declared terminal states a writer, and lets the next session resume from state rather than repeat the attempt.
- The prompt and its countdown print to **stderr**, so the payload on stdout stays parseable while the warning shows.
- A run nobody is watching never waits. `stdin.isatty()` alone was not a safe test: on Windows it reports a terminal even when stdin is a null device, so trusting it stalled an unattended run for the entire window. The prompt must be visible on the stream it is printed to and answerable on stdin, and a run declaring `CI` is neither — each case skips the wait and records which one it was.
- **This is the one setting whose cost is measured in lost work.** Entering a lane whose ownership could not be settled can run a commandlet into a project a frozen editor still holds. Diagnosis shrinks how often that is reached and the breaker stops it being retried into, but neither removes it.

### A lane whose state is unknown refuses differently from one that is merely busy

- `UNDETERMINED` reported `UNAVAILABLE_BLOCKING`, and then `resolve_tool_access` collapsed every status to `bound = startswith("AVAILABLE")`, so admission raised the same `route_unreachable` for an editor legitimately holding the lane and for a machine that could not say whether one did. The first is a normal condition to route around; the second is a fault, and the difference was carried only by a sentence in `forge-route-work`.
- `dispatch` now refuses a blocked lane as `route_blocked`, carrying the `ownership` verdict and the `human_action` that names what to resolve. The guarantee the previous release described in prose is now a branch in the code.

### The ownership verdict reaches the thing that was told to read it

- `probe_process_route` has built `ownership`, its evidence and its `human_action` since 0.6.0, and both consumers dropped all three. `forge-route-work` told the agent to *read `ownership` on the route*, and `route-status` never emitted it — an instruction pointing at a field that did not exist.
- Capability contracts and `route-status` rows carry `ownership`, `ownership_evidence` and `human_action`, and `capability-contract` declares the enum, which had never appeared in a schema.

### One decision, one process table

- Answering *does an editor hold this project* spawns a process-table query, and `route-status` asked twice per call: once through the capability contracts and once through its own route loop. `live_editor_holds_project` was the only function in the chain that did not accept the `table` its callees already took.
- It takes one now, and `mcp_status` resolves the table once and passes it down. Measured against a project with the engine command on PATH: **2.34s to 1.88s.** The residual is a duplicated endpoint handshake, which costs a socket connect rather than a subprocess.

### `lane_clear` said less than the field beside it

- `lane_clear` was exactly `status.startswith("AVAILABLE")` in every branch it was set in, while `status` distinguished the three separate reasons a lane was shut: the command was not on PATH, an editor held the project, or inspection could not answer. It had no production reader and was kept alive by the assertions that checked it.
- It is gone, along with `held`, which restated `ownership`. The four hand-written copies of the availability test are one `is_available` helper. Tests now assert the reason a lane is shut rather than that it is shut.

### A degraded capability refuses the packets that use it, not every packet under the work order

- A routing decision is recorded per work order, and `route_conflicts` read `tool_access_degraded` off the decision without asking whether the packet in hand had anything to do with it. A strictly read-only packet — no capabilities, no leases — was refused because an unrelated capability under the same work order was degraded.
- The refusal now requires the packet to claim a degraded capability or to take a lease. A packet that takes nothing is no longer refused for what a sibling packet needed.

## 0.6.0 - 2026-08-17

### The handshake is decided by a parsed reply, not by a substring in one read

- Driving a real editor turned up two defects in Forge's own probe. It read the reply once, bounded, and searched it for `"result"`. Both halves were wrong.
- **A JSON-RPC server that is not MCP passed.** Any endpoint returning a `result` of any shape earned `AVAILABLE_VERIFIED` as Unreal's typed route. The handshake is now decided by a parsed reply whose `result` is an object, and a test proves the old check accepted a server the new one refuses.
- **A reply on a stream that stays open was read as no reply.** Unreal answers on a `text/event-stream` with no content length and keeps the connection open, so there is no EOF; and `read(n)` on a buffered socket waits for exactly *n* bytes, which a short reply never supplies. Both are ways of waiting for an end that never comes, and both report a live editor as a route that did not answer. The probe now reads with `read1` until a frame decodes, under a byte budget.
- The fixture server became threaded, because a single-threaded one cannot represent an endpoint that holds a connection open — the very behaviour that had to be tested.

### An editor answering is not this project's editor answering

- The MCP endpoint is a machine port, not a project's. Ownership treated any answer as proof *this* project was held, so on a workstation running two editors, one project's session shut the other's editor-closed lane. The lane is per-project; the endpoint is not.
- The handshake and process inspection are now weighed together. An answer plus a process holding this project is `HELD`. An answer while other editors run and none holds this project is `FREE`. An answer that inspection cannot attribute at all is `HELD`, still failing closed. And an answer while **no editor process exists at all** is `UNDETERMINED` with a stated human action: two signals contradicting each other is not evidence a project is free.

### A moved MCP port no longer reads as a closed editor

- Forge probes the endpoint the project declares; the editor serves the one its own settings declare. Nothing tied the two together, so a project that moved `ServerPortNumber` presented **exactly** as a project with no editor running — a silent endpoint and no reason given. This was found on a real project configured for port 8800 while Forge probed 8000.
- Forge now reads `[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]` from `Config/DefaultEditorPerProjectUserSettings.ini` and `Saved/Config/<Platform>/…`, layered the way Unreal layers them. A failed handshake reports `engine_settings` and `endpoint_disagreement` as structured fields, and its note **names the port mismatch first**, because it is the one cause that looks identical to every other.
- Both `bAutoStartServer` and `ServerPortNumber` are read at editor startup, so changing either takes effect only after a restart. Every place that tells someone to change them now says so — a setting changed in a running editor is not yet true, which is its own way to spend an afternoon on a route that "should" work.

### Proven against UE 5.8, and the guidance corrected by what that proved

- The acceptance driver was run against a real UE 5.8 editor: **11 passed, 0 failed.** `ue.live.typed` reached `AVAILABLE_VERIFIED` against Epic's own plugin — the claim a stand-in server can never settle — the two editor lanes swapped as the editor opened and closed, and a commandlet ran against the closed project and reported 266 assets from its result file.
- It also settled the case this release exists for: **the editor was detected as holding the project 16 seconds before its MCP server finished binding its port.** For those 16 seconds an open editor answered nothing, which is what the old "no MCP answer means the project is free" rule would have read as an invitation to run a commandlet into it.
- Enabling the plugins is **not** enough to bind the route, and every place Forge said otherwise was wrong. `ShouldAutoStartServer()` honours `-ModelContextProtocolStartServer`, then falls back to `bAutoStartServer`, which is off by default. `README.md`, the project template's `mcp.json`, `route-registry.json` and the probe's own failure note now say so and name the three ways to start it, instead of leaving a correctly-configured editor unexplained.
- What that run did **not** establish is which change bound the route: the launch flag, the row-lookup fix and a hand-edited settings change all landed across the same set of runs. The corrected guidance rests on the engine source, where the default is unambiguous, not on the run. Recording this because a passing result whose cause is unknown is a weaker thing than it looks.

### A real engine can now be driven, and what remains unproven says so

- CI tested the factory controller well and never started the factory machinery: MCP against a stand-in server, the commandlet against a stub binary. Both prove the plumbing; neither proves Unreal.
- `tests/unreal/run_unreal_acceptance.ps1` builds a throwaway project, applies the overlay, launches a real editor and asserts what only a live engine can settle — the first-party MCP route answering a real `initialize`, an open editor detected as holding the project, the two editor lanes swapping as it opens and closes, and a commandlet running against the closed project and writing its result file. It runs on a workstation today; it does not need CI to be useful.
- `unreal-nightly.yml` runs the same driver on a self-hosted runner labelled `unreal`, gated on a repository variable so it **skips cleanly** rather than queueing forever on a repo with no such runner.
- Blueprint creation, compilation, PIE, actor-state readback and viewport capture now run for real, through `tests/unreal/mcp_client.py` — a small streamable-HTTP MCP client kept with the tests, because Forge itself only ever performs `initialize`: a probe needs to know whether a route answers, not to drive it. The full ladder is green against UE 5.8: **13 passed, 0 failed, 0 unproven.**
- Every tool name and argument shape was read off a live handshake rather than inferred, which is the only way to have learned three things that no documentation stated. The server answers on a keep-alive `text/event-stream` with no content length, which `urllib` reads as an empty body and `http.client` reads correctly. It applies **no schema defaults**, so a parameter the schema marks optional must still be supplied — `CaptureViewport` refuses once per missing argument until every one is passed. And `asset_type` wants a class object path, not a class name.
- The stages verify each toolset is still advertised before calling into it, and name their Blueprint per run. That second point came from colliding with an earlier probe: without it the stage fails on any second run against a project it has already touched, which would have read as a defect in the editor rather than in the test.
- The driver calls native binaries through one wrapper that captures stderr rather than obeying it. Windows PowerShell turns a native command's stderr into `ErrorRecord`s, and under `ErrorActionPreference = Stop` that makes any warning terminating — git's routine "LF will be replaced by CRLF" was enough to abort a run that had exited 0. Exit codes decide success here.

### `.forge` state has a version that means something

- `install-state.json` shipped `schema_version: 2` and **nothing read it** — a version number with no migration path behind it, on the one directory that accumulates months of a project's decisions. Upgrading Forge over an existing game was therefore an untested operation.
- `forge.py verify` now reports `state_version` as `CURRENT`, `MIGRATABLE` (older, with the migration notes that apply) or `NEWER`. `NEWER` fails the verdict: a `.forge` written by a later Forge knows things this build does not, and operating on it would silently drop them. Upgrade Forge instead. `forge-doctor` reads this before trusting anything else in the overlay.
- A guard requires every version below the current one to carry a migration note, so a bump cannot leave an upgrade nobody can perform, and another ties the number in the shipped template to the number in the code — they were never connected.

### Tagged versions become published releases

- Seven tags existed and none of them published anything. `.github/workflows/release.yml` cuts a GitHub Release from a `v*.*.*` tag, using that version's own `CHANGELOG.md` section as the body, and refuses to publish when the tag and `pyproject.toml` disagree or the suite is not green.

### Forge is a permission model, not a sandbox, and `SECURITY.md` now says so

- The control plane is carefully permission-aware — dry-run first, back up what is replaced, preserve unrelated entries, record consent, never change the machine implicitly. None of that is a security boundary, and the distinction matters most to anyone considering running Forge unattended, so it is stated rather than left to be inferred.
- `SECURITY.md` names what Forge contains and what it does not (process isolation, filesystem confinement, egress control, privilege separation), and gives the OS-level containment an autonomous production line needs. `unreal-operator`'s tool surface is deliberately **not** narrowed: it needs `Bash` to run commandlets and `Write` to author them, and `Bash` alone already reaches anything the account can reach — dropping the others would reduce the apparent surface without reducing the real authority.

### Admission is one decision, not four steps with seams between them

- Validating a packet, proving its routes were reachable, taking its leases and recording the transition were four commands an agent walked between. Each gap was somewhere a check could be skipped and the next step still reached, so the guarantee held only while the agent followed the workflow. Routing could also return `selected: resident` while a required capability had no viable route, leaving the final capability resolution to the agent.
- `forge.py dispatch` does all four as one decision. Nothing is acquired unless every check passed, and nothing is recorded unless it was acquired. `exec acquire` remains for taking leases alone.
- The recorded decision and the live contracts are checked **together**, at admission. A decision records what was reachable when routing ran; in between an editor can open or close and a server can stop answering. `route_unreachable` refuses a capability no route can serve right now; `route_decision_stale` refuses when what is reachable has drifted from what the decision was scored against.
- `.forge/state/work-orders.json` declared `forge.work-orders/v1` and no such schema shipped — a contract named with nothing to validate against. It ships now, and `dispatch --apply` writes the order transition through it.

### A silent editor is not a closed editor

- The editor-closed lane was entered whenever no MCP endpoint answered: "no live editor answered … so the project is free for editor-closed work". Silence is not absence. An editor that is open but whose MCP plugin is disabled, crashed, firewalled or simply frozen stops answering while still holding every file it has open — and a frozen editor is *exactly* when MCP goes quiet, so the most likely failure was also the undetected one. Forge would then let `UnrealEditor-Cmd` run against a project the live editor held, which is the corruption the super-lock exists to prevent.
- `live_editor_holds_project` now answers `HELD`, `FREE` or `UNDETERMINED` and carries the evidence for it. An MCP handshake is conclusive proof an editor is live and short-circuits everything else. Otherwise Forge looks for an Unreal editor process with this project's `.uproject` on its command line. Only a *positive* finding that nothing holds the project opens the lane.
- `UNDETERMINED` reports `UNAVAILABLE_BLOCKING` with a stated human action rather than a guess. A failed process check is a fault to resolve, not a condition to route around, and if it cannot be resolved the user decides — Forge does not, because the cost of being wrong is a commandlet writing into an open project. `forge-route-work` step 8 stops and asks.
- A mechanism that lists processes without their command lines cannot tell which project is held, so it reports `UNDETERMINED` too rather than answering from a process name alone.

### A lease is held by a process, not by a clock

- `LEASE_TTL_MINUTES = 120` with no way to renew meant a lane could be freed while its worker was still writing. A Nanite rebuild, a cook, a mass retarget or a large import legitimately outruns two hours; at the TTL the lease was marked `EXPIRED` and the next acquire admitted a second writer, which defeats the isolation the lease exists to provide.
- A lease now records `owner_pid`, `owner_machine` and `owner_process_start`, and recovery requires evidence the owner is gone rather than only a passed deadline. The start time is what makes this sound: over a two-hour window a pid can be recycled, and a bare pid check would read a recycled one as the original owner still working.
- `forge.py exec renew` extends a lease and stamps a heartbeat. A lease past expiry whose owner is still running **keeps its lane** and is reported as `renewal_overdue` by `exec status`, so a worker that stopped reporting is visible rather than silently holding forever. A lease taken on another machine cannot be checked from here, so it waits for `recoverable_after` instead of being freed on a guess.

### A resource Forge could not free is not a resource it reports as free

- `release` marked leases `RELEASED` even when `git lfs unlock` had failed, and said so in a note: "the lane is free but those paths are not". That is transparent about entering an inconsistent state rather than avoiding it, and it left Forge depending on the LFS server to rediscover the orphan later. The ordinary release path also called `git worktree remove` and `git branch -D` without checking either return code — the rollback path already reported these failures and the release path discarded them.
- Releasing is now `ACTIVE → RELEASING → RELEASED`, or `→ ORPHANED_EXTERNAL_LOCK` when an LFS lock or worktree survived. A quarantined lease keeps blocking its write scope, so the next writer is refused by Forge rather than by a remote server that happens to still say no.
- `forge.py exec reconcile` retries the outstanding teardown and frees the lane only if it works. It also recovers a lease left `RELEASING` by a crash — retrying an unlock is idempotent so it is safe, while discarding a workspace is not and an interrupted release never recorded the outcome that would have earned it, so a worktree is removed only when a release already named it as what it could not remove.
- Process inspection is one stdlib-only primitive in the executor with two independent mechanisms, because a failed inspection must be reportable as "cannot tell" rather than read as an empty machine.

## 0.5.0 - 2026-08-17

### Every verb is reachable from a workflow, and a guard keeps it that way

- `CommandSurfaceTests` proved every verb *runs*. Nothing proved any verb is ever *reached*, and seven were not: `route`, `verify`, `validate`, `profile`, `gsd-sync`, `mcp enable` and `mcp-status`. A verb no workflow invokes only rots, which is how `profile` stayed broken through an entire release — it was named in prose while every command around it was named by path.
- `WorkflowReachabilityTests` walks the same parser `CommandSurfaceTests` does and requires each leaf command to be invoked by some workflow or skill file, counting both the `forge.py <verb>` and `install.ps1 -Mode <Mode>` spellings and translating the latter through the same `$verbMap` `install.ps1` uses — the collapse this catches happens at translation, so checking the untranslated text would miss it. Exemptions are a dict of command to stated reason, and two further tests fail an exemption that names a command that no longer exists or one the prose already invokes.
- `verify` is now a step in `forge-doctor`: overlay drift makes every capability answer below it suspect, and it was surfaced only if a human thought to look.
- `profile` and `survey` are named by path in `forge-bootstrap` step 5, which said "Run Survey and Profile" as prose while naming fifteen state files exactly.
- `validate` runs in `forge-bootstrap` on the bootstrap report and job ledger, and in `forge-route-work` on the work packet before dispatch and on each attempt result before it is acted on. Its absence is *why* the shipped schemas were never exercised.
- `gsd-sync` appeared in no workflow at all, not even in prose. It is now the repair step in `forge-runtime` for a `runtime` key that drifted without a host swap.
- `mcp enable` is documented beside `disable`, and the pair is explained: disabling keeps the declaration, so re-adopting a route is `enable` rather than a second `add`.
- `mcp-status` stays deliberately unreachable, recorded with its reason: it is the retained spelling of `route-status`, and promoting both would offer one route under two names.

### The version this repo declares is the version it is

- Three files declare a version and all three said `0.2.0` while five tags existed through `v0.4.0` and the changelog held everything since 2026-08-14 under `Unreleased`. Anyone installing the plugin read `0.2.0` for three releases.
- `CHANGELOG.md` is cut into the releases that actually happened, each dated from its tag. Two were never written down and are recovered from their commits: `0.3.1`, the profile verb that failed on every invocation, and the operator agent's reach over the routes `0.4.1` made servable.
- `validate_repo.py` now fails when `pyproject.toml`, either `plugin.json`, and the newest `CHANGELOG.md` heading do not all state the same version. Declarations that drifted apart once will drift again.

### A routing decision is state the executor reads, not a file an agent carries

- `exec acquire --route` was optional, so the workflow telling the agent to pass it was compliance, not enforcement. It was worse than optional: **`forge.py route` was invoked by no workflow at all**. Step 10 of `forge-route-work` said "save the decision from step 6 and pass it", and step 6 never ran the command that produces a decision. There was no documented path that created the file the flag consumes, so in practice every packet was taken on trust.
- `forge.py route --apply` now records its decision in `.forge/state/route-decisions.json` under the canonical work order, against a new `forge.route-decisions/v1` contract that ships in the project template. Without `--apply` the decision is still a preview that writes nothing.
- `exec acquire` resolves the decision for the packet's own work order from that ledger. An agent that skipped routing cannot acquire by omitting a flag, because there is no flag to omit. `--route <path>` remains as an override for a decision held elsewhere; it replaces the lookup and never relaxes it.
- A work order with no recorded decision is refused as `route_decision_missing`. A decision older than `route_decision.freshness_minutes` in `route-policy.json` is refused as `route_decision_stale`: the two Unreal routes swap availability as the editor opens and closes, so a decision scored against a live editor names a lane that protects nothing once the editor is gone.
- A packet naming a registered alias resolved its decision and then failed that decision's own work-order check, because `route_conflicts` compared the raw id. The registry treats aliases as display compatibility, so one may not read as a different work order; the canonical id is what is compared now.
- The atomic-replace-under-mutex write that guarded the lease ledger is now `write_state_atomically`, and `StateMutex` takes the ledger it guards, so the decision ledger gets the same protection rather than a second implementation of it.

## 0.4.1 - 2026-08-17

### Routing decides what a packet must hold, and acquiring checks it

- `route_work` scored eligibility from `detected.json`, whose provider statuses come from survey's plugin-name heuristics, so it could refuse a route the live probe had just verified. It now resolves every required capability through the route contracts and overlays their status. A capability no route serves is not an error: the resident host or an engine prerequisite answers it, and the payload says so rather than failing closed.
- The decision names what it implies — `lanes`, `leases`, `isolation_mode`, and a `tool_access` row per capability. The mapping from capability to lease existed in the registry and reached nobody; a packet author had to transcribe it. `lane_warnings` reports a route implying a lane the request never declared, and a declared lane no bound route serves.
- `exec acquire --route <decision>` refuses a packet that declares fewer leases than routing resolved, weaker isolation than it requires, or any lane while tool access is degraded. Acquiring the weaker thing is worse than refusing, because no lease can detect afterwards that the work ran outside the protection routing decided it needed.
- A lease whose lane belongs to no exclusive group excluded nothing and said nothing. `exec acquire` and `exec status` now name the group each lease joined and list the lanes that joined none, so a misspelled lane reads as a misspelling rather than as protection.
- Project-local routes must spell their lane with the `lane.` prefix the registry's own rules require. A lane spelled any other way is not the lane the ledger enforces.

### The operator agent can reach the routes it is meant to operate

- Declaring the two new Unreal routes made three capabilities servable that no agent declared, and `forge-route-work` step 7 dispatches a capability only to an agent declaring it — routable and undispatchable at once. `unreal-operator` now declares all six UE capabilities, and its description and instructions are written around peer routes rather than a live editor with a fallback.
- The validator fails when a capability some route serves is declared by no agent, so a route can no longer be added without an agent that can be given the work.

## 0.4.0 - 2026-08-17

### All three Unreal routes exist, and the verb that reports them says so

- Declare VibeUE's live-Python route, the third of the three `COUNTERPLAN.md` separates. It shares `lane.ue-editor` with the first-party typed route because it runs inside the same editor process, and takes the `ue-live-python` lease the super-lock already declared. Declaring the route does not install it: it stays uncommitted until a project declares the server and the probe finds it, which is what "not a Forge prerequisite" means.
- `forge.py route-status` replaces `mcp-status`, which reported only the routes reachable by connecting to a server and would have hidden the two routes that are not. Its `routes` list now carries every kind with its lane, lease and reason, and the payload is `forge.route-status/v1`. The `mcp-status` spelling still works, so nothing that already calls it breaks.

### The editor-closed Unreal API is a route, not a fallback string

- `COUNTERPLAN.md` specifies three deliberately separate Unreal routes and calls the editor-closed API "a primary production surface, not just documentation" and "first-class rather than exceptional" — the first choice for batch import, retargeting, asset audits, LOD generation, null-RHI-safe work and anything unsafe inside the editor tick. The lease layer implemented that: `ue-editor-closed-api` has always been a peer inside `unreal-project-super-lock`. The route layer did not. `mcp-registry.json` held only `kind: mcp` rows, so `unreal-python` sat in the catalog as `routing: declared` with the note "No typed tool route declared yet", and `ue.python.commandlet` and `ue.batch` were capabilities no route could serve, no contract could describe, and `forge-route-work` step 7 could therefore never bind.
- The registry is now `dependencies/route-registry.json` and admits any kind of route: `mcp` names a server the host connects to, `process` names a command it runs. Nothing else varies by kind, so both are probed, scored, leased and reported the same way. `mcp-provider` becomes `route-provider`, with the required reach field chosen by kind.
- `unreal-python` is a routed peer on its own lane, `lane.ue-editor-closed`. The `lane.ue-editor` description no longer claims editor-closed commandlets contend for the live lane; they contend for the project, which is what the super-lock already expressed.
- Add the `ue-commandlet-ready` probe. Readiness is the inverse of `mcp-http-handshake`: the engine command must resolve *and* the editor's MCP endpoint must be silent, because a commandlet must not run against a project the live editor holds. The two Unreal routes now swap availability as the editor opens and closes, and a test asserts they are never both available for one project.
- Route rows name the `lease` they take, and the validator refuses a lease no exclusive group declares. The registry said `lane.ue-editor` while the ledger that enforces exclusion said `ue-live-native-mcp`; two vocabularies that happened to agree now agree by rule.
- `route-policy.json` gains `unreal_routing`, which says which work shape belongs to which lane and records that the result file, never the exit code alone, is authoritative for editor-closed work. `forge-route-work` gains a step that picks the route by the shape of the work rather than by what happens to be running.

### The bootstrap job ledger is wired to the resume it exists for

- `.forge/state/install-jobs.json` was mandated before dispatch by step 6 and read by nothing. Step 4 enumerated what `--resume` reads and did not name it, so the ledger written to survive bootstrap's two stop points was not read by the resume those stops require. Step 4 now reads it and carries forward every job already `COMPLETE`, `NOT_APPLICABLE` or `FAILED`, re-dispatching only what is still `PLANNED` or was left `DISPATCHED`.
- The ledger ships in the project template and has a contract, `forge.install-jobs/v1`, with a `status` vocabulary the resume can act on. It was the only bootstrap state file with neither.
- Name the phase activation policy by path in `forge-capability-admin` and `forge-route-work`. Both told the agent to load "the phase activation policy" while naming fourteen other state files by exact path, leaving the agent to guess that it meant `.forge/context/activation-policy.json`.

### Re-profiling the same machine no longer proposes a change to it

- `forge.py profile --apply` wrote a `.forge-proposed` sibling on every run against an installed project, because the stored profile records the literal `--project` argument and that literal was compared. `install` resolves the path before profiling and an agent typically passes `.`, so the two never matched. The gate treats a proposal as a human merge decision, so the noise arrived exactly where bootstrap tells the agent to run Profile.
- `stable_profile` now drops the invocation record alongside the timestamp it already dropped. `requested` stays in the file as provenance; it can no longer cause a proposal.

### `forge-next` stops offering choices that are not choices

- Two situations offered a recommended Forge verb and, as the alternative, a GSD verb the registry fronts with that same Forge verb. On a greenfield project `forge-init` and `project-discovery` both rendered as `/forge-init`, and on unreadable GSD state `doctor` and `planning-health` both rendered as `/forge-doctor`. Distinct ids hid it: the collapse happens at translation, after the ids are assigned.
- Greenfield now offers `forge-doctor` as its alternative, which is a different action. The unfronted GSD path is not lost: `gsd_snapshot` already lists `/gsd:new-project` untranslated, which is where a user who wants stock GSD should find it.
- A test renders every action block's commands through the same translation the payload uses and fails when two ids land on one verb.

## 0.3.1 - 2026-08-17

### The profile verb worked again, and every verb got exercised

- `forge.py profile` failed on **every** invocation since the result contract landed in `bfc7630`: `write_profile` never returned a `schema` key and the contract assertion rejected the payload. It hid because `install_overlay` calls `write_profile` directly, bypassing `main()`, so the only path that exercised it was the one that skipped the check.
- `CommandSurfaceTests` drives every leaf command the parser declares through `main()`, and fails when a declared command has no invocation. A verb cannot be shipped unexercised, so that class of rot cannot recur.

## 0.3.0 - 2026-08-16

### One module per concern, cut where the code already separated

- Split `forge.py` into ten modules. It had grown to 2,558 lines carrying the failure contract, host registry, MCP routes, GSD front, capability survey, lifecycle, installer, routing and the CLI, so every one of those concerns was read and edited through the same file.
- The cut follows the call graph rather than a guess. Three names had to move first: `capability` was used only by the MCP layer and the survey that defined it, and the overlay's path helpers were used by both the host renderer and the installer, so both belong to `forge_core`. `host_set`, `host_status` and `host_list` are called only by the CLI and sat between the host registry and the GSD sync that depends on it, so they became `forge_runtime`. With those moved the layering is acyclic, and a test asserts it stays that way.
- `forge.py` keeps every public name, so `forge.<verb>` resolves exactly as before and the split changes no behaviour. A test walks each module with `symtable` and fails on any name a module references but never defines or imports, which is the check that would otherwise wait for a rare path to raise `NameError`.
- `forge_executor.py` imports nothing from the rest, and a test holds it there. The transactional core does not depend on the layers above it.

## 0.2.0 - 2026-08-16

### Isolation is enforced by the runtime, not by workflow compliance

- Add `scripts/forge_executor.py` and the `forge.py exec acquire|release|status` verbs. Leases, Git worktrees and `git lfs lock` were described in `forge-route-work` and `directives.md` and implemented nowhere: the words "lease", "worktree" and "lfs" did not appear in `forge.py`, and `.forge/state/leases.json` shipped an `exclusive_groups` map nothing read or wrote. A guarantee that depends on an agent following prose is not a guarantee.
- `exec acquire` resolves the base revision, refuses a lane already held or held in the same exclusive group, creates the worktree, takes each LFS lock, and rolls back every completed step when a later one fails. A lock it cannot take never becomes a lease it appears to hold.
- The ledger is written atomically under a cross-process mutex, so two workers racing one lane produce a holder and a refusal rather than two writers. A test races two real processes and asserts exactly one wins with `lease_conflict`.
- `exec acquire` expires leases past `expires_at` before checking conflicts, so a crashed session blocks its lane until expiry rather than forever.
- `forge-route-work` steps 8, 9 and 15 call the executor instead of instructing the agent to take isolation by hand. Step 8 declares isolation, step 9 establishes it, and nothing else may.
- Test the LFS path against real `git lfs` by running a Git LFS locking server in the suite. A path another writer holds is refused by git, a partly-locked set is unlocked again on rollback, and `release` reports the paths it could not unlock instead of freeing the lane silently and leaving them held.
- Report incomplete rollback. An undo step that fails now attaches `rollback_incomplete` to the failure, because a lock left behind that Forge is no longer tracking is worse than the error that caused it.

### Unreal's first-party MCP is the shipped route

- Point `unreal-native-mcp` at Unreal Engine's own Unreal MCP plugin (`ModelContextProtocol` plus `AllToolsets`, Experimental since 5.8), which advertises itself as `unreal-mcp` — the server id the registry already named. The editor hosts it; Forge never starts it.
- Support http transports. The renderer emitted `command`/`args`/`env` only, so an editor-hosted endpoint could not be expressed at all. `mcp add` now takes `--url`, and refuses a declaration naming both a command and a url.
- A new project's `.forge/mcp.json` declares that route instead of shipping `servers: []`, so the layer that decides whether Unreal work is possible is no longer left for the user to choose.
- Add the `mcp-http-handshake` probe kind: it sends a real MCP `initialize` to the declared endpoint. Passing earns `AVAILABLE_VERIFIED`, which a configuration file alone never did. Failing marks the route `UNAVAILABLE_OPTIONAL`, so work degrades to `ue.editor-closed-or-human` instead of dispatching into a closed editor.
- Test that path against a server that answers `initialize`, over JSON and over the SSE framing the first-party plugin uses. A port that is listening without speaking MCP does not earn a route, and a live server the host's configuration does not declare is reported as undeclared rather than as available.

### Resume as a first-class verb

- Add `forge-resume-work`, fronting `gsd-resume-work`. Resuming was previously reachable only as `forge-handoff --resume`, which hid a daily command behind a flag on a verb named for pausing. `forge-handoff` now pauses only, and smart-entry's `gsd-resume-work` emission translates to `/forge-resume-work`.
- Resuming reclaims lane leases before work restarts and re-probes qualification when the handoff was produced under a different host.

### Correctness

- Fix `mcp-status` routes overwriting the declared scope with the probe's. Both are reported: `scope` is what the project declared (`project`/`user`/`both`), `found_in_scope` is where the probe found the server. Consumers reading `scope` were reading the probe result.
- Fix `mcp amend` writing an unroutable declaration to disk and only then failing to resolve it, which left `.forge/mcp.json` in a state the next command refused. The amendment now resolves before anything is written.

### Skills follow GSD's architecture

- Split every skill into a launcher and a workflow, the way GSD does. `skills/<verb>/SKILL.md` carries `<invocation>`, `<objective>`, `<flags>`, `<execution_context>`, `<context>` and `<process>`; the steps live in `workflows/<verb>.md` and load by path. Descriptions are one line under 110 characters, saying what the verb does — the "Use when …" trailer moved into `<objective>`.
- `<execution_context>` lists every file a verb loads, which closed a silent gap: `forge-discuss-phase` fronts four GSD workflows and named one, `forge-milestone` fronts five and named one, `forge-review` fronts five and named four.
- Declare flags where the agent reads them, with GSD's rule that a flag is active only when its literal token appears in `{{FORGE_ARGS}}`. `forge-discuss-phase --assumptions/--power/--list-assumptions` and `forge-plan-phase --dependencies` were documented publicly and absent from the skill.
- Every line of a workflow is now a step. Justification clauses, restated rationale, and one reference to a past incident are gone or have become instructions.

### Forge runs GSD's workflows instead of containing them

- Replace the `contain` delegation mode with `run`. It spawned a subagent whose only job was reading a workflow file whose path the registry already declares, which then spawned GSD's real agents — three layers where GSD itself uses two. Forge now loads the workflow from disk and runs it end to end in the current session, with its own PRE before and POST after. GSD's typed agents still spawn as its workflow directs.
- Delete `forge-execute-phase`. Its PRE restated `forge-route-work` steps 7–9 and its POST restated step 15, and its own PRE ended by routing through `forge-route-work` anyway. `gsd-execute-phase` now fronts `forge-route-work`, which gained clean-base verification and a step that runs GSD's executor under the leases it already holds.
- `forge-resume-work` now treats an `ACTIVE` lease past its `expires_at` as stale. The schema has always required that field and nothing read it, so a lease held by a dead session was indistinguishable from a live one.
- Distinguish `forge-docs-update` from `forge-ingest-docs` in both objectives. They read as duplicates because both touch the GDD ledger; they run in opposite directions — ingest takes documents into planning state, docs-update takes implemented code out to documentation.

### Promises closed

- Declare `forge-quality-gate --tests` and `forge-ship --pr` in their skills. Both appeared in the verb registry and the independence map, and in neither `<flags>` block, so an agent executing the skill could not act on them.
- Take the real `git lfs lock` on a declared binary write scope where LFS is configured, so a second writer is refused by git rather than by convention. Where it is not configured, the recorded lease stays the only protection and the attempt result now says so.
- Stop advertising `forge-explore` and `forge-capture`. Five GSD commands were dropped with the reason "Planned: …" against verbs that do not exist. Greybox and blockout belong to `forge-visual-production`; Socratic ideation, spikes, idea capture and backlog triage are not production surface, and each drop reason now says to run the GSD command directly.

### Forge fronts GSD; it does not replace it

- Correct a claim that was never true of the product: the docs said "GSD is never addressed directly — you will not type a `gsd-` verb". Both surfaces are installed and GSD stays directly usable. The instruction file Forge renders has always pointed at `gsd-quick` and `gsd-debug` for small fixes, so the code and the documentation disagreed.
- Reframe the rule to what it actually is: a Forge verb exists where the game side needs work the bare GSD command does not do — lane leases, the acceptance registry, canonical packet IDs, in-engine evidence — so a **routed** action is a Forge verb. That is a statement about what Forge emits, not a restriction on the user.
- Stop treating a `drop` as something the user cannot run. `forge-next` now reports each suppressed action with `run_directly`, the command spelled for the assigned host, and `forge-next` presents them as available in GSD. Added a reference table of the 29 commands Forge does not route, with reasons.

### Documentation

- Rebuild `README.md` as a landing page — what Forge is, how it works, a quickstart, and an index — instead of a 500-line manual. Everything it used to carry now lives in `docs/`, organised as tutorials, how-to guides, reference, and explanation, with `docs/README.md` as the index.
- Add [Your first game](docs/tutorials/your-first-game.md), [Adopt an existing project](docs/tutorials/adopt-an-existing-project.md), [Install Forge](docs/how-to/install-forge.md), [Swap the resident runtime](docs/how-to/swap-runtime-host.md), [Troubleshoot](docs/how-to/troubleshoot.md), [Skills](docs/reference/skills.md), [Installer](docs/reference/installer.md), [Repository and project layout](docs/reference/repository-layout.md), and [How Forge works](docs/explanation/how-forge-works.md).

### Comments and skill prose

- Remove every comment from `forge.py`, `validate_repo.py`, `test_forge.py`, and `install.ps1` (−350 lines). Rules moved to the skill step, doc, or registry that owns them; explanations became named values, extracted functions, or failure messages; history stayed in git.
- Record the rule in `CONTRIBUTING.md` and enforce it in `validate_repo.py`, which now fails on any comment in those four files apart from shebangs and tool pragmas.
- Cut the same class of prose from 18 `SKILL.md` files: justification clauses, restated rationale, and one reference to a past incident. A skill states what to do and what is refused, not why the rule was written.

### Host-agnostic runtime

- Make the resident AI runtime a **swappable assignment** rather than a hardcoded vendor. A project records its host in `.forge/runtime.json` and can change it at any stage — including mid-phase and at a resume boundary — without losing planning state, packets, or evidence.
- Add `plugins/forge-ue-studio/hosts/registry.json`: host profiles plus a required/optional prerequisite contract. Built-in hosts are `claude` (Claude Code, default), `codex` (OpenAI Codex CLI), and `generic`. A new host is added by appending a profile; no Forge code changes are required.
- Split the project overlay into **canon** (host-neutral, authoritative) and **rendered surfaces** (host-specific, disposable). Canonical studio-role agents now live in `.forge/agents/*.json` and the project instruction file is generated from `.forge/templates/project-instructions.md`.
- Render host surfaces per assignment: `CLAUDE.md` + `.claude/agents/*.md` for Claude Code, `AGENTS.md` + `.codex/agents/*.toml` for Codex. Swapping away and back is byte-identical.
- Add `forge-runtime`, a skill for inspecting, assigning, and swapping the resident host, and `forge.py host list|status|set` behind `install.ps1 -Mode Host`.
- Spell skill invocations per host (`/forge-next` in Claude Code, `$forge-next` in Codex). Forge Next returns commands already spelled for the assigned host.
- Detect every known host in the survey, not just the active one, so a swap can be planned from evidence. Detection never grants the resident seat.
- Add the `host-surfaces-stale` smart-entry situation so Forge Next refuses to proceed against stale instructions or agents.
- Treat provider qualification evidence as **host-scoped**. An evaluation recorded under a different host is rejected as ineligible with an explicit re-probe reason.
- Replace the literal `codex` resident provider with the neutral `resident` role across route policy, project config, capability registry, and dependency catalog.
- Add `host-profile` and `runtime-state` schemas, and extend repository validation to reject duplicate skill prefixes, unsupported agent formats, hosts that cannot meet the contract, host-specific files shipped in the project template, and canon that hardcodes a host spelling.
- Add the Claude Code plugin manifest and repo-local marketplace alongside the existing Codex ones.
- Add [docs/host-runtimes.md](docs/host-runtimes.md) covering the prerequisite contract, canon/rendered split, swap semantics, and how to add a host.

### Neutrality audit follow-ups

- Fix `install.ps1` rejecting newly registered hosts: `-RuntimeHost` had a hardcoded `ValidateSet` that failed parameter binding before the registry was read, contradicting the documented "append a profile, no code changes" path. Validation is now registry-driven, with an argument completer for tab-completion.
- Remove vendor names from four canon files that the old guard could not see: the template capability registry provider id and activation list, the activation policy `always_on` entry, the acceptance-suite purpose, and a duplicated host list in the dependency catalog.
- Replace the narrow neutrality check — four skill prefixes inside `.forge/agents/*.json` — with a guard over all of `assets/project-template/`, `dependencies/*.json`, and `schemas/*.json`, banning vendor names, host home directories, host instruction filenames, host agent directories, and host skill invocations. Banned tokens derive from the registry, so the guard extends itself as hosts are added.
- Stop skill prose instructing agents to read `AGENTS.md`, which does not exist under the default host. Bootstrap and Init now refer to the instruction file named by the active host profile.
- Re-word ~20 prose assertions in SKILL.md, `references/*.md`, and `docs/installation-agent-jobs.md` that still named a vendor as the resident worker.
- Make bare skill names the canonical internal form in `forge.py`, and change the missing-profile prefix fallback from `$` to none, so a forgotten profile degrades neutrally instead of emitting another host's spelling.
- Fix a deprecation error message that hardcoded `$forge-next`, and correct stale `pyproject.toml` metadata (`0.1.0`, "Codex-native") to match the manifests.

### Forge owns the verb surface; GSD becomes an invoked sublayer

- Add `verbs/registry.json`: every GSD command maps to the Forge verb that fronts it, with a declared delegation mode (`contain` / `relay` / `native`), the GSD workflow it calls, and the game-dev adaptation applied. Validation refuses a verb with no matching skill, an unknown mode, or a duplicate GSD mapping.
- Translate GSD commands into Forge vocabulary at the one boundary where they surface. `normalize_gsd_command()` maps `gsd-*` to its Forge verb, then spells it for the active host. An unmapped GSD verb emits an explicit `[UNMAPPED: …]` marker rather than leaking silently.
- Add 17 skills: `forge-review` (verb-based — plan, `--code`, `--security`, `--audit` — graded against Forge's acceptance registry rather than generic criteria) plus `forge-discuss-phase`, `forge-plan-phase`, `forge-execute-phase`, `forge-verify-work`, `forge-progress`, `forge-phase`, `forge-milestone`, `forge-onboard`, `forge-ingest-docs`, `forge-map-codebase`, `forge-docs-update`, `forge-spec-phase`, `forge-debug`, `forge-handoff`, `forge-ship`, `forge-undo`.
- Add `references/delegation-contract.md` defining the shared PRE (Forge) / CORE (stock GSD) / POST (Forge) shape. GSD is invoked in place — never edited, never copied — so upstream fixes arrive without a merge.
- Tell GSD which host it is running under. GSD resolves its command spelling from `.planning/config.json`'s `runtime` key and defaults to `claude`, so a Codex-hosted project previously got the wrong spelling. `sync_gsd_runtime()` writes that one key at overlay install and on every host swap, and `GSD_RUNTIME` is exported on every `gsd_run` call. Repairable with `forge.py gsd-sync`.
- Move the GSD pin from 1.8.0 to **1.9.1**, the version actually installed and tested against. 1.10.0 exists but is unvalidated.

### Bootstrap gate and dead-code removal

- Make Forge's bootstrap closure checks **reachable**. They previously lived in `require_artifacts()`, which only the unreachable lifecycle-transition block called, so nothing ran them. They are now `bootstrap_verdict()`, wired into `bootstrap_is_complete()` (and therefore Forge Next) and exposed as `forge.py bootstrap-check` / `install.ps1 -Mode BootstrapCheck`, which exits non-zero until every check passes.
- The gate verifies the capability profile exists, the report parses and carries every required `forge.bootstrap-report/v1` field, the verdict is closable, no blocking items remain, every canonical `FI-*` packet is accounted for, and the rendered instruction file actually contains `## Forge phase contract`. These are Forge's own domain — GSD owns phase state and has no equivalent — so nothing downstream catches them.
- Surface partial phase execution in Forge Next as advisory `warnings` plus per-phase `execution_coverage`. GSD computes the same set but keeps it non-blocking, so an interrupted phase can reach 100% silently. Forge reports it without raising a competing gate; the routed action is unchanged.
- Delete `require_artifacts()` and the unreachable lifecycle-transition block, plus the now-unused `LIFECYCLE_EVENTS` constant. `lifecycle_state()` keeps only its read-only status path and still rejects transitions. Its `phase` and `apply` parameters are removed — they were inert.
- Retain GSD's verification gate as the authority for phase completion. Its `readVerificationStatus` / UAT predicate is stricter than Forge's old UAT regex (it requires positive passing evidence and refuses a vacuous pass), so no Forge equivalent was reintroduced.

### Earlier in this cycle

- Add `forge-next`, a state-aware front door that combines Forge adoption/bootstrap readiness with GSD `smart-entry`, dispatches one action, and stops.
- Make GSD `.planning` the sole phase authority; deprecate Forge lifecycle transitions and retain the old lifecycle file as compatibility history only.
- Make Forge Init invoke the detector first, so re-running it in a partial project routes to bootstrap, document ingestion, onboarding, or the exact active GSD action instead of restarting inception.
- Allow the Forge project overlay to install before a `.uproject` exists, eliminating the new-game bootstrap deadlock.
- Add `forge-bootstrap` with explicit delegated installation waves, independent verification, persisted reports, and visible degraded-inline fallback.
- Add project `AGENTS.md`, compatibility state, canonical packet registry, and route rejection for unknown/relabelled work orders.
- Stop Forge Init after inception and use Forge Next/GSD smart-entry for the next command instead of hardcoding phase 1 or dispatching the first implementation packet in the same task.
- Add a separate preview-first, stable-version-pinned GSD Core installer plus runtime/skill/agent detection and fresh-session qualification guidance.
- Rewrite the README as an end-user installation, first-use, skill, project-adoption, capability, and troubleshooting guide.
- Make the resident host the default across art, code, review and tool-operation seats.
- Remove the named model-provider routes and replace provider-specific cost assumptions with evidence-backed, provider-neutral local and remote worker registration.
- Add bounded-context offload rules for long extraction, code/review, image-to-3D breakdown and DCC work.
- Adopt typed capability trust/consent/integrity, phase-scoped activation, exact task/complexity qualification and deterministic route decisions.
- Add plan convergence, quality gate, retrospective/forensics, gameplay gauntlet and capability-administration skills.
- Add attempt, evaluation, review, learning, lease, route and research schemas plus persistent project registries.
- Extend installation with a non-destructive detected capability profile and contract validation/profile/route commands.
- Enforce clean-base Git worktree isolation for concurrent text/code workers, binary ownership for Unreal assets, and canonical-JSON production scorecards with optional XLSX/CSV views.

## 0.1.0 - 2026-08-14

- Add the Codex plugin, repo-local marketplace, five studio skills, environment doctor, project overlay installer, capability catalog, routing policy, schemas, tests, and CI.
- Define cost-aware local routing after quality and safety qualification.
- Treat Blender and Unreal as alternate or split asset, rigging, and animation routes.
