<!-- forge:workflow
name: ship
consumes: .planning/ verification results, .forge/acceptance/registry.json, .forge/state/work-orders.json, <project>.uproject
produces: a PR (GSD's), and a packaged build recorded with its provenance and engine version
-->

# Forge Ship — workflow

<purpose>
Turn a verified milestone into something that actually runs on the target platform, and record what
produced it.
</purpose>

<core_principle>
A merged PR is not a shipped game. The cook is the first step that exercises the whole content set,
so it is the first step that can fail on content nothing else touched.
</core_principle>

<process>

<step name="refuse_an_unverified_milestone" priority="first">
Confirm every phase in the milestone passed verification, and read
`.forge/state/work-orders.json` for orders that never closed. An order at `DISPATCHED` is work still
in flight; an order at `BLOCKED` names a lane and a `human_action` still outstanding.

Refuse to ship over either. Shipping is the one operation that makes an unfinished order permanent.

Check the acceptance suites in `.forge/acceptance/registry.json` have current evidence rather than
evidence recorded before the last change.
</step>

<step name="run_gsd_ship">
Relay GSD's ship workflow for the review and PR mechanics. It owns the branch, the PR body and the
review request.

**Skip if:** the invocation is `--pr` — then run `pr-branch.md` alone, and stop before the cook.
`--pr` produces a reviewable branch, not a shipped milestone, and the gates below still stand between
the two.
</step>

<step name="take_the_cook_lane">
A cook is `cook-and-build-preparation` on the editor-closed lane, and that lane is mutually exclusive
with every live editor route through the project super-lock:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-ship --lane ue-editor-closed-api --lane build-config --apply
```

A `blocked` answer usually means an editor is open on this project. That is binding — close it or
wait. A cook started beside a live editor reads a content set someone is still changing.

Read the procedure rather than improvising the steps:

```powershell
python <forge-plugin-root>/scripts/forge.py procedure --task-class cook-and-build-preparation
```

Its `acceptance`, `verification` and `evidence` are what this gate grades against.

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *The procedure layer*
</step>

<step name="renew_across_the_cook">
A full cook and package routinely outruns the two-hour lease TTL. Renew before it expires:

```powershell
python <forge-plugin-root>/scripts/forge.py exec renew --project <project-root> --work-order <id> --apply
```

A lease whose owner process is still alive is never taken away — it is reported as `renewal_overdue`.
Renew anyway; liveness is only checkable from the machine that took the lease.

> **Why:** CHANGELOG.md 0.6.0 § *A lease is held by a process, not by a clock*
</step>

<step name="verify_the_package">
Require build and package verification for the target platform, not just a successful cook.

For editor-closed work the **result file is authoritative, never the exit code alone** — a cook can
exit zero having skipped assets it could not load. Read the cook log for warnings that name missing
references, and treat the packaged build's own first launch as the verification.

A milestone whose package was not launched is not shipped. Say it is unverified rather than shipped.
</step>

<step name="record_provenance" priority="last">
Record, with the artifact:

| Recorded | Read from |
|---|---|
| Engine version | `EngineAssociation` in `<project>.uproject`, and the engine actually invoked — say when they differ |
| Enabled plugins at cook time | `Plugins` in `<project>.uproject` |
| Source revision | The commit the cook ran from, not the branch name |
| Target platform and configuration | The cook invocation |
| Which acceptance suites had current evidence | `.forge/acceptance/registry.json` |

Then release the lanes, including on a failed cook:

```powershell
python <forge-plugin-root>/scripts/forge.py exec release --project <project-root> --work-order <id> --outcome passed|failed --apply
```

A failed ship that keeps the editor-closed lane blocks every other department behind it.
</step>

</process>
