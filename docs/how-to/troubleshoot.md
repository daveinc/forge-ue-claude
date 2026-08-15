# Troubleshoot

## Forge does not appear in a session

1. Confirm the plugin is installed: `/plugin` in Claude Code, or `codex plugin list` in Codex.
2. Confirm `forge-ue-studio@forge-ue-studio-local` is installed and enabled.
3. Rerun `.\install.ps1 -Mode Plugin -RuntimeHost <id> -Apply` from the current Forge repository.
4. Start a new session; existing sessions do not acquire a newly installed skill snapshot.

## The host CLI is not found

Forge will not install or modify a runtime host automatically. Install or repair it through its own supported setup, then rerun `.\install.ps1 -Mode Host -HostAction list` to confirm detection.

## GSD is missing or not visible to Forge

1. Run `.\install.ps1 -Mode GSD -RuntimeHost <id>` and review the pinned package and current detection state.
2. Run the same command with `-Apply` only after approving the external install.
3. Rerun the Forge survey and confirm `workflow.gsd` is detected. GSD places its skills, agents, and runtime under the host's home directory — `~/.claude/gsd-core` for Claude Code, `~/.codex/gsd-core` for Codex — plus shared skills under `~/.agents/skills`. Forge reads those locations from the host profile's `discovery` and `gsd` blocks.
4. Start a new session so newly installed GSD skills and agents are loaded.

## The project instruction file or agents look wrong for my host

The generated surfaces are stale. Run `.\install.ps1 -Mode Host -HostAction status -ProjectPath "<project>"`; anything not `CURRENT` needs re-rendering with `-HostAction set -RuntimeHost <id> -Apply`. Forge Next reports this as the `host-surfaces-stale` situation rather than letting work proceed against stale instructions.

## A route stopped being eligible after I changed runtime

This is intended. Qualification evidence does not cross hosts, because context windows, tool scopes, and generation surfaces differ. Re-probe the route through `forge-capability-admin` under the new host.

## Project adoption says the project path is invalid

Pass an existing directory or a full `.uproject` path. Pre-project directories are supported. If a directory contains multiple top-level `.uproject` files, pass the intended file explicitly; Forge refuses to guess.

## Forge tries to continue after a stop point

Stop the current task. Open a fresh project task and run `forge-next`. It reads GSD smart-entry state and routes paused, blocked, failed-verification, planning, execution, and verification situations without trusting prior chat or the deprecated Forge lifecycle mirror.

## A detected model, MCP, Blender, or Unreal route is not used

Expected until that exact route is consented, probed, and qualified. Ask:

```text
Use forge-capability-admin to explain the missing qualification evidence for this route. Do not install or activate anything without my approval.
```

## Forge proposes `.forge-proposed` files

The target already contains a different file. Forge preserves it and writes the proposed version beside it for review instead of overwriting accepted local policy.

## A command failed and I need to know why

Every failure carries a typed `reason` code, and exit code `2` (ran, and the answer is no) is deliberately different from exit code `1` (could not run). See the [failure contract](../failure-contract.md).
