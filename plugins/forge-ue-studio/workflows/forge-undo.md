# Forge Undo — workflow

## PRE — Forge

1. Check the binary-asset lock. Never revert Unreal content while another lane holds the project-exclusive lease.
2. Identify dependent packets from the canonical registry before reverting.

## CORE — GSD

1. Run GSD's undo, which owns the phase manifest and dependency checks.

## POST — Forge

1. Confirm the working copy still opens in the editor before declaring the rollback complete.
