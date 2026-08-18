# Test-prose findings — the 23 claims that were prose, and what each should assert

Task 5 of the v0.7.0 plan. Every docstring, comment and restating assertion message has been removed
from `tests/`. This file is what those removals *cost*: 23 places where the prose asserted something
the code does not.

**All 23 are converted.** Tier 1 landed in `3371b21`, Tier 2 in `2d0eb67`, Tiers 3 and 4 in
`30e01e1`. Two proposals in this list were wrong and are corrected in those commits: A1 expected
`rendered_to_host` to read False when it reads True, and A19 assumed every verdict command already
appeared in the in-process payload sweep when `validate` did not — that gap is now closed rather
than asserted around. A4 and A13 are written but unverified: both need a real UE 5.8 editor.

Ordered by value. Tier 1 assertions currently prove nothing at all.

---

## Tier 1 — the assertion beneath is vacuous or absent

### A1 · `tests/test_forge.py:1201` — an assertion that cannot fail
> *"A hand-edited surface is a LOCAL_VARIANT like any rendered file, and status reports the lost server by probing rather than diffing."*

`surface_path = str((root / ".mcp.json").resolve())` is assigned at the top of the test, used nowhere
else, and ends the test as `self.assertTrue(surface_path)`. `str()` of a resolved `Path` is never
empty, so **this assertion cannot fail under any condition.** It is ballast holding a claim about
probe-vs-diff that nothing checks.

**Replace with:**
```python
self.assertTrue(route["declared_in_project"])
self.assertFalse(route["rendered_to_host"])
```
The lost server is still declared by the project while absent from the rendered host surface — which
is only knowable by re-probing, not by diffing the two.

**Vacuous today: YES.**

---

### A2 · `tests/test_forge.py:2849` — asserts the fixture against itself, and the claim needs two editors
> *"The MCP endpoint is a machine port, not a project's. On a workstation running two editors, one project's session must not shut another's lane."*

Two defects. `self.assertEqual(elsewhere["name"], "UnrealEditor.exe")` asserts a field the helper
`self.editor_process(...)` just set — **the fixture verified against itself.** And the process table
contains `[elsewhere]` only: **one** editor. The docstring's scenario, two editors where one must not
shut the other's lane, is never constructed, so the discrimination is untested. The test proves only
that a single foreign editor yields `FREE`.

**Replace with:** put both editors in the table and prove the verdict flips on the command line, not
on the mere presence of an editor.
```python
mine = self.editor_process(root, pid=4242)
table = {"resolved": True, "mechanism": "Win32_Process", "processes": [elsewhere, mine]}
with self.process_table(table):
    ownership = forge.live_editor_holds_project(root)
    self.assertEqual(ownership["ownership"], "HELD")
    self.assertEqual(ownership["holder"]["pid"], 4242)
```
Keep the existing single-editor `FREE` leg as the negative case.

**Vacuous today: YES** (line 2849 specifically). This is the strongest finding in the list — it is
the exact defect v0.6.0's "an editor answering is not this project's editor answering" was written
to fix, and it is unproven.

> Note for Task 3: this test's last line reads `probe_process_route(...)["lane_clear"]`, a field
> Task 3 deletes. These two changes touch the same line and should be sequenced.

---

### A3 · `tests/test_forge.py:2586` — proves the probe answers, not that it answers *promptly*
> *"How Unreal actually answers: an event stream with no content length, kept open after the reply. Reading to EOF never returns, so a probe that waits for one reports a live editor as a route that did not answer."*

The whole test is three lines: set `behaviour = "held-open-sse"`, start the server, assert
`AVAILABLE_VERIFIED`. The handler holds the connection open for 6 seconds. **If the probe waited the
full 6 seconds and then returned, this test would still pass** — so the claim that it does not wait
for EOF is not tested. The regression this guards against is a *hang*, and no assertion measures time.

**Replace with:**
```python
start = time.monotonic()
self.assertEqual(self.route(root)["status"], "AVAILABLE_VERIFIED")
self.assertLess(time.monotonic() - start, 6)
```

**Vacuous today: NO, but blind to the actual regression.**

---

### A4 · `tests/unreal/run_unreal_acceptance.ps1` — a stage that was claimed and never written
> *"a frozen editor -- alive but not answering MCP -- is still detected"* (deleted from `.DESCRIPTION`)

**The driver has no frozen-editor stage.** Its stages are `engine-binaries`, `fixture-project`,
`forge-overlay`, `ownership-before-launch`, `ownership-editor-open`, `mcp-handshake`,
`live-route-verified`, `lane-exclusivity-open`, `blueprint-create-compile`,
`pie-and-viewport-evidence`, `ownership-editor-closed`, `lane-swap-on-close`,
`commandlet-result-file`, `driver`. There is no `frozen`, and no call to suspend a process.

The frozen editor is **the case v0.6.0 exists for** — "a silent editor is not a closed editor" — and
it is covered only by a unit test with a mocked process table, never against a real engine.

**Add a stage:** suspend the editor process (or block its port), then
```powershell
Add-Result "ownership-frozen-editor" $(if ($o.ownership -eq "HELD") {"PASS"} else {"FAIL"}) `
    "frozen editor read as $($o.ownership) via $($o.evidence.mechanism)"
```
Asserted claim: with MCP silent and the process alive, ownership is `HELD` on process-inspection
evidence.

**Vacuous today: N/A — the claim had no code at all.**

---

### A5 · `tests/unreal/mcp_client.py:120` — the module has no unit test whatsoever
> *"Read until this call's reply parses, not until the stream ends. The connection stays open after the reply, so waiting for EOF waits forever. Guessing at a terminator does not work either: a chunk boundary can land on a closing brace inside the payload and truncate a large answer. `read1` is required rather than `read`, because a plain `read(n)` on a buffered socket waits for exactly n bytes."*

Two falsifiable claims — the interior-brace truncation and the `read1` requirement — and
**`tests/unreal/mcp_client.py` has no test file.** `test_forge.py`'s `held-open-sse` handler
exercises Forge's own probe, never this client.

**Add `tests/unreal/test_mcp_client.py`,** three assertions against `_try_decode`:
```python
self.assertIsNone(_try_decode('{"jsonrpc":"2.0","result":{"a"'))       # partial
self.assertEqual(_try_decode(FRAME)["result"]["a"], 1)                 # complete
self.assertEqual(_try_decode(INTERIOR_BRACE_FRAME)["result"]["b"]["c"], 2)  # interior }
```
`INTERIOR_BRACE_FRAME` is the payload whose nested `}` would fool a terminator scan.

**Vacuous today: N/A — no test exists.**

---

## Tier 2 — the claim is real and unproven; the assertion beneath is sound but narrower

| # | Location | Deleted claim | Assertion to add |
|---|---|---|---|
| **A6** | `test_forge.py:2411` | *"Silence here would mean a lock held on the server that Forge no longer tracks."* | Test asserts `rollback_incomplete` and the note, **never checks the server.** Add `self.assertIn("Content/Main.umap", self.held_paths())` — the leak the note reports is otherwise unproven. |
| **A7** | `test_forge.py:2462` | *"The lane must not read as free while the path it protects is still locked."* | Asserts lane state only. Add `self.assertEqual(self.held_paths(), ["Content/Main.umap"])`. |
| **A8** | `test_forge.py:2819` | *"Two signals disagreeing is not evidence the project is free, so the lane stays shut **and asks**."* | Asserts the lane is shut; unlike its sibling it never asserts the prompt exists. Add `self.assertIn("human_action", forge.probe_process_route(root, self.row))`. |
| **A9** | `test_forge.py:2034` | *"The group is declared in leases.json; the runtime, not the workflow, enforces it."* | The two lanes used are never shown to share an exclusive group. Read `exclusive_groups` from `leases.json` and assert both lane names land in one group **before** asserting the conflict. |
| **A10** | `test_forge.py:2996` | *"A typo'd lane **still leases**, but it protects nothing."* | Runs `apply=False`, so nothing proves a lease is taken. Add an `apply=True` leg asserting the lease appears in `executor.status(root)["active"]` alongside `ungrouped_lanes`. |
| **A11** | `test_forge.py:3377` | *"The port is checked **first** because it is the one cause that looks like every other."* | Ordering is the claim; only membership is asserted. Add `self.assertLess(row["note"].index("THE PORT"), row["note"].index("restart"))`. |
| **A12** | `test_forge.py:1348` | *"…but the id is displayed too."* | Only the absence of a `gsd-` prefix is asserted. Add: every action in `forge_next(...)["actions"]` carries a non-empty `id`. |
| **A13** | `tests/unreal/live_editor_stages.py` | *"this server applies no schema defaults. A parameter the schema marks optional must still be supplied, and omitting one fails with a message naming the next missing parameter."* | A claim about the **live engine**, so it belongs in the acceptance driver, not a unit test. Add a stage calling a toolset tool with one optional parameter omitted, asserting `McpError` names that parameter. |
| **A14** | `tests/unreal/mcp_client.py` | *"Unreal's server runs in discovery mode by default, where `tools/list` returns only `list_toolsets`, `describe_toolset` and `call_tool`."* | `main()` only checks `if "list_toolsets" in names`. Record `names == {"list_toolsets","describe_toolset","call_tool"}` as a `discovery_mode` boolean in the report. |
| **A15** | `run_unreal_acceptance.ps1` | *"The process appears well before the MCP server finishes binding its port, so these are two waits and not one."* | The driver **measures** this (`$waited`) and then interpolates it into an English sentence, unreadable by any consumer of `acceptance-result.json`. Emit `process_detected_at` and `mcp_answered_after_seconds` as **fields**, and fail the stage if `$ownedAt` was never set. This is the 16-second finding that justified v0.6.0 — it should be a number in the artifact, not a sentence. |

---

## Tier 3 — cheap insurance; **the audit overstated these**

I verified each and the original audit's "silently weakens to nothing" claim is **wrong** for three of
them. They fail loudly, not silently. The guards are still worth adding (one line each, and the repo
already uses this idiom in five places) but they are not defects.

| # | Location | Audit claimed | What actually happens | Guard |
|---|---|---|---|---|
| **A16** | `test_forge.py:3605` `install_modes` | anchor drift makes the reachability suite vacuous | `verb_map` empties → `invoked()` falls back to `mode.lower()` → `route-status` reads unreachable → **test FAILS loudly** | `self.assertTrue(pairs)` |
| **A17** | `test_forge.py:3611` `invoked` | `PROSE_ROOTS` drift makes it vacuous | main reachability test would report *every* command unreachable and **FAIL loudly**; only `test_no_exemption_covers_a_command_the_prose_already_invokes` goes vacuous | `self.assertIn("install", found)` |
| **A18** | `test_forge.py:1252` | `REASON_OWNERS` outside `MODULE_PATHS` → all expectations 0, passes vacuously | expectation becomes 0 while the two owners still contain one `raise ValueError` each → **FAILS loudly** | `self.assertLessEqual(set(REASON_OWNERS), set(MODULE_PATHS))` |

---

## Tier 4 — already resolved in this task, listed for completeness

| # | Was | Action taken |
|---|---|---|
| **A19** | `_payloads` docstring claimed *"Every result the CLI can emit"* — it returns **8**; `leaf_commands()` enumerates ~28 | Docstring deleted. Optional follow-up: `self.assertLessEqual(forge.VERDICT_COMMANDS, set(self._payloads(root)))` |
| **A20** | `McpHandler` docstring described a `segmented-sse` behaviour **the class does not implement** (real ones: `json`, `http-error`, `not-mcp`, `jsonrpc-not-mcp`, `sse`, `held-open-sse`) | Docstring deleted; drift gone |
| **A21** | `.DESCRIPTION` claimed stages report `NOT_IMPLEMENTED`; **no code path emits it**, yet the summary counted it into `unproven` | Claim and dead counter both removed |
| **A22** | `test_a_failing_verdict_exits_contract_not_failure` — *"ran-and-said-no must stay distinguishable from could-not-run"*; only `EXIT_CONTRACT` asserted | Low value: add `self.assertNotEqual(forge.EXIT_CONTRACT, forge.EXIT_USAGE)` if wanted |
| **A23** | `game()` helper — *"so no test writes the developer's real config"*; the redirect is conditional (`if surface:`) and no-ops for a host declaring no `user_surface` | Add `self.assertTrue(surface, host)` inside the helper |

---

## Recommendation

Convert **Tier 1 (A1–A5)**. Those five are the whole justification for the exercise: two assertions
that cannot fail, one blind to the regression it names, one stage that was advertised and never
written, and one module with no test at all.

Tier 2 is genuine but lower yield — convert opportunistically when touching those files.
Tier 3 is three one-line guards; take them or leave them.
