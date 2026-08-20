<!-- forge:workflow
name: verify-work
consumes: .forge/acceptance/registry.json, .forge/config.json (human_gates), the running build, plugins/forge-ue-studio/doctrine/procedures.json
produces: UAT results with in-engine evidence and explicit residual risk
-->

# Forge Verify Work — workflow

<purpose>
Decide whether a phase actually delivered, by playing it — not by reading that its plans completed.
</purpose>

<core_principle>
A green build and green tests are not a verified game phase. Feel and presentation are human gates
and stay human gates.
</core_principle>

<process>

<step name="load_the_registered_suites" priority="first">
Read `.forge/acceptance/registry.json` and grade against the suites registered for this phase, never
against a generic definition of done.

A phase whose acceptance was never registered cannot be verified here. Say so and route back to
`forge-plan-phase`; inventing criteria at verification time grades the work against whatever the
verifier happened to expect.

Read `human_gates` in `.forge/config.json` — `game-mandate`, `primary-visual-direction`,
`subjective-art`, `game-feel`, `release`. Any of these touched by this phase needs a signature, and
this workflow cannot supply one.
</step>

<step name="read_the_evidence_doctrine">
Read what evidence this shape of work owes, rather than deciding it here:

```powershell
python <forge-plugin-root>/scripts/forge.py procedure --task-class <task-class>
```

`evidence` on the procedure is the list. For live verification the class is `pie-verification`, whose
capabilities are `ue.pie` and `ue.viewport`. A `null` procedure means no doctrine covers this shape —
say the phase was verified undoctrined rather than pretending the list was authoritative.

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *The procedure layer*
</step>

<step name="take_the_lane_the_evidence_needs">
Producing PIE and viewport evidence means driving the live editor, which is exclusive with every
editor-closed route:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-verify-work --lane ue-live-native-mcp --apply
```

Use `--lane human-editor` instead when a person is playing the build rather than an agent driving it;
use `--lane ue-live-python` for the VibeUE route. For a UAT session run entirely against a packaged
build, name no `--lane` — `holds_no_lane` is recorded, and it is true.

A `blocked` answer means a cook or a batch pass has the project. Verification measured against a
project someone is rewriting is not verification.

> **Why:** CHANGELOG.md 0.7.0 § *Lane supervision is reachable from any workflow, not only from the one that dispatches*
</step>

<step name="run_gsd_uat">
Relay GSD's UAT session. It owns the conversational pass/fail predicate — never weaken it, duplicate
it, or re-derive it.
</step>

<step name="require_in_engine_evidence">
A passing UAT is necessary and not sufficient. Require at least one of these on top of it, captured
under fixed conditions — same camera, same input, same content, same hardware:

- A PIE session outcome for the affected loop.
- Fixed-condition frame captures showing the change at gameplay distance, not in an asset viewer.
- A recorded playthrough of the affected loop.

An asset that reads correctly in the content browser and not at gameplay distance has failed, and only
the third kind of evidence catches it.
</step>

<step name="release_and_record" priority="last">
Release the lane, including on a failed verification:

```powershell
python <forge-plugin-root>/scripts/forge.py exec release --project <project-root> --work-order <id> --outcome passed|failed --apply
```

Then record, explicitly and separately:

| Recorded | Not to be merged with |
|---|---|
| Which registered suites passed, with the evidence for each | Which passed without fresh evidence |
| Which human gates were signed, and by whom | Which are outstanding |
| Residual risk | The verdict |

Never close a subjective gate on the human's behalf. Report on it and leave it open.

On a failure, route the next action through `forge-route-work` or `forge-retrospective` rather than
fixing it here — a verifier that repairs its own finding is no longer independent.
</step>

</process>
