# Delegation contract

How every Forge verb that fronts a GSD workflow behaves. Read this once; the individual skills assume it.

## The rule

**Forge owns the vocabulary. GSD owns `.planning`. GSD is invoked in place, never edited and never copied.**

That last clause is the point. Copying GSD's workflow prose into Forge would freeze it at the version copied, and GSD ships roughly a minor release a week. Forge reads the workflow that is on disk right now, so upstream fixes arrive without a merge.

## Three delegation modes

Declared per verb in `verbs/registry.json`.

### `contain` — default

Spawn a subagent. Instruct it to read and follow the stock GSD workflow at `<gsd-core>/workflows/<file>`, calling `gsd_run` verbs as that workflow directs. Require a **structured result**, not prose.

The subagent's transcript never reaches the user. This is what makes containment work: GSD's own `gsd-…` command strings exist only inside the agent, so there is nothing to filter and nothing can leak.

Ask the subagent for an action **identifier** (`execute-phase`), never a command string (`/gsd-execute-phase`). Forge renders the command itself.

### `relay` — interactive workflows

Some workflows must reach the user — `discuss-phase` above all. Containment would swallow the questions.

Relay instead: surface each question, reframe it in game-dev terms, pass the answer back down. Forge controls presentation at every turn, so vocabulary stays Forge's. This is more plumbing and it is where Forge adds the most value, because GSD's generic prompts are the least suited to a game project.

### `native`

Forge owns the behaviour outright; no GSD workflow is involved. Used where Forge's version is already stronger — capability qualification, visual production, the gameplay gauntlet, runtime assignment.

## The shape of every delegating verb

```
PRE    Forge   capability qualification, Unreal write-lock / lane lease,
               canonical packet ID, game-dev framing of the request
CORE   GSD     the stock workflow, unmodified, via contain or relay
POST   Forge   acceptance registry, evidence contract, in-engine verification,
               then present the outcome in Forge vocabulary
```

PRE and POST are Forge's. CORE is untouched upstream. If a game concern cannot be expressed in PRE or POST — because it must be *held across* GSD's steps, like the Unreal write-lock — acquire it in PRE and release it in POST, and say so in the skill.

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
