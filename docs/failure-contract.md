# Failure contract

How `forge.py` reports a failure, and what a caller may rely on. Modelled on
GSD's own CLI contract (`bin/lib/io.cjs`, `bin/lib/cli-exit.cjs`) so a skill
reading one runtime's errors reads the other's the same way.

## Every failure is typed

A failure carries a reason code, not only a sentence:

```json
{"ok": false, "reason": "project_not_found", "message": "Project directory does not exist", "command": "host"}
```

`reason` is the stable part. `message` is written for a person and may be
reworded at any time. **Branch on `reason`; never parse `message`.**

The full vocabulary is `ERROR_REASON` in `plugins/forge-ue-studio/scripts/forge_core.py`,
which folds in the reasons `forge_executor.py` declares for the leases and isolation
it enforces. It is a frozen mapping, so it cannot be extended at runtime, and
`scripts/validate_repo.py` refuses a call site that passes an inline reason
string or declares a reason nothing raises. The enum is therefore the complete
list of everything this CLI can fail with.

### Adding a reason

1. Pick a `snake_case` value. That string is the wire form.
2. Group it under the subsystem prefix its call sites belong to.
3. Raise it: `raise fail("what happened", reason=ERROR_REASON["NEW_CODE"])`.

The validator fails the build if the new code is never raised, so a reason
cannot be added speculatively and left dangling.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Success. |
| `1` | Operational failure — something the run needed was missing, unreadable, or refused. |
| `2` | The command ran and returned a verdict of not-ok. Used by report verbs whose payload carries `ok: false` as a **result**, not as an error. |
| `3` | Usage error — the invocation itself was wrong. |

`2` and `1` are deliberately different. A bootstrap check that runs correctly
and reports an incomplete bootstrap is not the same event as a bootstrap check
that could not run, and a caller that conflates them will retry the wrong one.

## `ok` is a verdict, not decoration

A payload carries `ok` when pass/fail **is** the answer, and not otherwise. GSD
draws the same line: `check-latest-version` carries `ok` because "did the check
succeed" is its result, while `smart-entry` does not, because its result is the
situation.

`VERDICT_COMMANDS` in `forge.py` is the list. Today it is `verify`,
`bootstrap-check`, `validate` and `host status`. `main()` asserts membership
**both ways** — a declared verdict command that returns no `ok` fails, and a
reporting command that grows one fails too. There is no
`result.get("ok", True)` default anywhere, because a default makes a forgotten
verdict indistinguishable from a deliberate absence, and the forgotten one then
silently exits 0.

Commands with a richer outcome say so in their own field rather than flattening
it into a boolean. `mcp sync-user` reports `mode` — `dry-run`, `apply`,
`blocked`, `report-only` — because "applied nothing" is frequently the correct
result rather than a failure.

Every payload also carries `schema`, so a consumer identifies what it received
instead of inferring it from which keys happen to be present.

## Failures are raised, not exited

CLI logic raises `ForgeExit`; `main()` is the only place that turns one into an
exit code. Nothing in the module calls `sys.exit()`, which is enforced by a test
that walks the AST rather than grepping the source. A caller that imports
`forge.py` as a module therefore gets an exception it can catch instead of a
process that disappears underneath it.

A bare `ValueError` reaching `main()` is a **bug**, and is reported as
`reason: "unknown"` rather than being dressed up as a declared failure. Exactly
one `raise ValueError` is permitted in the module: the guard that refuses an
undeclared reason code.

## Degradation is explicit about what it tolerates

A site that degrades instead of failing catches `ForgeExit` by name, so it states
which declared failure it is willing to absorb. Two rules hold there:

- **Indeterminate is not success.** A check that could not run must record a
  failure, not a pass. An unreadable packet registry makes job coverage unknown,
  so bootstrap reports that it could not be checked rather than reporting an
  empty expected set and passing vacuously.
- **A guard must not assert over nothing.** Where a check iterates an inventory,
  the empty inventory is itself a failure, so a gate cannot pass by finding
  nothing to check.

## What a skill should do

Read `reason` and act. Do not match on message text, and do not treat a non-zero
exit as interchangeable with a payload whose `ok` is `false` — the first means
the command failed, the second means it ran and told you something.
