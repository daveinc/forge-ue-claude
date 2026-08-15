# Contributing

Keep the assigned resident host as the default and every external/local worker optional unless a workflow truly cannot exist without it. Add a capability contract, resident-baseline comparison, known-good/known-bad probe, fallback, lane declaration, and acceptance test for each new route.

Never hardcode a runtime vendor. Canon (`.forge/agents`, `.forge/directives.md`, `.forge/templates`, policy, schemas, plans, packets, evidence) must stay host-neutral and use `{{resident}}` / `{{skill:name}}` tokens; only rendering resolves a host spelling. Host-specific behaviour belongs in `plugins/forge-ue-studio/hosts/registry.json` — the one file exempt from the neutrality guard.

`scripts/validate_repo.py` scans all of `assets/project-template/`, `dependencies/*.json`, and `schemas/*.json` and fails on any vendor name, host home directory, host instruction filename, host agent directory, or host skill invocation. The banned-token list is derived from the registry itself, so it extends automatically when a host is added. `tests/test_forge.py` exercises the guard in both directions — that it catches planted leaks, and that it tolerates path segments like `plugins/forge-ue-studio/…` and protocol names like `openai-compatible`.

Inside `forge.py`, write skill references as **bare names** (`forge-next`, not `$forge-next`). `normalize_gsd_command` adds the active host's prefix; the neutral fallback is no prefix, so a forgotten `profile` argument degrades to a bare name rather than another host's spelling.

Adding a host must not require code changes. If you find yourself editing a host list outside `registry.json`, that is the bug.

## Code carries no comments

`forge.py`, `validate_repo.py`, `test_forge.py`, and `install.ps1` ship with zero comments, and `validate_repo.py` fails the build on a new one. A comment is one of three things, and each has a home that is not the source:

- **A rule** — how Forge must behave. It belongs in the skill step that performs it, in `docs/`, or in the registry that declares it, where the workflow reading it will actually see it. A rule restated in a comment is a second copy that drifts from the first.
- **An explanation of what the code does** — it belongs in the code: name the value, extract the function, or state it in the failure message the user reads.
- **History** — why something used to be different. It belongs in the commit message and `CHANGELOG.md`.

Docstrings stay, one line, naming what a function returns. Shebangs and tool pragmas (`# noqa`, `# type:`) are exempt.

Run:

```powershell
python scripts/validate_repo.py
python -m unittest discover -s tests -v
```

Do not commit credentials, generated Unreal directories, model weights, third-party binaries, or licensed assets.
