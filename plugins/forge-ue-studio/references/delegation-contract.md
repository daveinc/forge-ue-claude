# Delegation contract

How every Forge verb that fronts a GSD workflow behaves. Read this once; the individual skills assume it.

## The rule

**Forge owns build doctrine. GSD owns planning artifacts. GSD is invoked in place, never edited and never copied.**

Two different things get called planning, and only the second is GSD's.

**Planning artifacts** are `.planning/` — ROADMAP.md, PLAN.md, SUMMARY.md, phase IDs, status transitions, the schedule. GSD writes every one of them, always through `gsd_run`. Forge reads that state through `smart-entry` and never writes it; two writers is the failure this architecture exists to prevent.

**Build doctrine** is what a game of this kind needs built, in what order, with which capabilities and tools, and what evidence closes a step. That is Unreal domain procedure, GSD has no reason to hold it, and Forge supplies it as content: GSD schedules and records the phase, Forge says what a phase of this kind consists of. It lives as data in the plugin — see [build doctrine](../../../docs/explanation/build-doctrine.md) for the boundary and the procedure layer's shape.

Read as "Forge does no planning", the old wording left doctrine homeless, and a verb with nothing of its own to contribute could only wrap a GSD call. `forge-onboard`'s CORE is one line reading *Run GSD's onboarding* for exactly that reason.

The last clause is separate and stands unchanged. Copying GSD's workflow prose into Forge would freeze it at the version copied, and GSD ships roughly a minor release a week. Forge reads the workflow that is on disk right now, so upstream fixes arrive without a merge.

None of this narrows what you may run. A verb Forge routes is spelled as a Forge verb because it is the GSD workflow plus the game-specific PRE and POST below; the user remains free to call GSD directly, and Forge neither hides nor disables it.

## Three delegation modes

Declared per verb in `verbs/registry.json`.

### `run` — default

Load the stock GSD workflow from `<gsd-core>/workflows/<file>` and run it end to end in this session, calling `gsd_run` verbs as that workflow directs. Require a **structured result**, not prose. GSD's own typed agents still spawn as its workflow directs — Forge adds no agent of its own.

The workflow's own command strings never become the action Forge routes, so a routed action always carries Forge's PRE and POST.

Take an action **identifier** (`execute-phase`) from the workflow, never a command string (`/gsd-execute-phase`). Forge renders the command itself.

### `relay` — interactive workflows

Some workflows must reach the user — `discuss-phase` above all. Running one end to end would swallow the questions.

Relay instead: surface each question, reframe it in game-dev terms, pass the answer back down. Forge controls presentation at every turn. This is more plumbing and it is where Forge adds the most value, because GSD's generic prompts are the least suited to a game project.

### `native`

Forge owns the behaviour outright; no GSD workflow is involved. Used where Forge's version is already stronger — capability qualification, visual production, the gameplay gauntlet, runtime assignment.

## The shape of every delegating verb

```
PRE    Forge   build doctrine for the task class, capability qualification,
               Unreal write-lock / lane lease, canonical packet ID,
               game-dev framing of the request
CORE   GSD     the stock workflow, unmodified, via run or relay
POST   Forge   acceptance registry, evidence contract, in-engine verification,
               then present the outcome in Forge vocabulary
```

PRE and POST are Forge's. CORE is untouched upstream. If a game concern cannot be expressed in PRE or POST — because it must be *held across* GSD's steps, like the Unreal write-lock — acquire it in PRE and release it in POST, and say so in the skill.

## Entry points versus internal steps

GSD's workflows chain — by command name and by file reference — and several load nested step files. Measured against GSD 1.10.0: **91 workflow files plus 62 nested step and mode files; Forge enters 45 of them; the rest are reached as internal steps.**

Examples of internal chaining Forge must never interfere with:

| Internal step | Reached from | Via |
|---|---|---|
| `execute-plan.md` → `node-repair.md` | `execute-phase.md` | file |
| `code-review-fix.md`, `verify-phase.md` | `code-review.md` | file |
| `diagnose-issues.md` | `verify-work.md` | file |
| `graduation.md`, `transition.md` | `new-milestone.md`, `extract-learnings.md` | cmd/file |
| `execute-phase/steps/*` — drift, isolation, worktree, post-merge, regression gates | `execute-phase.md` | nested |
| `discuss-phase/modes/*` — advisor, analyze, power, batch, chain | `discuss-phase.md` | nested |

**These are not Forge's business and must not be registered, translated, or suppressed.** Forge runs GSD's workflow from disk, so the whole chain executes as upstream intended. The verb registry governs only two things: which Forge verbs exist, and how GSD's *terminal* action list from `smart-entry` is presented. It has no reach inside a running workflow.

A `drop` disposition therefore does **not** disable a GSD workflow. It only means "Forge does not offer this as a command you type." The workflow still runs whenever GSD's own chain reaches it.

## Never do these

- **Never show a `gsd-` name to the user.** If one appears, the verb registry has a gap. Fix the registry, do not hand-edit the string.
- **Never write `.planning` directly.** Always through `gsd_run`. GSD is the phase authority; two writers is the failure this architecture exists to prevent.
- **Never edit `~/.claude/gsd-core` or copy its workflows into Forge.** Both forfeit upstream fixes.
- **Never let a delegated subagent talk to the user.** Its output is a result for Forge to interpret.

## Command rendering

`forge.py` translates and spells every command. `normalize_gsd_command()` maps a GSD command to the Forge verb that fronts it, then applies the active host's prefix — `/forge-plan-phase` on Claude Code, `$forge-plan-phase` on Codex. An unmapped GSD verb is emitted with an explicit `[UNMAPPED: …]` marker rather than passed through silently.

## Telling GSD which host it is under

GSD resolves its own command spelling from `.planning/config.json`'s `runtime` key, defaulting to `claude`. Forge assigns the host, so Forge writes that key — at overlay install and again on every host swap, via `sync_gsd_runtime()`. Forge touches only that one key.

Repair it manually with:

```powershell
python <forge-plugin-root>/scripts/forge.py gsd-sync --project <project-root> --apply
```
