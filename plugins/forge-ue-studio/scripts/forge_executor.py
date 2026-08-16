#!/usr/bin/env python3
"""Transactional execution: leases, isolation and rollback enforced in code, not in prose."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable


ERROR_REASONS = MappingProxyType(
    {
        "LEASE_CONFLICT": "lease_conflict",
        "LEASE_UNKNOWN": "lease_unknown",
        "LEASE_STATE_UNREADABLE": "lease_state_unreadable",
        "PACKET_INVALID": "packet_invalid",
        "ISOLATION_FAILED": "isolation_failed",
        "VCS_UNAVAILABLE": "vcs_unavailable",
        "STATE_MUTEX_HELD": "state_mutex_held",
    }
)

LEASE_TTL_MINUTES = 120
MUTEX_STALE_SECONDS = 120
MUTEX_WAIT_SECONDS = 10
ISOLATION_MODES = ("read-only", "git-worktree", "lfs-lock", "project-exclusive")
BINARY_MODES = ("lfs-lock", "project-exclusive")
ACTIVE = "ACTIVE"


class ExecutorError(Exception):
    """A failure carrying the typed reason forge.py republishes as its own."""

    def __init__(self, message: str, reason: str, **extra: Any):
        super().__init__(message)
        if reason not in set(ERROR_REASONS.values()):
            raise ValueError(f"ExecutorError reason {reason!r} is not declared in ERROR_REASONS")
        self.reason = reason
        self.extra = extra


def _fail(message: str, reason: str, **extra: Any) -> ExecutorError:
    return ExecutorError(message, reason=reason, **extra)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _parse_time(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except ValueError:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def lease_state_path(root: Path) -> Path:
    return root / ".forge" / "state" / "leases.json"


def read_lease_state(root: Path) -> dict[str, Any]:
    """Read the lease ledger, refusing to guess when it is absent or malformed."""
    path = lease_state_path(root)
    if not path.is_file():
        raise _fail(
            f"{path} does not exist; apply the Forge overlay before executing work",
            reason=ERROR_REASONS["LEASE_STATE_UNREADABLE"],
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _fail(f"{path} is unreadable: {exc}", reason=ERROR_REASONS["LEASE_STATE_UNREADABLE"]) from exc
    if not isinstance(document, dict) or not isinstance(document.get("leases"), list):
        raise _fail(
            f"{path} does not carry a forge.lane-leases/v1 leases array",
            reason=ERROR_REASONS["LEASE_STATE_UNREADABLE"],
        )
    return document


def write_lease_state(root: Path, document: dict[str, Any]) -> None:
    """Replace the ledger atomically so a crash mid-write cannot truncate it."""
    path = lease_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(f".{os.getpid()}.tmp")
    staging.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(staging, path)


class StateMutex:
    """Cross-process mutual exclusion over the lease ledger."""

    def __init__(self, root: Path, wait_seconds: int = MUTEX_WAIT_SECONDS):
        self.path = lease_state_path(root).with_suffix(".mutex")
        self.wait_seconds = wait_seconds
        self.handle: int | None = None

    def _break_if_stale(self) -> None:
        try:
            age = time.time() - self.path.stat().st_mtime
        except OSError:
            return
        if age > MUTEX_STALE_SECONDS:
            self.path.unlink(missing_ok=True)

    def __enter__(self) -> StateMutex:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                self.handle = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.handle, str(os.getpid()).encode("utf-8"))
                return self
            except FileExistsError:
                self._break_if_stale()
                if time.monotonic() >= deadline:
                    raise _fail(
                        f"Another Forge process holds {self.path} and did not release it within "
                        f"{self.wait_seconds}s",
                        reason=ERROR_REASONS["STATE_MUTEX_HELD"],
                    ) from None
                time.sleep(0.05)

    def __exit__(self, *exc_info: Any) -> None:
        if self.handle is not None:
            os.close(self.handle)
            self.handle = None
        self.path.unlink(missing_ok=True)


def expire_stale_leases(document: dict[str, Any], now: str | None = None) -> list[str]:
    """Mark every ACTIVE lease past its expiry EXPIRED. Returns the ids recovered."""
    moment = _parse_time(now or utc_now())
    recovered: list[str] = []
    for lease in document.get("leases", []):
        if lease.get("status") != ACTIVE:
            continue
        if _parse_time(str(lease.get("expires_at", ""))) <= moment:
            lease["status"] = "EXPIRED"
            lease["released_at"] = now or utc_now()
            lease["release_note"] = "expired without release; recovered on the next acquire"
            recovered.append(str(lease.get("lease_id")))
    return recovered


def exclusive_group_of(document: dict[str, Any], name: str) -> str | None:
    for group, members in (document.get("exclusive_groups") or {}).items():
        if name in members:
            return str(group)
    return None


def lease_conflicts(
    document: dict[str, Any],
    lane: str,
    write_scope: list[str],
    mode: str,
) -> list[dict[str, Any]]:
    """Every active lease that cannot coexist with the requested one, and why."""
    if mode == "read-only":
        return []
    requested_scope = set(write_scope)
    requested_group = exclusive_group_of(document, lane)
    conflicts: list[dict[str, Any]] = []
    for held in document.get("leases", []):
        if held.get("status") != ACTIVE:
            continue
        held_lane = str(held.get("lane", ""))
        held_mode = str((held.get("isolation") or {}).get("mode", "project-exclusive"))
        if held_mode == "read-only":
            continue
        held_scope = set(held.get("write_scope", []))
        reason = None
        if held_lane == lane:
            reason = f"lane {lane!r} is already leased"
        elif requested_group and requested_group == exclusive_group_of(document, held_lane):
            reason = (
                f"lane {lane!r} and held lane {held_lane!r} are both in exclusive group "
                f"{requested_group!r}"
            )
        else:
            overlap = requested_scope & held_scope
            if overlap and (mode in BINARY_MODES or held_mode in BINARY_MODES):
                reason = (
                    f"write scope {sorted(overlap)} overlaps a lease held in {held_mode!r} mode, "
                    "which is not concurrently mergeable"
                )
        if reason:
            conflicts.append(
                {
                    "lease_id": held.get("lease_id"),
                    "lane": held_lane,
                    "owner": held.get("owner"),
                    "work_order": held.get("work_order"),
                    "expires_at": held.get("expires_at"),
                    "reason": reason,
                }
            )
    return conflicts


def git(root: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run one git command against the project, surfacing failures as typed errors."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise _fail("git is not on PATH; Forge cannot enforce isolation without it", reason=ERROR_REASONS["VCS_UNAVAILABLE"]) from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _fail(f"git {' '.join(args)} did not complete: {exc}", reason=ERROR_REASONS["VCS_UNAVAILABLE"]) from exc
    return completed


def git_checked(root: Path, *args: str, reason: str, timeout: int = 120) -> str:
    completed = git(root, *args, timeout=timeout)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise _fail(f"git {' '.join(args)} failed: {detail}", reason=reason)
    return completed.stdout.strip()


def resolve_revision(root: Path, revision: str) -> str:
    return git_checked(root, "rev-parse", "--verify", f"{revision}^{{commit}}", reason=ERROR_REASONS["ISOLATION_FAILED"])


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Check the fields the executor acts on, before it touches any state."""
    if not isinstance(packet, dict):
        raise _fail("Work packet is not an object", reason=ERROR_REASONS["PACKET_INVALID"])
    work_order = str(packet.get("work_order", "")).strip()
    if not work_order:
        raise _fail("Work packet has no work_order", reason=ERROR_REASONS["PACKET_INVALID"])
    isolation = packet.get("isolation")
    if not isinstance(isolation, dict):
        raise _fail(f"Work packet {work_order!r} has no isolation block", reason=ERROR_REASONS["PACKET_INVALID"])
    mode = str(isolation.get("mode", ""))
    if mode not in ISOLATION_MODES:
        raise _fail(
            f"Work packet {work_order!r} declares isolation mode {mode!r}; expected one of "
            f"{', '.join(ISOLATION_MODES)}",
            reason=ERROR_REASONS["PACKET_INVALID"],
        )
    if not str(isolation.get("base_revision", "")).strip():
        raise _fail(
            f"Work packet {work_order!r} declares no base_revision; isolation must start from a named revision",
            reason=ERROR_REASONS["PACKET_INVALID"],
        )
    lanes = [str(item) for item in packet.get("leases", []) if str(item).strip()]
    if mode != "read-only" and not lanes:
        raise _fail(
            f"Work packet {work_order!r} mutates in {mode!r} mode but names no lease to hold",
            reason=ERROR_REASONS["PACKET_INVALID"],
        )
    if mode == "lfs-lock" and not isolation.get("lock_targets"):
        raise _fail(
            f"Work packet {work_order!r} uses lfs-lock isolation but names no lock_targets",
            reason=ERROR_REASONS["PACKET_INVALID"],
        )
    return {
        "work_order": work_order,
        "mode": mode,
        "base_revision": str(isolation["base_revision"]),
        "lanes": lanes,
        "write_scope": [str(item) for item in packet.get("write_scope", [])],
        "workspace": str(isolation.get("workspace") or f".forge/workspaces/{work_order}"),
        "branch": str(isolation.get("branch") or f"forge/{work_order}"),
        "lock_targets": [str(item) for item in isolation.get("lock_targets", [])],
    }


def _plan(intent: dict[str, Any], owner: str, revision: str | None) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = [
        {"step": "acquire-lease", "detail": f"{lane} for {owner}"} for lane in intent["lanes"]
    ]
    if intent["mode"] == "git-worktree":
        steps.append(
            {
                "step": "create-worktree",
                "detail": f"{intent['workspace']} on branch {intent['branch']} from {revision or intent['base_revision']}",
            }
        )
    if intent["mode"] == "lfs-lock":
        steps.extend({"step": "lfs-lock", "detail": target} for target in intent["lock_targets"])
    if intent["mode"] == "project-exclusive":
        steps.append({"step": "hold-project-exclusive", "detail": "no concurrent writer may enter any lane in this group"})
    return steps


def acquire(
    root: Path,
    packet: dict[str, Any],
    owner: str,
    apply: bool,
    ttl_minutes: int = LEASE_TTL_MINUTES,
) -> dict[str, Any]:
    """Take every lease and set up isolation, or leave the project exactly as it was."""
    intent = validate_packet(packet)
    now = utc_now()
    expires_at = (
        (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=ttl_minutes))
        .replace(microsecond=0)
        .isoformat()
    )

    with StateMutex(root) as _mutex:
        document = read_lease_state(root)
        recovered = expire_stale_leases(document, now)
        blocked: list[dict[str, Any]] = []
        for lane in intent["lanes"]:
            blocked.extend(lease_conflicts(document, lane, intent["write_scope"], intent["mode"]))
        if blocked:
            raise _fail(
                f"Cannot acquire {intent['work_order']!r}: {len(blocked)} active lease(s) conflict",
                reason=ERROR_REASONS["LEASE_CONFLICT"],
                conflicts=blocked,
                recovered_stale=recovered,
            )
        revision = resolve_revision(root, intent["base_revision"]) if apply else None
        granted = [
            {
                "lease_id": f"lease-{uuid.uuid4().hex[:12]}",
                "lane": lane,
                "owner": owner,
                "work_order": intent["work_order"],
                "write_scope": intent["write_scope"] or [intent["work_order"]],
                "acquired_at": now,
                "expires_at": expires_at,
                "status": ACTIVE,
                "isolation": {
                    "mode": intent["mode"],
                    "base_revision": revision or intent["base_revision"],
                    "workspace": intent["workspace"],
                    "branch": intent["branch"],
                    "lock_targets": intent["lock_targets"],
                },
            }
            for lane in intent["lanes"]
        ]
        if apply:
            document["leases"] = list(document.get("leases", [])) + granted
            write_lease_state(root, document)
        elif recovered:
            write_lease_state(root, document)

    if not apply:
        return {
            "schema": "forge.execution-acquire/v1",
            "mode": "dry-run",
            "project": str(root),
            "work_order": intent["work_order"],
            "owner": owner,
            "isolation_mode": intent["mode"],
            "recovered_stale": recovered,
            "conflicts": [],
            "plan": _plan(intent, owner, None),
            "leases": [],
        }

    undo: list[Callable[[], str | None]] = [
        lambda: _release_ids(root, [item["lease_id"] for item in granted], "BROKEN", "rolled back after isolation failed") and None
    ]
    try:
        _establish_isolation(root, intent, revision or intent["base_revision"], undo)
    except ExecutorError as exc:
        leaked: list[str] = []
        for step in reversed(undo):
            try:
                detail = step()
            except ExecutorError as undo_failure:
                detail = str(undo_failure)
            if detail:
                leaked.append(detail)
        if leaked:
            exc.extra["rollback_incomplete"] = leaked
            exc.extra["rollback_note"] = (
                "Rollback could not undo every step. What is listed here is still held and Forge is no "
                "longer tracking it; release it by hand before another writer needs it."
            )
        raise

    return {
        "schema": "forge.execution-acquire/v1",
        "mode": "apply",
        "project": str(root),
        "work_order": intent["work_order"],
        "owner": owner,
        "isolation_mode": intent["mode"],
        "base_revision": revision,
        "workspace": intent["workspace"] if intent["mode"] == "git-worktree" else None,
        "branch": intent["branch"] if intent["mode"] == "git-worktree" else None,
        "locked": intent["lock_targets"] if intent["mode"] == "lfs-lock" else [],
        "recovered_stale": recovered,
        "conflicts": [],
        "plan": _plan(intent, owner, revision),
        "leases": granted,
    }


def _establish_isolation(root: Path, intent: dict[str, Any], revision: str, undo: list[Callable[[], str | None]]) -> None:
    if intent["mode"] == "git-worktree":
        workspace = intent["workspace"]
        branch = intent["branch"]
        git_checked(root, "worktree", "add", "-b", branch, workspace, revision, reason=ERROR_REASONS["ISOLATION_FAILED"])
        undo.append(lambda: _undo_worktree(root, workspace, branch))
    if intent["mode"] == "lfs-lock":
        for target in intent["lock_targets"]:
            git_checked(root, "lfs", "lock", target, reason=ERROR_REASONS["ISOLATION_FAILED"])
            undo.append(lambda held=target: _undo_lock(root, held))


def _undo_lock(root: Path, target: str) -> str | None:
    completed = git(root, "lfs", "unlock", target)
    if completed.returncode == 0:
        return None
    return f"lfs lock on {target!r} could not be released: {(completed.stderr or completed.stdout or '').strip()}"


def _undo_worktree(root: Path, workspace: str, branch: str) -> str | None:
    completed = git(root, "worktree", "remove", "--force", workspace)
    git(root, "branch", "-D", branch)
    if completed.returncode == 0:
        return None
    return f"worktree {workspace!r} could not be removed: {(completed.stderr or completed.stdout or '').strip()}"


def _remove_worktree(root: Path, workspace: str, branch: str) -> None:
    git(root, "worktree", "remove", "--force", workspace)
    git(root, "branch", "-D", branch)


def _release_ids(root: Path, lease_ids: list[str], status: str, note: str) -> list[dict[str, Any]]:
    with StateMutex(root) as _mutex:
        document = read_lease_state(root)
        released: list[dict[str, Any]] = []
        for lease in document.get("leases", []):
            if str(lease.get("lease_id")) in lease_ids and lease.get("status") == ACTIVE:
                lease["status"] = status
                lease["released_at"] = utc_now()
                lease["release_note"] = note
                released.append(lease)
        write_lease_state(root, document)
    return released


def release(root: Path, work_order: str, outcome: str, apply: bool) -> dict[str, Any]:
    """Release every lease a work order holds and tear down what its outcome no longer earns."""
    document = read_lease_state(root)
    held = [
        lease
        for lease in document.get("leases", [])
        if str(lease.get("work_order")) == work_order and lease.get("status") == ACTIVE
    ]
    if not held:
        raise _fail(
            f"No active lease is held for work order {work_order!r}",
            reason=ERROR_REASONS["LEASE_UNKNOWN"],
        )
    isolation = held[0].get("isolation") or {}
    mode = str(isolation.get("mode", "read-only"))
    discards_workspace = outcome == "failed" and mode == "git-worktree"
    teardown: list[dict[str, str]] = []
    if mode == "lfs-lock":
        teardown.extend({"step": "lfs-unlock", "detail": target} for target in isolation.get("lock_targets", []))
    if discards_workspace:
        teardown.append({"step": "remove-worktree", "detail": f"{isolation.get('workspace')} and branch {isolation.get('branch')}"})
    teardown.extend({"step": "release-lease", "detail": str(lease.get("lane"))} for lease in held)

    if not apply:
        return {
            "schema": "forge.execution-release/v1",
            "mode": "dry-run",
            "project": str(root),
            "work_order": work_order,
            "outcome": outcome,
            "isolation_mode": mode,
            "workspace_retained": mode == "git-worktree" and not discards_workspace,
            "workspace": str(isolation.get("workspace")) if mode == "git-worktree" and not discards_workspace else None,
            "plan": teardown,
            "released": [],
            "unlocked": [],
            "unlock_failures": [],
            "note": None,
        }

    unlocked: list[str] = []
    unlock_failures: list[dict[str, str]] = []
    if mode == "lfs-lock":
        for target in isolation.get("lock_targets", []):
            completed = git(root, "lfs", "unlock", str(target))
            if completed.returncode == 0:
                unlocked.append(str(target))
            else:
                unlock_failures.append(
                    {"target": str(target), "detail": (completed.stderr or completed.stdout or "").strip()}
                )
    if discards_workspace:
        _remove_worktree(root, str(isolation.get("workspace")), str(isolation.get("branch")))
    released = _release_ids(
        root,
        [str(lease.get("lease_id")) for lease in held],
        "RELEASED",
        f"released on outcome {outcome}",
    )
    return {
        "schema": "forge.execution-release/v1",
        "mode": "apply",
        "project": str(root),
        "work_order": work_order,
        "outcome": outcome,
        "isolation_mode": mode,
        "workspace_retained": mode == "git-worktree" and not discards_workspace,
        "workspace": str(isolation.get("workspace")) if mode == "git-worktree" and not discards_workspace else None,
        "plan": teardown,
        "released": released,
        "unlocked": unlocked,
        "unlock_failures": unlock_failures,
        "note": (
            f"{len(unlock_failures)} lock(s) could not be released and are still held on the LFS server; "
            "the lane is free but those paths are not. Unlock them before another writer needs them."
            if unlock_failures
            else None
        ),
    }


def status(root: Path) -> dict[str, Any]:
    """Report what is held right now, and what expired without being released."""
    document = read_lease_state(root)
    recoverable = [
        lease
        for lease in document.get("leases", [])
        if lease.get("status") == ACTIVE and _parse_time(str(lease.get("expires_at", ""))) <= _parse_time(utc_now())
    ]
    active = [lease for lease in document.get("leases", []) if lease.get("status") == ACTIVE]
    return {
        "schema": "forge.execution-status/v1",
        "project": str(root),
        "active": active,
        "expired_awaiting_recovery": [lease.get("lease_id") for lease in recoverable],
        "exclusive_groups": document.get("exclusive_groups", {}),
        "state_path": str(lease_state_path(root)),
    }
