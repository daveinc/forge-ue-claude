#!/usr/bin/env python3
"""Transactional execution: leases, isolation and rollback enforced in code, not in prose."""

from __future__ import annotations

import datetime as dt
import json
import os
import platform
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
        "LEASE_NOT_RENEWABLE": "lease_not_renewable",
        "PACKET_INVALID": "packet_invalid",
        "ISOLATION_FAILED": "isolation_failed",
        "VCS_UNAVAILABLE": "vcs_unavailable",
        "STATE_MUTEX_HELD": "state_mutex_held",
        "RECONCILE_INCOMPLETE": "reconcile_incomplete",
        "LANE_ABANDONED": "lane_abandoned",
    }
)

LEASE_TTL_MINUTES = 120
CROSS_MACHINE_GRACE_MINUTES = 60
MUTEX_STALE_SECONDS = 120
MUTEX_WAIT_SECONDS = 10
PROCESS_PROBE_TIMEOUT = 15
ISOLATION_MODES = ("read-only", "git-worktree", "lfs-lock", "project-exclusive")
BINARY_MODES = ("lfs-lock", "project-exclusive")
ACTIVE = "ACTIVE"
RELEASING = "RELEASING"
ORPHANED = "ORPHANED_EXTERNAL_LOCK"
HOLDING_STATES = (ACTIVE, RELEASING, ORPHANED)


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


def _in_minutes(minutes: int) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)).replace(microsecond=0).isoformat()


def _parse_time(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except ValueError:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def this_machine() -> str:
    return platform.node() or "unknown-machine"


def _run_probe(command: list[str]) -> tuple[str | None, str]:
    """Output of one process-inspection mechanism, and why it failed when it did.

    A caller that is told only None cannot attempt a resolution: a permission
    denial, a missing binary and a hung mechanism all need different answers.
    """
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=PROCESS_PROBE_TIMEOUT,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return None, f"{command[0]} is not on PATH"
    except PermissionError as exc:
        return None, f"{command[0]} refused to run: {exc}"
    except subprocess.TimeoutExpired:
        return None, f"{command[0]} did not answer within {PROCESS_PROBE_TIMEOUT}s"
    except OSError as exc:
        return None, f"{command[0]} could not be started: {exc}"
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()
        return None, f"{command[0]} exited {completed.returncode}: {detail[0] if detail else 'no error text'}"
    return completed.stdout, ""


def process_table() -> dict[str, Any]:
    """Every running process with its pid, name, command line and start time.

    Two independent mechanisms, because a failed inspection is a fault to resolve
    rather than a condition to route around: a caller that cannot tell must be
    able to say so instead of reading an empty table as an empty machine.
    """
    if platform.system() == "Windows":
        script = (
            "Get-CimInstance Win32_Process | "
            "Select-Object ProcessId,Name,CommandLine,CreationDate | "
            "ConvertTo-Json -Compress -Depth 3"
        )
        attempts: list[dict[str, str]] = []
        raw, why = _run_probe(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
        if why:
            attempts.append({"mechanism": "Win32_Process", "detail": why})
        if raw and raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                rows = parsed if isinstance(parsed, list) else [parsed]
                return {
                    "resolved": True,
                    "mechanism": "Win32_Process",
                    "processes": [
                        {
                            "pid": row.get("ProcessId"),
                            "name": str(row.get("Name") or ""),
                            "command_line": str(row.get("CommandLine") or ""),
                            "started_at": str(row.get("CreationDate") or ""),
                        }
                        for row in rows
                        if isinstance(row, dict) and row.get("ProcessId") is not None
                    ],
                }
        if raw is not None and not attempts:
            attempts.append({"mechanism": "Win32_Process", "detail": "answered but returned no parseable process rows"})
        raw, why = _run_probe(["tasklist", "/FO", "CSV", "/NH"])
        if why:
            attempts.append({"mechanism": "tasklist", "detail": why})
        if raw:
            processes = []
            for line in raw.splitlines():
                fields = [field.strip('"') for field in line.split('","')]
                if len(fields) < 2:
                    continue
                name = fields[0].lstrip('"')
                try:
                    pid = int(fields[1])
                except ValueError:
                    continue
                processes.append({"pid": pid, "name": name, "command_line": "", "started_at": ""})
            if processes:
                return {"resolved": True, "mechanism": "tasklist", "processes": processes}
        return {
            "resolved": False,
            "mechanism": None,
            "processes": [],
            "attempts": attempts,
            "detail": "neither Win32_Process nor tasklist answered; process ownership cannot be determined on this "
                      "machine. " + "; ".join(f"{item['mechanism']}: {item['detail']}" for item in attempts),
        }
    raw, why = _run_probe(["ps", "-eo", "pid=,lstart=,comm=,args="])
    if raw is None:
        return {
            "resolved": False,
            "mechanism": None,
            "processes": [],
            "attempts": [{"mechanism": "ps", "detail": why}],
            "detail": f"ps did not answer, so process ownership cannot be determined on this machine: {why}",
        }
    processes = []
    for line in raw.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        processes.append({"pid": pid, "name": parts[1].split()[-1], "command_line": parts[1], "started_at": ""})
    return {"resolved": True, "mechanism": "ps", "processes": processes}


def process_identity(pid: int | None = None) -> dict[str, Any]:
    """This process's identity, recorded on a lease so its liveness can be checked later."""
    target = os.getpid() if pid is None else pid
    table = process_table()
    match = next((row for row in table["processes"] if row["pid"] == target), None)
    return {
        "pid": target,
        "machine": this_machine(),
        "started_at": match["started_at"] if match else "",
    }


def owner_is_alive(lease: dict[str, Any], table: dict[str, Any] | None = None) -> dict[str, Any]:
    """Whether the process holding this lease is still running, and on what evidence.

    A bare pid is not enough over a two-hour lease: pids are reused, and a reused
    one would read as the original owner still working. The recorded start time is
    what separates the two.
    """
    machine = str(lease.get("owner_machine") or "")
    pid = lease.get("owner_pid")
    if not machine or pid is None:
        return {"alive": None, "detail": "lease records no owner process, so liveness cannot be checked"}
    if machine != this_machine():
        return {
            "alive": None,
            "detail": f"owner runs on {machine!r} and this is {this_machine()!r}; liveness is not checkable from here",
        }
    resolved = table if table is not None else process_table()
    if not resolved["resolved"]:
        return {"alive": None, "detail": str(resolved.get("detail", "process inspection did not answer"))}
    match = next((row for row in resolved["processes"] if row["pid"] == pid), None)
    if match is None:
        return {"alive": False, "detail": f"no process {pid} is running on {machine}"}
    recorded_start = str(lease.get("owner_process_start") or "")
    if recorded_start and match["started_at"] and match["started_at"] != recorded_start:
        return {
            "alive": False,
            "detail": f"process {pid} exists but started at {match['started_at']}, not {recorded_start}; the pid was reused",
        }
    return {"alive": True, "detail": f"process {pid} is running on {machine} and matches the recorded start time"}


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


def write_state_atomically(path: Path, document: dict[str, Any]) -> None:
    """Replace a state ledger atomically so a crash mid-write cannot truncate it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(f".{os.getpid()}.tmp")
    staging.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(staging, path)


def write_lease_state(root: Path, document: dict[str, Any]) -> None:
    write_state_atomically(lease_state_path(root), document)


class StateMutex:
    """Cross-process mutual exclusion over one state ledger."""

    def __init__(self, root: Path, wait_seconds: int = MUTEX_WAIT_SECONDS, state_path: Path | None = None):
        self.path = (state_path or lease_state_path(root)).with_suffix(".mutex")
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


def abandoned_by(lease: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, str] | None]:
    """What an owner that exited without releasing left standing behind it.

    An LFS lock outlives the process that took it, so a lane recovered from a
    dead owner is not a lane anyone can write: the lock is still held on the
    server and only an unlock frees it. A worktree outlives the process too, but
    it blocks no other writer — it occupies a path of its own and holds the dead
    worker's uncommitted work, which is why it is named rather than removed.
    """
    isolation = lease.get("isolation") or {}
    mode = str(isolation.get("mode", "read-only"))
    if mode == "lfs-lock":
        return (
            [
                {
                    "kind": "lfs-lock",
                    "target": str(target),
                    "detail": "the owner exited without releasing it, so the lock is still held on the server",
                }
                for target in isolation.get("lock_targets", [])
            ],
            None,
        )
    if mode == "git-worktree":
        return [], {"workspace": str(isolation.get("workspace")), "branch": str(isolation.get("branch"))}
    return [], None


def expire_stale_leases(document: dict[str, Any], now: str | None = None) -> dict[str, Any]:
    """Recover leases whose owner is gone; keep the lane for an owner still working.

    The clock alone cannot free a lane. Work that legitimately outruns the TTL —
    a Nanite rebuild, a cook, a mass retarget — would otherwise have its isolation
    withdrawn while it is still writing, which is the failure the lease exists to
    prevent. A lease is recovered only on evidence its owner is gone: the process
    is absent on the machine that took it, or its pid was reused, or it was taken
    on another machine and is past the cross-machine grace as well.

    Recovering the ledger entry is not the same as recovering the lane. What the
    dead owner still holds outside the ledger decides which: locks it never
    released quarantine the lane, because handing it on as clean would send the
    next writer at a file it cannot write.
    """
    moment = _parse_time(now or utc_now())
    stamp = now or utc_now()
    table: dict[str, Any] | None = None
    recovered: list[str] = []
    overdue: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    abandoned: list[dict[str, Any]] = []
    for lease in document.get("leases", []):
        if lease.get("status") != ACTIVE:
            continue
        if _parse_time(str(lease.get("expires_at", ""))) > moment:
            continue
        if table is None:
            table = process_table()
        liveness = owner_is_alive(lease, table)
        if liveness["alive"] is True:
            overdue.append(
                {
                    "lease_id": lease.get("lease_id"),
                    "lane": lease.get("lane"),
                    "owner": lease.get("owner"),
                    "work_order": lease.get("work_order"),
                    "expires_at": lease.get("expires_at"),
                    "heartbeat_at": lease.get("heartbeat_at"),
                    "detail": liveness["detail"],
                    "remedy": "the owner is still running, so the lane stays held. Renew it with "
                              "`forge.py exec renew`, or stop the worker before another writer needs the lane",
                }
            )
            continue
        if liveness["alive"] is None:
            recoverable_after = _parse_time(str(lease.get("recoverable_after") or lease.get("expires_at", "")))
            if recoverable_after > moment:
                overdue.append(
                    {
                        "lease_id": lease.get("lease_id"),
                        "lane": lease.get("lane"),
                        "owner": lease.get("owner"),
                        "work_order": lease.get("work_order"),
                        "expires_at": lease.get("expires_at"),
                        "recoverable_after": lease.get("recoverable_after"),
                        "detail": liveness["detail"],
                        "remedy": "liveness is unknown from here, so the lane is held until the grace window "
                                  "passes rather than freed on a guess",
                    }
                )
                continue
        still_held, workspace = abandoned_by(lease)
        entry = {
            "lease_id": lease.get("lease_id"),
            "lane": lease.get("lane"),
            "owner": lease.get("owner"),
            "work_order": lease.get("work_order"),
            "detail": liveness["detail"],
        }
        if still_held:
            lease["status"] = ORPHANED
            lease["unreleased"] = still_held
            lease["release_note"] = (
                f"the owner is gone and {len(still_held)} external resource(s) it took were never released, so "
                "the lane stays quarantined rather than being handed on as clean"
            )
            lease.pop("released_at", None)
            quarantined.append(
                {
                    **entry,
                    "unreleased": still_held,
                    "remedy": "free them with `forge.py exec reconcile`; until then no writer may take the lane",
                }
            )
            continue
        lease["status"] = "EXPIRED"
        lease["released_at"] = stamp
        lease["release_note"] = f"expired without release; recovered because {liveness['detail']}"
        if workspace:
            lease["abandoned"] = workspace
            abandoned.append(
                {
                    **entry,
                    **workspace,
                    "remedy": "the lane is free, but this workspace holds the dead worker's uncommitted work. "
                              "Take what you need from it, then `git worktree remove` it by hand",
                }
            )
        recovered.append(str(lease.get("lease_id")))
    return {"recovered": recovered, "overdue": overdue, "quarantined": quarantined, "abandoned": abandoned}


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
        held_status = str(held.get("status", ""))
        if held_status not in HOLDING_STATES:
            continue
        held_lane = str(held.get("lane", ""))
        held_mode = str((held.get("isolation") or {}).get("mode", "project-exclusive"))
        if held_mode == "read-only":
            continue
        held_scope = set(held.get("write_scope", []))
        reason = None
        if held_status == ORPHANED and (requested_scope & held_scope or held_lane == lane):
            reason = (
                f"lane {lane!r} is quarantined: releasing {held.get('work_order')!r} could not free "
                f"{held.get('unreleased') or 'an external resource'}, so the lane is not actually free. "
                "Clear it with `forge.py exec reconcile`"
            )
        elif held_lane == lane:
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
                    "status": held_status,
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
    """Take every lease and set up isolation, or leave the project exactly as it was.

    What the recovery sweep found is written before the conflicts are weighed,
    because it is true whether or not this acquisition succeeds. Holding it until
    the end discarded it on exactly the runs that most needed it recorded: the
    ones refused because the lane was still held.
    """
    intent = validate_packet(packet)
    now = utc_now()
    expires_at = _in_minutes(ttl_minutes)
    identity = process_identity()

    with StateMutex(root) as _mutex:
        document = read_lease_state(root)
        expiry = expire_stale_leases(document, now)
        recovered = expiry["recovered"]
        if recovered or expiry["quarantined"]:
            write_lease_state(root, document)
        blocked: list[dict[str, Any]] = []
        for lane in intent["lanes"]:
            blocked.extend(lease_conflicts(document, lane, intent["write_scope"], intent["mode"]))
        if blocked:
            raise _fail(
                f"Cannot acquire {intent['work_order']!r}: {len(blocked)} lease(s) still hold what it needs",
                reason=ERROR_REASONS["LEASE_CONFLICT"],
                conflicts=blocked,
                recovered_stale=recovered,
                renewal_overdue=expiry["overdue"],
            )
        revision = resolve_revision(root, intent["base_revision"]) if apply else None
        granted = [
            {
                "lease_id": f"lease-{uuid.uuid4().hex[:12]}",
                "lane": lane,
                "exclusive_group": exclusive_group_of(document, lane),
                "owner": owner,
                "owner_pid": identity["pid"],
                "owner_machine": identity["machine"],
                "owner_process_start": identity["started_at"],
                "work_order": intent["work_order"],
                "write_scope": intent["write_scope"] or [intent["work_order"]],
                "acquired_at": now,
                "expires_at": expires_at,
                "heartbeat_at": now,
                "renewals": 0,
                "recoverable_after": _in_minutes(ttl_minutes + CROSS_MACHINE_GRACE_MINUTES),
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

    ungrouped = sorted({item["lane"] for item in granted if not item["exclusive_group"]})
    ungrouped_note = (
        f"{', '.join(ungrouped)} belong to no exclusive group in leases.json, so each excludes only its own "
        "lane and nothing else contends with it. Check the spelling against the route registry before relying "
        "on it for protection."
        if ungrouped
        else None
    )

    if not apply:
        return {
            "schema": "forge.execution-acquire/v1",
            "mode": "dry-run",
            "project": str(root),
            "work_order": intent["work_order"],
            "owner": owner,
            "isolation_mode": intent["mode"],
            "recovered_stale": recovered,
            "renewal_overdue": expiry["overdue"],
            "conflicts": [],
            "plan": _plan(intent, owner, None),
            "leases": [],
            "ungrouped_lanes": ungrouped,
            "ungrouped_note": ungrouped_note,
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
        "renewal_overdue": expiry["overdue"],
        "conflicts": [],
        "plan": _plan(intent, owner, revision),
        "leases": granted,
        "ungrouped_lanes": ungrouped,
        "ungrouped_note": ungrouped_note,
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


def _remove_worktree(root: Path, workspace: str, branch: str) -> str | None:
    """Discard the workspace, reporting what survived instead of assuming it did not."""
    return _undo_worktree(root, workspace, branch)


def _release_ids(
    root: Path,
    lease_ids: list[str],
    status: str,
    note: str,
    from_states: tuple[str, ...] = (ACTIVE,),
    unreleased: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    with StateMutex(root) as _mutex:
        document = read_lease_state(root)
        released: list[dict[str, Any]] = []
        for lease in document.get("leases", []):
            if str(lease.get("lease_id")) in lease_ids and str(lease.get("status")) in from_states:
                lease["status"] = status
                lease["release_note"] = note
                if status in HOLDING_STATES:
                    lease["unreleased"] = unreleased or []
                    lease.pop("released_at", None)
                else:
                    lease["released_at"] = utc_now()
                    lease.pop("unreleased", None)
                released.append(lease)
        write_lease_state(root, document)
    return released


def _teardown_external(root: Path, isolation: dict[str, Any], discards_workspace: bool) -> dict[str, Any]:
    """Free every external resource the lease took, and report exactly what survived.

    Git LFS locks and worktrees live outside the ledger, so a teardown Forge only
    attempted is not a teardown that happened. What could not be freed is named
    here and keeps its lease quarantined rather than being written off.
    """
    mode = str(isolation.get("mode", "read-only"))
    unlocked: list[str] = []
    unreleased: list[dict[str, str]] = []
    if mode == "lfs-lock":
        for target in isolation.get("lock_targets", []):
            completed = git(root, "lfs", "unlock", str(target))
            if completed.returncode == 0:
                unlocked.append(str(target))
            else:
                unreleased.append(
                    {
                        "kind": "lfs-lock",
                        "target": str(target),
                        "detail": (completed.stderr or completed.stdout or "").strip(),
                    }
                )
    workspace_removed = None
    if discards_workspace:
        failure = _remove_worktree(root, str(isolation.get("workspace")), str(isolation.get("branch")))
        workspace_removed = failure is None
        if failure:
            unreleased.append(
                {"kind": "git-worktree", "target": str(isolation.get("workspace")), "detail": failure}
            )
    return {
        "unlocked": unlocked,
        "unreleased": unreleased,
        "workspace_removed": workspace_removed,
    }


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
            "lease_status": str(held[0].get("status")),
            "workspace_retained": mode == "git-worktree" and not discards_workspace,
            "workspace": str(isolation.get("workspace")) if mode == "git-worktree" and not discards_workspace else None,
            "plan": teardown,
            "released": [],
            "unlocked": [],
            "unreleased": [],
            "note": None,
        }

    lease_ids = [str(lease.get("lease_id")) for lease in held]
    _release_ids(root, lease_ids, RELEASING, f"releasing on outcome {outcome}")
    teardown_result = _teardown_external(root, isolation, discards_workspace)
    unreleased = teardown_result["unreleased"]
    if unreleased:
        released = _release_ids(
            root,
            lease_ids,
            ORPHANED,
            f"outcome {outcome}, but {len(unreleased)} external resource(s) could not be freed",
            from_states=(RELEASING,),
            unreleased=unreleased,
        )
    else:
        released = _release_ids(
            root, lease_ids, "RELEASED", f"released on outcome {outcome}", from_states=(RELEASING,)
        )
    return {
        "schema": "forge.execution-release/v1",
        "mode": "apply",
        "project": str(root),
        "work_order": work_order,
        "outcome": outcome,
        "isolation_mode": mode,
        "lease_status": ORPHANED if unreleased else "RELEASED",
        "workspace_retained": mode == "git-worktree" and not discards_workspace,
        "workspace": str(isolation.get("workspace")) if mode == "git-worktree" and not discards_workspace else None,
        "plan": teardown,
        "released": released,
        "unlocked": teardown_result["unlocked"],
        "unreleased": unreleased,
        "note": (
            f"{len(unreleased)} external resource(s) could not be freed, so these leases are "
            f"{ORPHANED} rather than released and their write scope stays quarantined. No writer may take "
            "the lane until `forge.py exec reconcile` frees what is listed."
            if unreleased
            else None
        ),
    }


def reconcile(root: Path, work_order: str, apply: bool) -> dict[str, Any]:
    """Retry the external teardown a release could not finish, and free the lane only if it works.

    Also recovers a lease left mid-release by a crash. Retrying an unlock is safe
    because it is idempotent; discarding a workspace is not, and an interrupted
    release never recorded the outcome that would have earned the discard. So a
    worktree is removed here only when the release already named it as what it
    could not remove.
    """
    document = read_lease_state(root)
    stuck = [
        lease
        for lease in document.get("leases", [])
        if str(lease.get("work_order")) == work_order and str(lease.get("status")) in (ORPHANED, RELEASING)
    ]
    if not stuck:
        raise _fail(
            f"Work order {work_order!r} holds nothing awaiting reconciliation",
            reason=ERROR_REASONS["LEASE_UNKNOWN"],
        )
    isolation = stuck[0].get("isolation") or {}
    outstanding = [item for lease in stuck for item in (lease.get("unreleased") or [])]
    targets = [item for item in outstanding if item.get("kind") == "lfs-lock"]
    worktree_stuck = any(item.get("kind") == "git-worktree" for item in outstanding)
    plan = [{"step": f"retry-{item.get('kind')}", "detail": str(item.get("target"))} for item in outstanding]
    if not outstanding:
        plan = [{"step": "retry-teardown", "detail": "release was interrupted before it recorded what survived"}]

    if not apply:
        return {
            "schema": "forge.execution-reconcile/v1",
            "mode": "dry-run",
            "project": str(root),
            "work_order": work_order,
            "plan": plan,
            "outstanding": outstanding,
            "cleared": [],
            "still_held": [],
            "lease_status": str(stuck[0].get("status")),
        }

    retry_isolation = {
        "mode": isolation.get("mode"),
        "workspace": isolation.get("workspace"),
        "branch": isolation.get("branch"),
        "lock_targets": [item["target"] for item in targets] if outstanding else isolation.get("lock_targets", []),
    }
    result = _teardown_external(root, retry_isolation, worktree_stuck)
    still_held = result["unreleased"]
    lease_ids = [str(lease.get("lease_id")) for lease in stuck]
    if still_held:
        _release_ids(
            root,
            lease_ids,
            ORPHANED,
            f"reconcile freed {len(result['unlocked'])}, {len(still_held)} still held",
            from_states=(ORPHANED, RELEASING),
            unreleased=still_held,
        )
        raise _fail(
            f"Reconciling {work_order!r} could not free {len(still_held)} external resource(s); the lane stays "
            "quarantined",
            reason=ERROR_REASONS["RECONCILE_INCOMPLETE"],
            still_held=still_held,
            cleared=result["unlocked"],
        )
    _release_ids(
        root, lease_ids, "RELEASED", "reconciled; every external resource is free", from_states=(ORPHANED, RELEASING)
    )
    return {
        "schema": "forge.execution-reconcile/v1",
        "mode": "apply",
        "project": str(root),
        "work_order": work_order,
        "plan": plan,
        "outstanding": outstanding,
        "cleared": result["unlocked"],
        "still_held": [],
        "lease_status": "RELEASED",
    }


def renew(root: Path, work_order: str, apply: bool, ttl_minutes: int = LEASE_TTL_MINUTES) -> dict[str, Any]:
    """Extend the lease a still-working owner holds, and record that it is alive.

    Work that outruns the TTL is normal at production scale. Renewing is how a
    worker says so; without it the only evidence of life is the owning process,
    which is checkable on one machine but not from another.
    """
    with StateMutex(root) as _mutex:
        document = read_lease_state(root)
        held = [
            lease
            for lease in document.get("leases", [])
            if str(lease.get("work_order")) == work_order and lease.get("status") == ACTIVE
        ]
        if not held:
            raise _fail(
                f"No active lease is held for work order {work_order!r}, so there is nothing to renew",
                reason=ERROR_REASONS["LEASE_NOT_RENEWABLE"],
            )
        now = utc_now()
        expires_at = _in_minutes(ttl_minutes)
        recoverable_after = _in_minutes(ttl_minutes + CROSS_MACHINE_GRACE_MINUTES)
        if apply:
            for lease in held:
                lease["heartbeat_at"] = now
                lease["expires_at"] = expires_at
                lease["recoverable_after"] = recoverable_after
                lease["renewals"] = int(lease.get("renewals", 0)) + 1
            write_lease_state(root, document)
    return {
        "schema": "forge.execution-renew/v1",
        "mode": "apply" if apply else "dry-run",
        "project": str(root),
        "work_order": work_order,
        "renewed": [str(lease.get("lease_id")) for lease in held] if apply else [],
        "lanes": [str(lease.get("lane")) for lease in held],
        "heartbeat_at": now if apply else None,
        "expires_at": expires_at if apply else None,
        "renewals": [int(lease.get("renewals", 0)) for lease in held],
    }


def supervise(root: Path, holder: str, lanes: list[str], apply: bool) -> dict[str, Any]:
    """Enter the lane system from any workflow: sweep what is dead, say what is takeable.

    Acquiring, releasing, renewing and reconciling are four verbs a workflow had
    to sequence correctly by hand, and thirty of the thirty-one never sequenced
    them at all. This is the one call that stands in front of them. It recovers
    what an exited owner left, reports every lane that cannot be entered and why,
    and refuses when a lane the caller says it needs was abandoned rather than
    released — a fact `lease_conflict` alone does not distinguish, because a lane
    someone is working in and a lane someone died in need different answers.

    A caller naming no lane is not a caller that forgot: holds_no_lane is written
    down, so a workflow that legitimately takes nothing is distinguishable from
    one that never considered the question.
    """
    with StateMutex(root) as _mutex:
        document = read_lease_state(root)
        expiry = expire_stale_leases(document)
        if apply and (expiry["recovered"] or expiry["quarantined"]):
            write_lease_state(root, document)

    wanted = [str(lane) for lane in lanes if str(lane).strip()]
    blocking = {lane: lease_conflicts(document, lane, [], "project-exclusive") for lane in wanted}
    abandoned = [
        {**item, "declared_by": holder, "needed_lane": lane}
        for lane in wanted
        for item in blocking[lane]
        if str(item.get("status")) == ORPHANED
    ]
    report = {
        "schema": "forge.lane-supervision/v1",
        "mode": "apply" if apply else "dry-run",
        "project": str(root),
        "holder": holder,
        "declared_lanes": wanted,
        "holds_no_lane": not wanted,
        "recovered": expiry["recovered"],
        "quarantined": expiry["quarantined"]
        + [
            {
                "lease_id": lease.get("lease_id"),
                "lane": lease.get("lane"),
                "work_order": lease.get("work_order"),
                "unreleased": lease.get("unreleased", []),
                "remedy": f"`forge.py exec reconcile --project {root} --work-order {lease.get('work_order')} --apply`",
            }
            for lease in document.get("leases", [])
            if str(lease.get("status")) == ORPHANED and lease.get("lease_id") not in {
                item["lease_id"] for item in expiry["quarantined"]
            }
        ],
        "abandoned_workspaces": expiry["abandoned"],
        "renewal_overdue": expiry["overdue"],
        "interrupted_release": [
            {
                "lease_id": lease.get("lease_id"),
                "lane": lease.get("lane"),
                "work_order": lease.get("work_order"),
                "remedy": f"`forge.py exec reconcile --project {root} --work-order {lease.get('work_order')} --apply`",
            }
            for lease in document.get("leases", [])
            if str(lease.get("status")) == RELEASING
        ],
        "blocked": {lane: rows for lane, rows in blocking.items() if rows},
        "enterable": [lane for lane in wanted if not blocking[lane]],
    }
    if abandoned:
        raise _fail(
            f"{len(abandoned)} lane {holder!r} declared it needs was left behind by a holder that exited "
            "without freeing what it took, so supervision cannot hand it over as clean",
            reason=ERROR_REASONS["LANE_ABANDONED"],
            abandoned=abandoned,
            report=report,
        )
    return report


def status(root: Path) -> dict[str, Any]:
    """Report what is held right now, why, and what is holding a lane it no longer earns."""
    document = read_lease_state(root)
    moment = _parse_time(utc_now())
    active = [lease for lease in document.get("leases", []) if lease.get("status") == ACTIVE]
    quarantined = [lease for lease in document.get("leases", []) if str(lease.get("status")) == ORPHANED]
    mid_release = [lease for lease in document.get("leases", []) if str(lease.get("status")) == RELEASING]
    past_expiry = [lease for lease in active if _parse_time(str(lease.get("expires_at", ""))) <= moment]
    table = process_table() if past_expiry else {"resolved": True, "processes": [], "mechanism": None}
    overdue = []
    recoverable = []
    for lease in past_expiry:
        liveness = owner_is_alive(lease, table)
        entry = {
            "lease_id": lease.get("lease_id"),
            "lane": lease.get("lane"),
            "work_order": lease.get("work_order"),
            "expires_at": lease.get("expires_at"),
            "heartbeat_at": lease.get("heartbeat_at"),
            "owner_alive": liveness["alive"],
            "detail": liveness["detail"],
        }
        (overdue if liveness["alive"] is not False else recoverable).append(entry)
    return {
        "schema": "forge.execution-status/v1",
        "project": str(root),
        "active": active,
        "lane_groups": {
            str(lease.get("lane")): exclusive_group_of(document, str(lease.get("lane")))
            for lease in active + quarantined
        },
        "expired_awaiting_recovery": [entry["lease_id"] for entry in recoverable],
        "renewal_overdue": overdue,
        "quarantined": [
            {
                "lease_id": lease.get("lease_id"),
                "lane": lease.get("lane"),
                "work_order": lease.get("work_order"),
                "unreleased": lease.get("unreleased", []),
                "remedy": f"`forge.py exec reconcile --project {root} --work-order {lease.get('work_order')} --apply`",
            }
            for lease in quarantined
        ],
        "interrupted_release": [lease.get("lease_id") for lease in mid_release],
        "process_inspection": {"resolved": table.get("resolved"), "mechanism": table.get("mechanism")},
        "exclusive_groups": document.get("exclusive_groups", {}),
        "state_path": str(lease_state_path(root)),
    }
