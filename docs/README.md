# Forge documentation

Start with a tutorial if you have not run Forge before. Reach for a how-to when you know what you want and need the steps. Reference is the exact surface; explanation is why it works that way.

## Tutorials

- [Your first game](tutorials/your-first-game.md) — from an empty folder to a design interview and a first phase, one guaranteed path.
- [Adopt an existing project](tutorials/adopt-an-existing-project.md) — bring Forge to an Unreal project that already has code, content, or design documents.

## How-to guides

- [Install Forge](how-to/install-forge.md) — requirements, choosing a runtime host, installing the plugin and GSD.
- [Swap the resident runtime](how-to/swap-runtime-host.md) — move a project between runtime hosts without losing state.
- [Troubleshoot](how-to/troubleshoot.md) — Forge missing from a session, GSD not detected, stale surfaces, refused routes.

## Reference

- [Skills](reference/skills.md) — every `forge-` verb, when to use it, and the normal production sequence.
- [Installer](reference/installer.md) — every `install.ps1` mode, what it writes, and its flags.
- [Repository and project layout](reference/repository-layout.md) — what ships in this repository and what project adoption adds.
- [Failure contract](failure-contract.md) — typed failure reasons, exit codes, and degradation rules.
- [Host runtimes](host-runtimes.md) — the prerequisite contract, canon versus rendered surfaces, and how to add a host.

## Explanation

- [How Forge works](explanation/how-forge-works.md) — the studio model, the capability ladder, and the Unreal routes.
- [Build doctrine](explanation/build-doctrine.md) — the split between planning artifacts and build doctrine, what crosses the boundary, and the procedure layer.
- [Dependency and route policy](dependency-policy.md) — what Forge requires versus what it routes to, and how a route is selected.
- [Installation agent jobs](installation-agent-jobs.md) — the bounded investigations `forge-bootstrap` dispatches.
- [GSD independence map](gsd-independence-map.md) — what GSD does, what Forge fronts, and what replacing it would cost.
- [The Forge counterplan](COUNTERPLAN.md) — the full architecture and staged build proposal.
- [Incidents](incidents/2026-08-15-runnerroyale-lifecycle-drift.md) — post-mortems that changed a Forge rule.
- [Test-prose findings](incidents/test-prose-findings.md) — the 23 claims that were prose in `tests/`, and what each should assert.

## Related

- [Root README](../README.md) — what Forge is, and the quickstart.
- [Changelog](../CHANGELOG.md) — release history.
- [Contributing](../CONTRIBUTING.md) — the rules this repository enforces on itself.
