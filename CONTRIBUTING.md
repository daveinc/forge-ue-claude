# Contributing

Keep the assigned resident host as the default and every external/local worker optional unless a workflow truly cannot exist without it. Add a capability contract, resident-baseline comparison, known-good/known-bad probe, fallback, lane declaration, and acceptance test for each new route.

Never hardcode a runtime vendor. Canon (`.forge/agents`, `.forge/directives.md`, `.forge/templates`, policy, schemas, plans, packets, evidence) must stay host-neutral and use `{{resident}}` / `{{skill:name}}` tokens; only rendering resolves a host spelling. Host-specific behaviour belongs in `plugins/forge-ue-studio/hosts/registry.json`. Repository validation and the test suite both fail on canon that leaks a host spelling.

Run:

```powershell
python scripts/validate_repo.py
python -m unittest discover -s tests -v
```

Do not commit credentials, generated Unreal directories, model weights, third-party binaries, or licensed assets.
