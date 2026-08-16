# Forge Mvp Phase — workflow

## PRE — Forge

1. Load the GDD decision ledger and the phase entry. Name the gameplay pillar the slice proves.
2. Define "playable" concretely: the input, the mechanic under test, the feedback the player receives, and the win/lose or exit condition.
3. Set the placeholder budget: which assets may be greybox, and which must be real because the slice tests presentation.

## CORE — GSD

1. Relay GSD's MVP workflow. It owns the story prompt, the splitting check, and the handoff to planning.
2. Reframe every story prompt as a player statement before showing it — what the player does, experiences, and why it matters to the loop.
3. Judge each split candidate by whether it leaves a playable loop behind. Reject a split that produces two non-playable halves.

## POST — Forge

1. Record the slice's acceptance in `.forge/acceptance/` as a feel criterion plus a mechanical one. Keep the feel half a human gate.
2. Register the asset interfaces the slice depends on, marked placeholder-satisfiable.
3. Hand off to `forge-plan-phase` without re-declaring the phase mode.

## Boundaries

- Never let a slice grow to include work that does not serve the loop under test.
- Never accept "the feature is implemented" as slice completion. Run it, then use `forge-gameplay-gauntlet`.
