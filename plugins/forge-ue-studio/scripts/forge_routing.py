"""Which provider earns a bounded work order, and on what evidence."""

from __future__ import annotations

import datetime as dt
import difflib
import json
import os
import platform
import re
import sys
import time
from pathlib import Path
from typing import Any

import forge_executor as executor
from forge_api_index import ApiIndexError, api_call_names
from forge_core import ERROR_REASON, find_uproject, is_available, EXIT_CONTRACT, EXIT_USAGE, RESIDENT_PROVIDER, fail, load_json, plugin_names, plugin_root, project_root, utc_now
from forge_hosts import active_profile
from forge_mcp import catalog_tool_names, mcp_capability_contracts, mcp_capability_index, project_engine_version


ISOLATION_STRENGTH = ("read-only", "git-worktree", "lfs-lock", "project-exclusive")


ROUTE_DECISIONS_SCHEMA = "forge.route-decisions/v1"


WORK_ORDERS_SCHEMA = "forge.work-orders/v1"


DEFAULT_FRESHNESS_MINUTES = 30


PROCEDURE_SCHEMA = "forge.procedure/v1"


def route_policy() -> dict[str, Any]:
    return load_json(plugin_root() / "dependencies" / "route-policy.json")


def procedures_path() -> Path:
    return plugin_root() / "doctrine" / "procedures.json"


def procedures() -> dict[str, Any]:
    document = load_json(procedures_path())
    body = document.get("procedures")
    return body if isinstance(body, dict) else {}


def capability_lanes(capabilities: list[str]) -> dict[str, str]:
    index = mcp_capability_index()
    return {
        str(item): str(index[str(item)].get("lane"))
        for item in capabilities
        if str(item) in index
    }


def _engine_version(value: str) -> tuple[int, ...] | None:
    parts = value.strip().split(".")
    return tuple(int(part) for part in parts) if parts and all(part.isdigit() for part in parts) else None


def engine_prerequisite_gaps(root: Path, capabilities: list[str]) -> list[dict[str, Any]]:
    """Every route prerequisite this project does not meet for the capabilities named.

    `requires_engine` states what a route needs before it can serve anything: a
    minimum engine and the `.uproject` plugins that expose its surface. Read
    here, a step that cannot run is refused before a lease is taken rather than
    part-way through the procedure that needed it. A project with no `.uproject`
    and an engine association that is not a version number are both unknowns,
    not shortfalls, and nothing is claimed about them.
    """
    uproject = find_uproject(root)
    if uproject is None:
        return []
    enabled = set(plugin_names(uproject))
    association = str(project_engine_version(uproject) or "")
    version = _engine_version(association)
    index = mcp_capability_index()
    gaps: list[dict[str, Any]] = []
    for name in sorted({str(item) for item in capabilities if str(item).strip()}):
        route = index.get(name) or {}
        required = route.get("requires_engine") or {}
        minimum = _engine_version(str(required.get("min_version", "")))
        if version and minimum and version < minimum:
            gaps.append({
                "capability": name,
                "route": route.get("id"),
                "requirement": "min_version",
                "required": str(required.get("min_version")),
                "found": association,
            })
        missing = sorted(str(item) for item in required.get("uproject_plugins", []) if str(item) not in enabled)
        if missing:
            gaps.append({
                "capability": name,
                "route": route.get("id"),
                "requirement": "uproject_plugins",
                "required": missing,
                "found": sorted(enabled),
            })
    return gaps


def procedure_for(task_class: str) -> dict[str, Any] | None:
    body = procedures().get(str(task_class))
    if not isinstance(body, dict):
        return None
    steps = body.get("steps", [])
    lanes = capability_lanes(list(body.get("capabilities", [])))
    spanned = sorted({lane for lane in lanes.values() if lane})
    return {
        **body,
        "schema": PROCEDURE_SCHEMA,
        "task_class": str(task_class),
        "capability_lanes": lanes,
        "lanes": spanned,
        "packets": len(spanned),
        "packet_split": [
            {
                "lane": lane,
                "capabilities": sorted(name for name, value in lanes.items() if value == lane),
                "steps": [
                    number
                    for number, step in enumerate(steps, start=1)
                    if lanes.get(str(step.get("capability"))) == lane
                ],
            }
            for lane in spanned
        ],
    }


def procedure_resolution(task_class: str) -> dict[str, Any]:
    name = str(task_class)
    known = sorted(procedures())
    found = procedure_for(name)
    if found is not None:
        return {
            "task_class": name,
            "procedured": True,
            "lane": found["lane"],
            "lanes": found["lanes"],
            "packets": found["packets"],
        }
    return {
        "task_class": name,
        "procedured": False,
        "nearest": difflib.get_close_matches(name.casefold(), known, n=3, cutoff=0.7),
        "known": known,
        "note": (
            f"no build procedure covers task class {name!r}, so this packet's steps, acceptance, verification "
            "and evidence were improvised rather than taken from doctrine"
        ),
    }


def procedure_gaps(packet: dict[str, Any], procedure: dict[str, Any]) -> list[str]:
    lanes = procedure["capability_lanes"]
    declared = {str(item) for item in packet.get("capabilities", []) if str(item).strip()}
    shared = declared & set(lanes)
    task_class = procedure["task_class"]
    if not shared:
        return [
            f"the packet declares none of the {len(lanes)} capabilities the procedure for task class "
            f"{task_class!r} names, so it executes no step of it"
        ]
    held = {lanes[item] for item in shared}
    steps_by_capability: dict[str, list[int]] = {}
    for number, step in enumerate(procedure.get("steps", []), start=1):
        steps_by_capability.setdefault(str(step.get("capability")), []).append(number)
    return [
        f"the procedure for task class {task_class!r} needs {name!r} for step(s) "
        f"{', '.join(str(item) for item in steps_by_capability.get(name, []))} on lane {lanes[name]!r}, which this "
        f"packet already takes, and the packet does not declare it"
        for name in sorted(set(lanes) - declared)
        if lanes[name] in held
    ]


def route_decisions_path(root: Path) -> Path:
    return root / ".forge" / "state" / "route-decisions.json"


def decision_freshness_minutes(policy: dict[str, Any] | None = None) -> int:
    settings = (policy or route_policy()).get("route_decision") or {}
    return int(settings.get("freshness_minutes", DEFAULT_FRESHNESS_MINUTES))


def read_route_decisions(root: Path) -> dict[str, Any]:
    """Read the decision ledger. Absent is empty, malformed is a refusal."""
    path = route_decisions_path(root)
    if not path.is_file():
        return {"schema": ROUTE_DECISIONS_SCHEMA, "decisions": [], "updated_at": None}
    document = load_json(path)
    if not isinstance(document.get("decisions"), list):
        raise fail(
            f"{path} does not carry a {ROUTE_DECISIONS_SCHEMA} decisions array",
            reason=ERROR_REASON["CONTRACT_INVALID"],
            code=EXIT_CONTRACT,
        )
    return document


def canonical_order(packet_registry: dict[str, Any], work_order: str) -> str:
    """The registered id behind a work order, resolving one alias hop."""
    aliases = {str(item.get("alias")): str(item.get("canonical")) for item in packet_registry.get("aliases", [])}
    return aliases.get(work_order, work_order)


def canonical_order_for(root: Path, work_order: str) -> str:
    """The registered id behind a work order, resolved against this project's registry.

    Every ledger keyed by work order resolves through here, so an alias and the
    id it stands for can never open two entries for one order.
    """
    path = root / ".forge" / "state" / "packet-registry.json"
    return canonical_order(load_json(path) if path.is_file() else {}, str(work_order))


JOBS_RETENTION_DEFAULT = "keep"


def jobs_root(root: Path) -> Path:
    return root / ".forge" / "jobs"


def job_dir(root: Path, work_order: str) -> Path:
    """The one folder a work order's job lives in, keyed on its canonical id.

    There is no verb segment above it. A work order is dispatched once and touched
    afterwards by verbs that never knew which workflow opened it, so a path
    composed from the caller's own verb would open a second folder for one order —
    the defect this repository has already fixed twice under other names. The verb
    is recorded inside the brief, where it is a field rather than a path segment.
    """
    return jobs_root(root) / canonical_order_for(root, str(work_order))


def jobs_retention(root: Path) -> str:
    """How long a finished job folder is kept, read at the moment one is written."""
    path = root / ".forge" / "config.json"
    settings = (load_json(path).get("jobs") or {}) if path.is_file() else {}
    return str(settings.get("retention", JOBS_RETENTION_DEFAULT))


def _referral_slug(referral: Any) -> str:
    for key in ("id", "ref", "name", "path", "source"):
        value = str(referral.get(key, "")).strip() if isinstance(referral, dict) else ""
        if value:
            return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "referral"
    return "referral"


def _brief_section(title: str, items: list[str]) -> list[str]:
    return [f"## {title}", "", *(f"- {item}" for item in items), ""] if items else []


def render_brief(
    packet: dict[str, Any],
    procedure: dict[str, Any] | None,
    tool_access: list[dict[str, Any]],
    retention: str,
    verb: str,
) -> str:
    """Compose the brief from the registries, at the only moment their answer is true.

    Nothing here is authored: the ordered steps, non-goals, acceptance, verification
    and evidence come from the procedure the packet's task class resolves to, and
    the tool and call names come from the catalogue and the API index as they
    resolve right now. Restating any of it in a file of its own would make this a
    third source of truth, and route availability in particular is only knowable
    while the editor is in the state it is in.
    """
    isolation = packet.get("isolation") or {}
    source = "the build procedure for this task class" if procedure else "the packet itself"
    body = procedure if procedure else packet
    lines = [
        f"# {packet.get('work_order')}",
        "",
        str(packet.get("objective", "")),
        "",
        f"- Opened by: `{verb}`",
        f"- Task class: `{packet.get('task_class')}`"
        + ("" if procedure else " — no build procedure covers it, so the sections below are improvised"),
        f"- Role: `{packet.get('role')}`",
        f"- Revision: `{packet.get('revision')}`",
        f"- Isolation: `{isolation.get('mode')}` from `{isolation.get('base_revision')}`",
        f"- Leases: {', '.join(f'`{item}`' for item in packet.get('leases', [])) or 'none'}",
        f"- Write scope: {', '.join(f'`{item}`' for item in packet.get('write_scope', [])) or 'none'}",
        f"- Retention: `{retention}` — finished jobs are not swept",
        f"- Rendered from {source} at {utc_now()}",
        "",
    ]
    steps = list(procedure.get("steps", [])) if procedure else []
    if steps:
        lines += ["## Steps", ""]
        for number, step in enumerate(steps, start=1):
            lines += [
                f"{number}. {step.get('does', '')}",
                f"   - Produces: {step.get('produces', '')}",
                f"   - Capability: `{step.get('capability')}`",
                "",
            ]
    lines += [
        "## Tools and routes",
        "",
        "| Capability | Lane | Lease | Route | Reachable now | MCP tools |",
        "|---|---|---|---|---|---|",
    ]
    for row in tool_access:
        lines.append(
            "| `{capability}` | {lane} | {lease} | {provider} | {bound} | {tools} |".format(
                capability=row.get("capability"),
                lane=row.get("lane") or "—",
                lease=row.get("lease") or "—",
                provider=row.get("provider"),
                bound=str(row.get("status") or ("bound" if row.get("bound") else "unbound")),
                tools=", ".join(f"`{name}`" for name in row.get("tools", [])) or "—",
            )
        )
    lines.append("")
    for row in tool_access:
        if row.get("api_calls"):
            lines += [
                f"Python API calls for `{row['capability']}` on `{row.get('provider')}`:",
                "",
                ", ".join(f"`{name}`" for name in row["api_calls"]),
                "",
            ]
    for title, field in (
        ("Non-goals", "non_goals"),
        ("Acceptance", "acceptance"),
        ("Verification", "verification"),
        ("Evidence", "evidence"),
    ):
        lines += _brief_section(title, [str(item) for item in body.get(field, [])])
    return "\n".join(lines).rstrip() + "\n"


def write_job(
    root: Path,
    packet: dict[str, Any],
    procedure: dict[str, Any] | None,
    tool_access: list[dict[str, Any]],
    verb: str,
) -> dict[str, Any]:
    """Put on disk what this job was given, before anything is acquired for it.

    Before, because a folder that fails to appear after the leases are taken leaves
    a worker holding the project super-lock with nothing to read. A folder written
    for an acquisition that then fails is kept rather than removed: it holds no
    lease and grants nothing, the lease ledger remains the only authority on what
    is held, and it is the record of what was attempted and refused — which is the
    claim this tree exists to make checkable. The next dispatch of the same order
    renders over it from the registries as they read then.
    """
    directory = job_dir(root, str(packet.get("work_order", "")))
    context = directory / "context"
    context.mkdir(parents=True, exist_ok=True)
    for stale in sorted(context.glob("*.json")):
        stale.unlink()
    written: list[str] = []
    for number, referral in enumerate(packet.get("referrals", []), start=1):
        name = f"{number:02d}-{_referral_slug(referral)}.json"
        (context / name).write_text(json.dumps(referral, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(name)
    (directory / "packet.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    retention = jobs_retention(root)
    (directory / "brief.md").write_text(
        render_brief(packet, procedure, tool_access, retention, verb), encoding="utf-8"
    )
    return {
        "job": str(directory),
        "brief": str(directory / "brief.md"),
        "packet": str(directory / "packet.json"),
        "context": written,
        "opened_by": verb,
        "retention": retention,
    }


def write_job_result(root: Path, work_order: str, result: dict[str, Any]) -> Path:
    """File the attempt result where the brief that asked for it lives."""
    directory = job_dir(root, work_order)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "result.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def release_attempt_result(root: Path, work_order: str, outcome: str, release: dict[str, Any]) -> dict[str, Any]:
    """The attempt result a release can honestly write when the worker returned none.

    It is the `forge.attempt-result/v1` every other result is; a second shape for
    one artifact is how a reader ends up with two answers to one question. What it
    claims is only what the release observed — the outcome the caller passed, what
    the teardown freed and what it could not — and it says so, so a job folder that
    holds one of these is visibly a job whose worker filed nothing.
    """
    released = release.get("released") or []
    unreleased = release.get("unreleased") or []
    return {
        "schema": "forge.attempt-result/v1",
        "work_order": canonical_order_for(root, work_order),
        "attempt": 1,
        "provider": str(next((item.get("owner") for item in released if item.get("owner")), RESIDENT_PROVIDER)),
        "verdict": "PASS" if outcome == "passed" else "FAIL",
        "result_source": "release-observation",
        "observed_facts": [
            f"the release recorded outcome {outcome!r} with lease status {release.get('lease_status')!r}",
            f"isolation mode {release.get('isolation_mode')!r} was torn down, freeing "
            f"{len(release.get('unlocked') or [])} external resource(s) and leaving {len(unreleased)} held",
        ],
        "inferences": [],
        "findings": [],
        "touched": sorted({str(item) for lease in released for item in lease.get("write_scope", [])}),
        "evidence": [
            {"kind": "lease-ledger", "path": str(executor.lease_state_path(root)),
             "detail": "what the release freed and what stayed quarantined"},
            {"kind": "work-order-ledger", "path": str(work_orders_path(root)),
             "detail": "the terminal state this outcome moved the order to"},
        ],
        "verification": [],
        "residual_risk": [str(release["note"])] if release.get("note") else [],
        "next_action": (
            f"run `forge.py exec reconcile --work-order {work_order}` to free what the release could not"
            if unreleased
            else "pass the worker's own result to `exec release --result <path>` so this folder holds what the "
                 "worker reported rather than only what the release observed"
        ),
    }


def record_route_decision(root: Path, decision: dict[str, Any], owner: str | None = None) -> dict[str, Any]:
    """Write the decision under its canonical work order, replacing any earlier one."""
    path = route_decisions_path(root)
    order = str(decision.get("canonical_work_order", ""))
    entry = {
        "canonical_work_order": order,
        "recorded_at": utc_now(),
        "recorded_by": owner,
        "decision": decision,
    }
    with executor.StateMutex(root, state_path=path) as _mutex:
        document = read_route_decisions(root)
        document["schema"] = ROUTE_DECISIONS_SCHEMA
        document["decisions"] = [
            item for item in document["decisions"] if str(item.get("canonical_work_order")) != order
        ] + [entry]
        document["updated_at"] = entry["recorded_at"]
        executor.write_state_atomically(path, document)
    return entry


def resolve_route_decision(root: Path, work_order: str, freshness_minutes: int | None = None) -> dict[str, Any]:
    """The recorded decision authorising this work order, or the reason there is none.

    Acquisition reads the decision rather than being handed one, so an agent that
    skipped routing cannot acquire by omitting a flag, and a decision the
    environment has outlived cannot authorise a lane it no longer describes.
    """
    order = canonical_order_for(root, work_order)
    document = read_route_decisions(root)
    entry = next(
        (item for item in document["decisions"] if str(item.get("canonical_work_order")) == order),
        None,
    )
    if entry is None:
        raise fail(
            f"No routing decision is recorded for work order {order!r}; run "
            f"`forge.py route --project {root} --request <request> --apply` before acquiring, or pass "
            "--route for a decision stored elsewhere",
            reason=ERROR_REASON["ROUTE_DECISION_MISSING"],
            code=EXIT_CONTRACT,
            work_order=order,
            ledger=str(route_decisions_path(root)),
        )
    window = decision_freshness_minutes() if freshness_minutes is None else freshness_minutes
    recorded_at = str(entry.get("recorded_at", ""))
    age_minutes = (dt.datetime.fromisoformat(utc_now()) - _parse_moment(recorded_at)).total_seconds() / 60
    if age_minutes > window:
        raise fail(
            f"The routing decision for {order!r} was recorded {int(age_minutes)} minutes ago and the freshness "
            f"window is {window}; the routes it scored can have swapped availability since. Re-run route",
            reason=ERROR_REASON["ROUTE_DECISION_STALE"],
            code=EXIT_CONTRACT,
            work_order=order,
            recorded_at=recorded_at,
            freshness_minutes=window,
        )
    return entry


def resolve_decision_for(root: Path, packet: dict[str, Any], route_value: str | None) -> dict[str, Any]:
    """The routing decision authorising this packet, from the ledger or an override."""
    if route_value:
        override = Path(route_value).expanduser().resolve()
        return {
            "decision": load_json(override),
            "source": str(override),
            "recorded_at": None,
            "canonical_work_order": None,
        }
    entry = resolve_route_decision(root, str(packet.get("work_order", "")))
    return {
        "decision": entry.get("decision") or {},
        "source": str(route_decisions_path(root)),
        "recorded_at": entry.get("recorded_at"),
        "canonical_work_order": str(entry.get("canonical_work_order", "")),
    }


def route_drift(decision: dict[str, Any], live: list[dict[str, Any]]) -> list[str]:
    """Every way the routes available now differ from the ones the decision was scored against.

    A decision records what was reachable when routing ran. Admission happens
    later, and in between an editor can open or close, a server can stop
    answering, or a lane can change hands. Acquiring on the recorded answer alone
    would hold protection for a route that is no longer the one being used.
    """
    recorded = {str(item.get("capability")): item for item in decision.get("tool_access", [])}
    drift: list[str] = []
    for item in live:
        name = str(item["capability"])
        was = recorded.get(name)
        if was is None:
            drift.append(f"capability {name!r} is required now but the decision never scored it")
            continue
        if bool(was.get("bound")) != bool(item["bound"]):
            state = "bound" if item["bound"] else "unbound"
            drift.append(
                f"capability {name!r} was {'bound' if was.get('bound') else 'unbound'} when routing ran and is "
                f"{state} now"
            )
            continue
        if item["bound"] and was.get("lease") != item.get("lease"):
            drift.append(
                f"capability {name!r} resolved to lease {was.get('lease')!r} when routing ran and to "
                f"{item.get('lease')!r} now"
            )
    return drift


def work_orders_path(root: Path) -> Path:
    return root / ".forge" / "state" / "work-orders.json"


BLOCKED_LANE_DEFAULTS = {"posture": "autonomous", "interrupt_seconds": 60, "consecutive_failure_limit": 3}


def blocked_lane_policy(policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """The posture Forge takes on a lane whose ownership it could not determine."""
    settings = dict(BLOCKED_LANE_DEFAULTS)
    settings.update((policy or route_policy()).get("blocked_lane") or {})
    return settings


def lane_failure_counts(root: Path) -> dict[str, int]:
    path = work_orders_path(root)
    document = load_json(path) if path.is_file() else {}
    return {str(lane): int(row.get("consecutive", 0)) for lane, row in (document.get("blocked_lanes") or {}).items()}


WORK_ORDER_TERMINAL_STATES = ("ACCEPTED", "REJECTED")


def read_work_orders(root: Path) -> dict[str, Any]:
    """The order ledger as it stands, with an absent file reading as empty.

    Two workflows opened `.forge/state/work-orders.json` by hand to answer what
    `exec status` did not report, which is the pattern this release has been
    removing: a state file read by prose is a read nothing can check.
    """
    path = work_orders_path(root)
    document = load_json(path) if path.is_file() else {}
    return {
        "path": str(path),
        "present": path.is_file(),
        "terminal_states": [str(item) for item in document.get("terminal_states") or WORK_ORDER_TERMINAL_STATES],
        "orders": [item for item in document.get("orders") or [] if isinstance(item, dict)],
        "supervision": [item for item in document.get("supervision") or [] if isinstance(item, dict)],
        "blocked_lanes": {str(lane): row for lane, row in (document.get("blocked_lanes") or {}).items()},
    }


def job_folders(root: Path) -> list[dict[str, Any]]:
    """Every job folder on disk, whatever the ledger remembers about it.

    `job_dir` composes the one canonical path, and resume composed it from each
    order's work order, which is correct and depends on the ledger being
    complete. A folder whose acquisition failed holds no order and is the record
    of what was attempted; listing the tree is how it stays findable.
    """
    base = jobs_root(root)
    if not base.is_dir():
        return []
    return [
        {
            "work_order": directory.name,
            "path": str(directory),
            "brief": (directory / "brief.md").is_file(),
            "packet": (directory / "packet.json").is_file(),
            "result": (directory / "result.json").is_file(),
            "context": sorted(path.name for path in (directory / "context").glob("*.json")),
        }
        for directory in sorted(base.iterdir())
        if directory.is_dir()
    ]


REACHABILITY_UNCHECKED = (
    "Capability routes. An action Forge offers names no capability, so whether the route serving one is "
    "bound is settled when a packet is compiled, by forge-route-work, and not here.",
    "GSD phase logic. Which phase may run is GSD's answer and is never second-guessed by this join.",
    "Abandoned workspaces. A dead worker's worktree leaves the lane free, so it is a human action to name "
    "rather than a state that blocks an action.",
)


def work_blockers(execution: dict[str, Any], ledger: dict[str, Any], policy: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Every state standing between this project and admitting more work.

    Each entry names what holds, what it holds, and the remedy that clears it,
    so an action can be shown as unreachable with its blocking state rather than
    silently dropped. A terminal order is not here: an order resting at ACCEPTED
    or REJECTED is finished, not running.
    """
    limit = int(blocked_lane_policy(policy)["consecutive_failure_limit"])
    blockers: list[dict[str, Any]] = []
    for lease in execution.get("active") or []:
        blockers.append({
            "kind": "lane_held",
            "lane": lease.get("lane"),
            "work_order": lease.get("work_order"),
            "detail": f"{lease.get('owner')} holds {lease.get('lane')} until {lease.get('expires_at')}",
            "remedy": "wait for the holder to release it, or resume the work it is doing",
        })
    for lease in execution.get("renewal_overdue") or []:
        blockers.append({
            "kind": "renewal_overdue",
            "lane": lease.get("lane"),
            "work_order": lease.get("work_order"),
            "detail": f"the owner of {lease.get('lane')} is alive and past its TTL: {lease.get('detail')}",
            "remedy": "leave it alone; work is running, and nothing may contend with it",
        })
    for row in execution.get("quarantined") or []:
        blockers.append({
            "kind": "lane_quarantined",
            "lane": row.get("lane"),
            "work_order": row.get("work_order"),
            "detail": f"{len(row.get('unreleased') or [])} external resource(s) survived a release on {row.get('lane')}",
            "remedy": str(row.get("remedy") or "run `exec reconcile --apply` through forge-route-work"),
        })
    for lease_id in execution.get("interrupted_release") or []:
        blockers.append({
            "kind": "release_interrupted",
            "lane": None,
            "work_order": None,
            "detail": f"lease {lease_id} died mid-release",
            "remedy": "run `exec reconcile --apply` through forge-route-work",
        })
    terminal = set(ledger.get("terminal_states") or WORK_ORDER_TERMINAL_STATES)
    for order in ledger.get("orders") or []:
        status = str(order.get("status", ""))
        if status in terminal:
            continue
        if status == "DISPATCHED":
            blockers.append({
                "kind": "order_dispatched",
                "lane": None,
                "work_order": order.get("work_order"),
                "detail": f"order {order.get('work_order')} was admitted and never released",
                "remedy": "finish or resume it through forge-resume-work before opening more work",
            })
        elif status == "BLOCKED":
            blockers.append({
                "kind": "order_blocked",
                "lane": None,
                "work_order": order.get("work_order"),
                "detail": f"order {order.get('work_order')} was refused admission",
                "remedy": str(order.get("human_action") or "read the order's human_action and act on it"),
            })
    for lane, row in sorted((ledger.get("blocked_lanes") or {}).items()):
        consecutive = int(row.get("consecutive", 0)) if isinstance(row, dict) else 0
        if consecutive >= limit:
            blockers.append({
                "kind": "lane_breaker",
                "lane": lane,
                "work_order": None,
                "detail": f"{consecutive} consecutive failed entries into {lane}, at a limit of {limit}",
                "remedy": "clear what makes entry fail; offering the lane again is how a loop starts",
            })
    return blockers


def reachability(root: Path) -> dict[str, Any]:
    """Join the lease ledger, the order ledger and the job tree into one answer.

    `forge-next` hand-joined `exec status`, `route-status` and a raw read of
    `work-orders.json` to decide whether an action it was about to offer could
    run, which made reachability a step an agent could skip and still reach the
    dispatch below it. Joined here it is data an action arrives carrying.
    """
    try:
        execution = executor.status(root)
    except executor.ExecutorError as exc:
        return {
            "readable": False,
            "detail": str(exc),
            "execution": None,
            "orders": [],
            "supervision": [],
            "blocked_lanes": {},
            "terminal_states": list(WORK_ORDER_TERMINAL_STATES),
            "work_orders": str(work_orders_path(root)),
            "jobs": [],
            "blockers": [],
            "sources": [str(executor.lease_state_path(root)), str(work_orders_path(root))],
            "not_checked": list(REACHABILITY_UNCHECKED),
        }
    ledger = read_work_orders(root)
    return {
        "readable": True,
        "detail": "",
        "execution": execution,
        "orders": ledger["orders"],
        "supervision": ledger["supervision"],
        "blocked_lanes": ledger["blocked_lanes"],
        "terminal_states": ledger["terminal_states"],
        "work_orders": ledger["path"],
        "jobs": job_folders(root),
        "blockers": work_blockers(execution, ledger),
        "sources": [str(executor.lease_state_path(root)), ledger["path"]],
        "not_checked": list(REACHABILITY_UNCHECKED),
    }


def _write_orders(root: Path, mutate) -> dict[str, Any]:
    path = work_orders_path(root)
    with executor.StateMutex(root, state_path=path) as _mutex:
        document = load_json(path) if path.is_file() else {"schema": WORK_ORDERS_SCHEMA, "orders": []}
        document.setdefault("schema", WORK_ORDERS_SCHEMA)
        document.setdefault("terminal_states", list(WORK_ORDER_TERMINAL_STATES))
        mutate(document)
        document["updated_at"] = utc_now()
        executor.write_state_atomically(path, document)
    return document


def lane_exit_note(outcome: str, lease_status: str, work_order: str, unreleased: list[dict[str, Any]]) -> str:
    """What a next session must do about the lane this order was working in."""
    if lease_status == executor.ORPHANED:
        return (
            f"{len(unreleased)} external resource(s) survived the release, so the lane is quarantined and no "
            f"writer may take it. Run `forge.py exec reconcile --work-order {work_order} --apply`"
        )
    if outcome == "failed":
        return (
            "the lane was released and is free to retake; the failure is in this order's result.json, so "
            "diagnose from there rather than by retrying into the lane"
        )
    return "the lane was released and is free to retake"


def record_release(
    root: Path,
    work_order: str,
    outcome: str,
    lease_status: str,
    release: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Move the order to the state its outcome earned, and say what became of its lane.

    Until this ran, every order Forge wrote rested at DISPATCHED forever, so a
    resume could not tell finished work from work still in flight. It still could
    not tell which lane the work had failed in, what it had been holding or what
    to do about it, so a failure inside a lane was a fact only the local runtime
    held. The lane, the leases, what would not free and the next action are
    written here so another department can plan around a known-blocked lane
    rather than discover it by collision.
    """
    status = "REJECTED" if outcome == "failed" else "ACCEPTED"
    closed_at = utc_now()
    work_order = canonical_order_for(root, work_order)
    released = list((release or {}).get("released") or [])
    unreleased = list((release or {}).get("unreleased") or [])
    lanes = [str(item.get("lane")) for item in released if item.get("lane")]

    def mutate(document: dict[str, Any]) -> None:
        orders = document.get("orders", [])
        entry = dict(next((item for item in orders if str(item.get("work_order")) == work_order), {}))
        entry.update({
            "work_order": work_order,
            "status": status,
            "outcome": outcome,
            "lease_status": lease_status,
            "closed_at": closed_at,
            "unreleased": unreleased,
            "lane_exit": lane_exit_note(outcome, lease_status, work_order, unreleased),
        })
        if lanes:
            entry["lanes"] = lanes
            entry["leases"] = [str(item.get("lease_id")) for item in released]
        document["orders"] = [item for item in orders if str(item.get("work_order")) != work_order] + [entry]

    return [item for item in _write_orders(root, mutate)["orders"] if str(item.get("work_order")) == work_order][0]


SUPERVISION_RETAINED = 20


def record_supervision(root: Path, report: dict[str, Any], refusal: str | None) -> dict[str, Any]:
    """File what a workflow declared it needed of the lane system, including nothing.

    A workflow that takes no lane and one that never considered the question look
    identical in the ledger, which is why thirty of thirty-one workflows reading
    as lane-free proves nothing. Declaring it makes the silence a decision.
    """
    entry = {
        "holder": str(report.get("holder")),
        "at": utc_now(),
        "declared_lanes": [str(lane) for lane in report.get("declared_lanes") or []],
        "holds_no_lane": bool(report.get("holds_no_lane")),
        "recovered": [str(item) for item in report.get("recovered") or []],
        "quarantined": [str(item.get("lane")) for item in report.get("quarantined") or []],
        "abandoned_workspaces": [str(item.get("workspace")) for item in report.get("abandoned_workspaces") or []],
        "refusal": refusal,
    }

    def mutate(document: dict[str, Any]) -> None:
        document["supervision"] = (list(document.get("supervision") or []) + [entry])[-SUPERVISION_RETAINED:]

    _write_orders(root, mutate)
    return entry


def record_blocked_lane(root: Path, packet: dict[str, Any], blocked: list[dict[str, Any]], decision: str) -> dict[str, Any]:
    """Persist that a lane could not be determined, and count it against the breaker.

    A refusal that leaves no trace cannot be resumed from and cannot be counted,
    so the next session repeats it and the breaker has nothing to break on.
    """
    order = canonical_order_for(root, str(packet.get("work_order", "")))
    lanes = sorted({str(item.get("lane")) for item in blocked if item.get("lane")})
    moment = utc_now()
    entry = {
        "work_order": order,
        "status": "BLOCKED",
        "decision": decision,
        "revision": packet.get("revision"),
        "role": packet.get("role"),
        "blocked_at": moment,
        "lanes": lanes,
        "capabilities": [str(item.get("capability")) for item in blocked],
        "ownership": [str(item.get("ownership")) for item in blocked],
        "human_action": next((str(item.get("human_action")) for item in blocked if item.get("human_action")), None),
    }

    def mutate(document: dict[str, Any]) -> None:
        document["orders"] = [
            item for item in document.get("orders", []) if str(item.get("work_order")) != order
        ] + [entry]
        counts = document.setdefault("blocked_lanes", {})
        for lane in lanes:
            row = counts.setdefault(lane, {"consecutive": 0})
            row["consecutive"] = int(row.get("consecutive", 0)) + 1
            row["last_at"] = moment
            row["last_work_order"] = order

    _write_orders(root, mutate)
    return entry


def clear_lane_failures(root: Path, lanes: list[str]) -> None:
    """A lane that admitted work is a lane that is working; the count starts over."""
    wanted = {str(lane) for lane in lanes if lane}
    if not wanted:
        return
    path = work_orders_path(root)
    if not path.is_file():
        return
    if not set(load_json(path).get("blocked_lanes") or {}) & wanted:
        return

    def mutate(document: dict[str, Any]) -> None:
        counts = document.get("blocked_lanes") or {}
        document["blocked_lanes"] = {lane: row for lane, row in counts.items() if lane not in wanted}

    _write_orders(root, mutate)


def _read_choice(seconds: int) -> str | None:
    """One keystroke within the window, or None when nobody answered."""
    if platform.system() == "Windows":
        import msvcrt

        deadline = time.monotonic() + seconds
        typed = ""
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                char = msvcrt.getwch()
                if ord(char) in (10, 13):
                    return typed.strip()
                typed += char
            time.sleep(0.05)
        return None
    import select

    ready, _, _ = select.select([sys.stdin], [], [], seconds)
    return sys.stdin.readline().strip() if ready else None


def _nobody_can_answer(stream) -> str:
    """Whether a prompt on this stream could actually be answered.

    stdin.isatty() alone is not enough: on Windows it reports a terminal even
    when stdin is a null device, so trusting it stalls an unattended run for the
    whole window. The prompt has to be visible on the stream it is printed to
    and answerable on stdin, and a declared CI run is neither.
    """
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        return "this run declares itself CI, so no one is watching the prompt"
    try:
        if not stream.isatty():
            return "the prompt stream is not a terminal, so the warning would not be seen"
        if not sys.stdin.isatty():
            return "stdin is not a terminal, so an answer could not be typed"
    except (AttributeError, ValueError):
        return "the prompt stream is closed"
    return ""


def confirm_autonomous_entry(lanes: list[str], seconds: int, stream=None) -> dict[str, Any]:
    """Offer a human the chance to take an undetermined lane back, then proceed.

    The prompt is on stderr because the payload on stdout has to stay
    machine-readable while it is showing, and a run nobody is watching must
    never wait for an answer that cannot arrive.
    """
    stream = stream or sys.stderr
    named = ", ".join(lanes) or "an undetermined lane"
    unattended = _nobody_can_answer(stream)
    if unattended:
        print(
            f"Problem encountered on {named} - self-diagnosing. The {seconds}s interrupt window is skipped "
            f"because {unattended}; Forge proceeds and records why.",
            file=stream,
            flush=True,
        )
        return {"choice": "proceed", "interrupted": False, "waited": False, "reason": unattended}
    print(f"Problem encountered on {named} - self-diagnosing.", file=stream, flush=True)
    print("  [1] intervene    [enter] skip the wait", file=stream, flush=True)
    print(f"  Otherwise: attempt the fix and enter the lane in {seconds}s.", file=stream, flush=True)
    answer = _read_choice(seconds)
    if answer == "1":
        return {"choice": "intervene", "interrupted": True, "waited": True, "reason": "the user intervened"}
    if answer is None:
        return {"choice": "proceed", "interrupted": False, "waited": True, "reason": f"nobody answered within {seconds}s"}
    return {"choice": "proceed", "interrupted": False, "waited": True, "reason": "the user skipped the wait"}


def decide_blocked_lane(root: Path, packet: dict[str, Any], blocked: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Whether to enter a lane whose ownership could not be determined.

    Three bounds sit between an undetermined lane and a commandlet: the posture
    the project declares, a breaker that stops an unstable editor being retried
    into a loop, and a window in which a human can take the lane back. The record
    is written either way, because a refusal nobody can resume from is repeated.
    """
    policy = blocked_lane_policy(policy)
    lanes = sorted({str(item.get("lane")) for item in blocked if item.get("lane")})
    limit = int(policy["consecutive_failure_limit"])
    counts = lane_failure_counts(root)
    tripped = sorted(lane for lane in lanes if counts.get(lane, 0) + 1 >= limit)
    posture = str(policy["posture"])

    if posture != "autonomous":
        record_blocked_lane(root, packet, blocked, "refused")
        return {"proceed": False, "posture": posture, "lanes": lanes, "prompted": False,
                "reason": f"the project's blocked_lane posture is {posture!r}, so Forge refuses rather than deciding"}
    if tripped:
        record_blocked_lane(root, packet, blocked, "breaker-tripped")
        return {"proceed": False, "posture": posture, "lanes": lanes, "prompted": False, "breaker_tripped": tripped,
                "reason": f"diagnosis has now failed {limit} times running on {', '.join(tripped)}, so Forge stops "
                          "deciding and hands the lane back rather than retrying an unstable editor into a loop"}

    answer = confirm_autonomous_entry(lanes, int(policy["interrupt_seconds"]))
    if answer["interrupted"]:
        record_blocked_lane(root, packet, blocked, "user-intervened")
        return {"proceed": False, "posture": posture, "lanes": lanes, "prompted": True,
                "reason": "the user intervened within the interrupt window"}
    record_blocked_lane(root, packet, blocked, "entered-autonomously")
    return {"proceed": True, "posture": posture, "lanes": lanes, "prompted": answer["waited"],
            "reason": answer["reason"], "risk": "entered a lane whose ownership could not be determined"}


def record_dispatch(root: Path, packet: dict[str, Any], admission: dict[str, Any], leases: list[dict[str, Any]], autonomy: dict[str, Any] | None = None, procedure: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write the order transition in the same breath as the acquisition that earned it."""
    order = canonical_order_for(root, str(packet.get("work_order", "")))
    entry = {
        "work_order": order,
        "status": "DISPATCHED",
        "revision": packet.get("revision"),
        "role": packet.get("role"),
        "dispatched_at": utc_now(),
        "lanes": [str(item.get("lane")) for item in leases],
        "leases": [str(item.get("lease_id")) for item in leases],
        "isolation_mode": str((packet.get("isolation") or {}).get("mode", "")),
        "route_source": admission["source"],
        "route_recorded_at": admission["recorded_at"],
        "entered_undetermined_lane": autonomy if autonomy and autonomy.get("proceed") else None,
        "task_class": packet.get("task_class"),
        "procedure": procedure or procedure_resolution(str(packet.get("task_class", ""))),
    }
    def mutate(document: dict[str, Any]) -> None:
        document["orders"] = [
            item for item in document.get("orders", []) if str(item.get("work_order")) != order
        ] + [entry]

    _write_orders(root, mutate)
    return entry


def _parse_moment(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def resolve_tool_access(
    contracts: dict[str, Any],
    required_capabilities: set[str],
    task_class: str | None = None,
) -> list[dict[str, Any]]:
    """What each required capability resolves to right now, and what holding it would take.

    A capability no route serves is not an error: the resident host or an engine
    prerequisite answers it. A capability a route serves but cannot reach today is
    the case the declared fallback exists for, and it must be reported rather than
    dispatched into.

    `tools` are the catalogued MCP call names a live route exposes; `api_calls` are
    the Unreal Python call names the index assorts to this task class, which is the
    only surface an editor-closed route has. Both carry names rather than detail,
    and the agent pulls one class's methods on demand.
    """
    resolved: list[dict[str, Any]] = []
    for name in sorted(required_capabilities):
        contract = contracts.get(name)
        if contract is None:
            resolved.append(
                {
                    "capability": name,
                    "routed": False,
                    "bound": True,
                    "provider": RESIDENT_PROVIDER,
                    "kind": "resident",
                    "lane": None,
                    "lease": None,
                    "isolation_mode": None,
                    "fallbacks": [],
                    "tool_surface": None,
                    "tools": [],
                    "api_calls": [],
                    "detail": "no typed route serves this capability; the resident host or an engine prerequisite answers it",
                }
            )
            continue
        bound = is_available(contract.get("status"))
        try:
            api_calls = api_call_names(contract.get("provider"), str(task_class), [name]) if task_class else []
        except ApiIndexError:
            api_calls = []
        resolved.append(
            {
                "capability": name,
                "routed": True,
                "bound": bound,
                "provider": contract.get("provider"),
                "kind": contract.get("kind"),
                "status": contract.get("status"),
                "ownership": contract.get("ownership"),
                "human_action": contract.get("human_action"),
                "lane": contract.get("lane"),
                "lease": contract.get("lease"),
                "isolation_mode": contract.get("isolation_mode"),
                "fallbacks": contract.get("fallbacks", []),
                "tool_surface": contract.get("tool_surface"),
                "tools": catalog_tool_names(contract.get("provider"), [name]),
                "api_calls": api_calls,
                "detail": contract.get("detection_note"),
            }
        )
    return resolved


def strictest_isolation(modes: set[str]) -> str | None:
    ranked = [mode for mode in ISOLATION_STRENGTH if mode in modes]
    return ranked[-1] if ranked else None


def route_conflicts(packet: dict[str, Any], decision: dict[str, Any], work_order: str | None = None) -> list[str]:
    """Every way a packet contradicts the routing decision that authorised it.

    Routing resolves which lanes the work needs and how strongly it must be
    isolated. A packet that holds less than that would run outside the protection
    routing decided it required, which no lease can detect after the fact.

    Pass `work_order` when the packet names an alias: the registry treats aliases
    as display compatibility, so one must not read as a different work order.
    """
    conflicts: list[str] = []
    order = str(work_order or packet.get("work_order", ""))
    canonical = str(decision.get("canonical_work_order", ""))
    if canonical and order and order != canonical:
        conflicts.append(f"packet is work order {order!r}; the decision authorises {canonical!r}")
    if decision.get("tool_access_degraded"):
        degraded_capabilities = {str(item.get("capability")) for item in decision.get("degraded_capabilities", [])}
        packet_capabilities = {str(item) for item in packet.get("capabilities", []) if item}
        claimed = sorted(degraded_capabilities & packet_capabilities)
        takes_a_lane = bool([item for item in packet.get("leases", []) if item])
        if claimed or takes_a_lane:
            named = ", ".join(claimed) or ", ".join(sorted(degraded_capabilities))
            conflicts.append(
                f"routing marked tool access degraded for {named}; take the declared fallback rather than the lane"
            )
    routed = {str(item) for item in decision.get("leases", []) if item}
    declared = {str(item) for item in packet.get("leases", []) if item}
    for missing in sorted(routed - declared):
        conflicts.append(f"routing requires lease {missing!r}, which the packet does not declare")
    required_mode = decision.get("isolation_mode")
    packet_mode = str((packet.get("isolation") or {}).get("mode", ""))
    if required_mode and packet_mode:
        if ISOLATION_STRENGTH.index(required_mode) > ISOLATION_STRENGTH.index(packet_mode):
            conflicts.append(
                f"routing requires {required_mode!r} isolation; the packet declares the weaker {packet_mode!r}"
            )
    return conflicts


def unreal_shape_lane(task_class: str, policy: dict[str, Any]) -> str | None:
    """The lane route-policy's unreal_routing implies for this shape of work."""
    routing = policy.get("unreal_routing", {})
    if task_class in set(routing.get("prefer_editor_closed_for", [])):
        return "lane.ue-editor-closed"
    if task_class in set(routing.get("prefer_live_editor_for", [])):
        return "lane.ue-editor"
    return None


def route_work(project_value: str, request_value: str, host_override: str | None = None) -> dict[str, Any]:
    root, _ = project_root(project_value)
    profile = active_profile(root, host_override)
    request_path = Path(request_value).expanduser().resolve()
    request = load_json(request_path)
    required = {"work_order", "task_class", "complexity", "bounded", "required_capabilities", "required_lanes", "mutation_risk"}
    missing = sorted(required - set(request))
    if missing:
        raise fail("Route request missing: " + ", ".join(missing), reason=ERROR_REASON["CONTRACT_INVALID"], code=EXIT_USAGE)

    packet_registry_path = root / ".forge" / "state" / "packet-registry.json"
    if not packet_registry_path.is_file():
        raise fail("Canonical packet registry is missing; apply the Forge overlay before routing", reason=ERROR_REASON["OVERLAY_MISSING"])
    packet_registry = load_json(packet_registry_path)
    packets = {str(item.get("id")): item for item in packet_registry.get("packets", [])}
    requested_order = str(request["work_order"])
    resolved_order = canonical_order(packet_registry, requested_order)
    if resolved_order not in packets:
        raise fail(f"Unregistered work_order {requested_order!r}; register the canonical packet or an explicit alias before routing", reason=ERROR_REASON["CONTRACT_INVALID"])

    policy = route_policy()
    offload = policy["offload_policy"]
    keep_on_resident = set(offload["keep_on_resident_by_default"])
    hard_resident = (
        not bool(request["bounded"])
        or request["task_class"] in keep_on_resident
        or request["complexity"] == "critical"
        or request["mutation_risk"] in {"external-write", "destructive"}
    )

    detected_path = root / ".forge" / "capabilities" / "detected.json"
    qualification_path = root / ".forge" / "capabilities" / "qualifications.json"
    detected = load_json(detected_path) if detected_path.exists() else {"providers": []}
    qualifications = load_json(qualification_path) if qualification_path.exists() else {"evaluations": []}
    provider_status = {str(item.get("id")): item.get("status") for item in detected.get("providers", [])}

    contracts = {str(item["capability"]): item for item in mcp_capability_contracts(root, profile)}
    for item in contracts.values():
        provider_status[str(item.get("provider"))] = item.get("status")

    required_capabilities = set(request.get("required_capabilities", []))
    required_lanes = set(request.get("required_lanes", []))
    tool_access = resolve_tool_access(contracts, required_capabilities, str(request["task_class"]))
    unbound = [item for item in tool_access if item["routed"] and not item["bound"]]
    holding = [item for item in tool_access if item["routed"] and item["bound"]]
    lanes = sorted({item["lane"] for item in holding if item["lane"]})
    leases = sorted({item["lease"] for item in holding if item["lease"]})
    isolation_mode = strictest_isolation({item["isolation_mode"] for item in holding if item["isolation_mode"]})
    undeclared_lanes = sorted(set(lanes) - required_lanes)
    unserved_lanes = sorted(required_lanes - set(lanes))

    candidates = [
        {
            "provider": RESIDENT_PROVIDER,
            "host": profile["id"],
            "eligible": True,
            "score": 0.0,
            "reason": f"resident baseline ({profile.get('display_name', profile['id'])})",
        }
    ]
    resident_aliases = {RESIDENT_PROVIDER, profile["id"]}
    for evaluation in qualifications.get("evaluations", []):
        provider = str(evaluation.get("provider", ""))
        if not provider or provider in resident_aliases:
            continue
        reasons = []
        if evaluation.get("verdict") != "PASS":
            reasons.append("evaluation did not pass")
        evidence_host = evaluation.get("host")
        if evidence_host and evidence_host != profile["id"]:
            reasons.append(f"qualification recorded under host {evidence_host!r}; re-probe under {profile['id']!r}")
        if evaluation.get("task_class") != request["task_class"] or evaluation.get("complexity") != request["complexity"]:
            reasons.append("task or complexity scope mismatch")
        if not required_capabilities.issubset(set(evaluation.get("capabilities", []))):
            reasons.append("required capability missing")
        if not required_lanes.issubset(set(evaluation.get("lanes", []))):
            reasons.append("required lane missing")
        if provider_status.get(provider) not in {"AVAILABLE_VERIFIED", "AVAILABLE_UNVERIFIED"}:
            reasons.append("provider unavailable or absent from current detection")
        metrics = evaluation.get("metrics", {})
        score = sum(float(metrics.get(name, 0.0)) for name in policy["score"]["positive"])
        score -= sum(float(metrics.get(name, 0.0)) for name in policy["score"]["negative"])
        candidates.append(
            {
                "provider": provider,
                "host": evidence_host,
                "eligible": not reasons,
                "score": round(score, 6),
                "reason": "; ".join(reasons) if reasons else "exact qualification passed",
            }
        )

    eligible_optional = sorted(
        (item for item in candidates if item["provider"] != RESIDENT_PROVIDER and item["eligible"]),
        key=lambda item: (item["score"], item["provider"]),
        reverse=True,
    )
    if hard_resident:
        selected = RESIDENT_PROVIDER
        decision = "resident-required-by-policy"
    elif eligible_optional and eligible_optional[0]["score"] > 0:
        selected = eligible_optional[0]["provider"]
        decision = "qualified-optional-advantage"
    else:
        selected = RESIDENT_PROVIDER
        decision = "no-qualified-positive-advantage"
    shape_lane = unreal_shape_lane(str(request["task_class"]), policy)
    shape_conflict = {
        lane
        for lane in set(request.get("required_lanes", [])) | set(lanes)
        if lane.startswith("lane.ue-editor") and lane != shape_lane
    } if shape_lane else set()
    return {
        "schema": "forge.route-decision/v1",
        "project": str(root.resolve()),
        "request": request,
        "canonical_work_order": resolved_order,
        "selected": selected,
        "resident_host": profile["id"],
        "decision": decision,
        "candidates": candidates,
        "fallback": RESIDENT_PROVIDER,
        "tool_access": tool_access,
        "lanes": lanes,
        "leases": leases,
        "isolation_mode": isolation_mode,
        "tool_access_degraded": bool(unbound),
        "degraded_capabilities": [
            {"capability": item["capability"], "status": item.get("status"), "take_fallback": item["fallbacks"]}
            for item in unbound
        ],
        "lane_warnings": (
            [f"route implies lane {lane!r}, which the request did not declare in required_lanes" for lane in undeclared_lanes]
            + [f"request declares lane {lane!r}, which no bound route serves" for lane in unserved_lanes]
            + (
                [
                    f"route-policy puts task class {request['task_class']!r} on {shape_lane!r}, and this request "
                    f"names {sorted(shape_conflict)!r}; the two Unreal lanes are mutually exclusive, so confirm the "
                    "shape of the work before taking a lane it does not imply"
                ]
                if shape_lane and shape_conflict
                else []
            )
        ),
        "requires_independent_verification": True,
    }
