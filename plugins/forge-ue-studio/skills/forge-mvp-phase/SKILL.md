---
name: forge-mvp-phase
description: Plan a game project phase as a vertical slice — the thinnest thing that is actually playable — then split it if it is too big. Use when a phase is large or vague, when the goal is to prove a loop rather than ship a feature, or before committing to full production on an unproven mechanic.
---

# Forge MVP Phase

Delegation mode: **relay** — this workflow is interactive, so surface each question in game-dev framing and pass answers back down. Never black-box it. GSD workflow: `mvp-phase.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape and the rules not repeated here.

## What a vertical slice means here

GSD's MVP mode is built around a user story — "As a / I want to / So that" — and SPIDR splitting. That framing is for shipping software features. A game phase is not done when a feature exists; it is done when a **loop is playable and feels like something**.

So translate before relaying. The slice is the thinnest path that a player can actually run end to end: input → mechanic → feedback → outcome. Placeholder art is expected and acceptable. A slice with final art and no loop is not a slice.

## PRE — Forge

1. Load the GDD decision ledger and the phase entry. Identify which gameplay pillar the slice is meant to prove.
2. Decide what "playable" means for this slice, concretely: the input, the mechanic under test, the feedback the player receives, and the win/lose or exit condition.
3. Identify the placeholder budget — which assets are allowed to be greybox, and which must be real because the slice is testing presentation rather than mechanics.

## CORE — GSD

1. Relay GSD's MVP workflow. It prompts for a story, runs the SPIDR splitting check, writes the mode field to the roadmap, and hands off to planning.
2. Reframe its story prompt as a player statement before showing it: *what the player does, what they experience, why it matters to the loop* — not *as a user I want*.
3. When SPIDR proposes a split, judge each candidate by whether it leaves a playable loop behind. A split that produces two non-playable halves is the wrong split; prefer one that narrows scope while keeping the loop intact.

## POST — Forge

1. Record the slice's acceptance criteria in `.forge/acceptance/` as a **feel** criterion plus a mechanical one. The mechanical half can be automated; the feel half is a human gate and stays one.
2. Register the asset interfaces the slice depends on, marked as placeholder-satisfiable, so visual production can proceed in parallel against them.
3. Hand off to `forge-plan-phase`. GSD auto-detects MVP mode from the roadmap field, so do not re-declare it.

## Boundaries

- Never let a slice grow to include work that does not serve the loop under test. That is the failure MVP mode exists to prevent.
- Never accept "the feature is implemented" as slice completion. Run it. `forge-gameplay-gauntlet` is the right follow-up once a loop exists.
