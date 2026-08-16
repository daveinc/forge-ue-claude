# Forge Debug — workflow

## PRE — Forge

1. Collect Unreal evidence first: crash logs, `Saved/Logs`, PIE output, and the exact reproduction lane — editor open, editor closed, or packaged build.

## CORE — GSD

1. Relay GSD's debugging cycle. It owns hypothesis tracking and session state.

## POST — Forge

1. Reproduce editor-closed before accepting a fix wherever possible. Never treat editor-open behaviour as proof for a packaged build.
2. Promote a confirmed root cause to `.forge/learnings/` only after repeated evidence-backed success.
