# Contributing

Keep Codex as the resident default and every external/local worker optional unless a workflow truly cannot exist without it. Add a capability contract, Codex baseline comparison, known-good/known-bad probe, fallback, lane declaration, and acceptance test for each new route.

Run:

```powershell
python scripts/validate_repo.py
python -m unittest discover -s tests -v
```

Do not commit credentials, generated Unreal directories, model weights, third-party binaries, or licensed assets.
