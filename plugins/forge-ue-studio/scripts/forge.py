#!/usr/bin/env python3
"""Forge's command line: argument surface, result contract, and exit codes.

Every verb it fronts lives in a sibling module, imported below so that this
file names the whole public surface in one place. Forge runs as a script
rather than a package, so it puts its own directory on the import path
before loading them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from forge_core import (
    ERROR_REASON,
    EXIT_CONTRACT,
    EXIT_FAILURE,
    EXIT_OK,
    EXIT_USAGE,
    ForgeExit,
    RESIDENT_PROVIDER,
    OCCUPANCY,
    SCHEMA_FILES,
    STATUSES,
    capability,
    command_probe,
    executable,
    executor,
    expand_host_path,
    is_available,
    fail,
    file_digest,
    find_uproject,
    load_json,
    plugin_names,
    plugin_root,
    project_root,
    proposal_path,
    proposal_payload_path,
    schema_files,
    schema_root,
    template_files,
    template_root,
    toml_escape,
    utc_now,
    validate_payload,
)
from forge_mcp import (
    agent_route_briefing,
    agent_tool_surface,
    catalog_staleness,
    catalog_tool_names,
    catalog_tools_for,
    project_engine_version,
    tool_catalog,
    endpoint_is_listening,
    host_speaks_mcp,
    EDITOR_PROCESS_NAMES,
    MCP_SETTINGS_DEFAULTS,
    MCP_SETTINGS_SECTION,
    decode_jsonrpc,
    editor_process_holding,
    endpoint_disagreement,
    read_jsonrpc_frame,
    unreal_mcp_settings,
    live_editor_holds_project,
    project_descriptors,
    mcp_amend,
    mcp_capability_contracts,
    mcp_capability_index,
    mcp_endpoint_url,
    mcp_providers,
    mcp_status,
    mcp_tool_namespace,
    probe_mcp_endpoint,
    probe_mcp_server,
    probe_process_route,
    process_providers,
    project_mcp,
    project_mcp_path,
    record_consent,
    render_project_mcp,
    resolve_declared_servers,
    resolve_project_servers,
    route_providers,
    route_registry,
    sync_user_mcp,
)
from forge_hosts import (
    active_host_id,
    active_profile,
    agent_definitions,
    apply_host_surfaces,
    canon_source,
    host_command,
    host_prerequisites,
    host_profile,
    host_profiles,
    host_registry,
    read_runtime,
    render_agent,
    render_tokens,
    rendered_surfaces,
    retire_host_surfaces,
    runtime_path,
    write_runtime,
)
from forge_gsd import (
    dropped_gsd_verbs,
    forge_action,
    gsd_command_name,
    gsd_environment,
    gsd_runtime,
    gsd_runtime_name,
    gsd_runtime_roots,
    gsd_smart_entry,
    gsd_to_forge_verbs,
    normalize_gsd_command,
    sync_gsd_runtime,
    translate_gsd_verb,
    verb_registry,
)
from forge_survey import ollama_models, survey
from forge_lifecycle import (
    BOOTSTRAP_CLOSABLE_VERDICTS,
    BOOTSTRAP_REPORT_FIELDS,
    bootstrap_is_complete,
    bootstrap_verdict,
    design_sources,
    execution_coverage,
    forge_next,
    lifecycle_state,
)
from forge_install import (
    STATE_MIGRATIONS,
    STATE_SCHEMA_VERSION,
    install_overlay,
    profile_registry,
    stable_profile,
    state_version,
    verify_overlay,
    write_profile,
)
from forge_routing import (
    BLOCKED_LANE_DEFAULTS,
    DEFAULT_FRESHNESS_MINUTES,
    ISOLATION_STRENGTH,
    PROCEDURE_SCHEMA,
    ROUTE_DECISIONS_SCHEMA,
    WORK_ORDERS_SCHEMA,
    blocked_lane_policy,
    canonical_order,
    canonical_order_for,
    capability_lanes,
    clear_lane_failures,
    confirm_autonomous_entry,
    decide_blocked_lane,
    decision_freshness_minutes,
    engine_prerequisite_gaps,
    lane_failure_counts,
    procedure_for,
    procedure_gaps,
    procedure_resolution,
    procedures,
    procedures_path,
    record_blocked_lane,
    read_route_decisions,
    record_dispatch,
    record_release,
    record_route_decision,
    resolve_decision_for,
    resolve_route_decision,
    resolve_tool_access,
    route_conflicts,
    unreal_shape_lane,
    route_decisions_path,
    route_drift,
    route_policy,
    route_work,
    strictest_isolation,
    work_orders_path,
    WORK_ORDER_TERMINAL_STATES,
)
from forge_runtime import host_list, host_set, host_status


VERDICT_COMMANDS = frozenset(
    {
        "verify",
        "bootstrap-check",
        "validate",
        "host status",
    }
)


def execute_acquire(
    project_value: str,
    packet_value: str,
    owner: str | None,
    apply: bool,
    host_override: str | None = None,
    route_value: str | None = None,
) -> dict[str, Any]:
    """Take the leases and isolation a work packet declares, as one transaction.

    The decision that authorised the work is looked up from the ledger `route
    --apply` writes, not handed in, so a packet no routing decision covers is
    refused rather than acquired on trust. A packet that holds less than routing
    resolved it needs is refused too, because acquiring the weaker thing leaves
    nothing able to detect afterwards that the work ran unprotected.
    """
    root, _ = project_root(project_value)
    profile = active_profile(root, host_override)
    packet_path = Path(packet_value).expanduser().resolve()
    packet = load_json(packet_path)
    admission = resolve_decision_for(root, packet, route_value)
    conflicts = route_conflicts(packet, admission["decision"], admission["canonical_work_order"])
    if conflicts:
        raise fail(
            f"Packet and routing decision disagree on {len(conflicts)} point(s); acquiring would hold less "
            "than routing required",
            reason=ERROR_REASON["ROUTE_PACKET_MISMATCH"],
            code=EXIT_CONTRACT,
            conflicts=conflicts,
            packet=str(packet_path),
            route=admission["source"],
        )
    result = executor.acquire(root, packet, owner or str(profile["id"]), apply=apply)
    return {
        **result,
        "packet": str(packet_path),
        "route": admission["source"],
        "route_recorded_at": admission["recorded_at"],
        "host": profile["id"],
    }


def procedure_brief(task_class: str) -> dict[str, Any]:
    return {
        "schema": PROCEDURE_SCHEMA,
        "task_class": task_class,
        "source": str(procedures_path()),
        "procedure": procedure_for(task_class),
        "resolution": procedure_resolution(task_class),
        "declared": sorted(procedures()),
    }


def dispatch_work(
    project_value: str,
    packet_value: str,
    owner: str | None,
    apply: bool,
    host_override: str | None = None,
    route_value: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Admit a packet to execution, or refuse it, as one decision.

    Validating the packet, proving its routes are reachable now, holding the
    leases and recording the transition were four steps an agent walked between.
    Each seam was a place the agent could skip a check and still reach the next
    step, so the guarantee held only while it followed the workflow. Here nothing
    is acquired unless every check passed, and nothing is recorded unless it was
    acquired.
    """
    root, _ = project_root(project_value)
    profile = active_profile(root, host_override)
    packet_path = Path(packet_value).expanduser().resolve()
    packet = load_json(packet_path)

    contract = validate_payload("work-packet", str(packet_path))
    if not contract["ok"]:
        raise fail(
            f"Work packet {packet_path.name} does not satisfy forge.work-packet/v1",
            reason=ERROR_REASON["CONTRACT_INVALID"],
            code=EXIT_CONTRACT,
            errors=contract["errors"],
            packet=str(packet_path),
        )

    procedure = procedure_for(str(packet.get("task_class", "")))
    resolution = procedure_resolution(str(packet.get("task_class", "")))
    if not resolution["procedured"]:
        print(json.dumps({"warning": resolution}), file=sys.stderr)
    gaps = procedure_gaps(packet, procedure) if procedure else []
    if gaps:
        raise fail(
            f"Task class {packet.get('task_class')!r} has a build procedure this packet leaves uncovered in "
            f"{len(gaps)} way(s); dispatching would run the procedure with a step nothing can perform",
            reason=ERROR_REASON["PROCEDURE_UNCOVERED"],
            code=EXIT_CONTRACT,
            gaps=gaps,
            procedure={
                "task_class": procedure["task_class"],
                "lanes": procedure["lanes"],
                "packets": procedure["packets"],
                "packet_split": procedure["packet_split"],
            },
            packet=str(packet_path),
        )

    shortfalls = engine_prerequisite_gaps(root, [str(item) for item in packet.get("capabilities", [])])
    if shortfalls:
        raise fail(
            f"{len(shortfalls)} route prerequisite the packet's capabilities need is not met by this project's "
            "engine or .uproject; the step that needed it would fail part-way rather than here",
            reason=ERROR_REASON["ENGINE_PREREQUISITE_MISSING"],
            code=EXIT_CONTRACT,
            shortfalls=shortfalls,
            packet=str(packet_path),
        )

    admission = resolve_decision_for(root, packet, route_value)
    conflicts = route_conflicts(packet, admission["decision"], admission["canonical_work_order"])
    if conflicts:
        raise fail(
            f"Packet and routing decision disagree on {len(conflicts)} point(s); dispatching would run outside "
            "the protection routing decided it needed",
            reason=ERROR_REASON["ROUTE_PACKET_MISMATCH"],
            code=EXIT_CONTRACT,
            conflicts=conflicts,
            packet=str(packet_path),
            route=admission["source"],
        )

    contracts = {str(item["capability"]): item for item in mcp_capability_contracts(root, profile)}
    required = {str(item) for item in packet.get("capabilities", []) if str(item).strip()}
    live = resolve_tool_access(contracts, required)
    blocked = [item for item in live if item["routed"] and item.get("status") == "UNAVAILABLE_BLOCKING"]
    autonomy: dict[str, Any] | None = None
    if blocked:
        autonomy = decide_blocked_lane(root, packet, blocked, policy)
        if not autonomy["proceed"]:
            raise fail(
                f"{len(blocked)} capability the packet declares sits on a lane whose state could not be "
                f"determined, and {autonomy['reason']}",
                reason=ERROR_REASON["ROUTE_BLOCKED"],
                code=EXIT_CONTRACT,
                blocked=[
                    {
                        "capability": item["capability"],
                        "status": item.get("status"),
                        "ownership": item.get("ownership"),
                        "human_action": item.get("human_action"),
                    }
                    for item in blocked
                ],
                autonomy=autonomy,
                packet=str(packet_path),
            )
    accepted = {item["capability"] for item in blocked} if (autonomy and autonomy["proceed"]) else set()
    unreachable = [
        item for item in live
        if item["routed"] and not item["bound"] and item["capability"] not in accepted
    ]
    if unreachable:
        raise fail(
            f"{len(unreachable)} capability the packet declares has no reachable route right now; dispatching "
            "would send work to a provider that cannot answer",
            reason=ERROR_REASON["ROUTE_UNREACHABLE"],
            code=EXIT_CONTRACT,
            unreachable=[
                {"capability": item["capability"], "status": item.get("status"), "take_fallback": item["fallbacks"]}
                for item in unreachable
            ],
            packet=str(packet_path),
        )
    drift = route_drift(admission["decision"], [item for item in live if item["capability"] not in accepted])
    if drift:
        raise fail(
            f"The routes available now differ from the ones routing scored in {len(drift)} way(s); re-run route "
            "rather than admitting on an answer the environment has moved past",
            reason=ERROR_REASON["ROUTE_DECISION_STALE"],
            code=EXIT_CONTRACT,
            drift=drift,
            route=admission["source"],
            route_recorded_at=admission["recorded_at"],
        )

    result = executor.acquire(root, packet, owner or str(profile["id"]), apply=apply)
    if apply and not blocked:
        clear_lane_failures(root, [str(item.get("lane")) for item in live if item.get("lane")])
    recorded = record_dispatch(root, packet, admission, result["leases"], autonomy, resolution) if apply else None
    return {
        "schema": "forge.dispatch/v1",
        "mode": "apply" if apply else "dry-run",
        "project": str(root),
        "work_order": result["work_order"],
        "packet": str(packet_path),
        "host": profile["id"],
        "route": admission["source"],
        "route_recorded_at": admission["recorded_at"],
        "contract": {"kind": "work-packet", "ok": True},
        "procedure": {**resolution, "covered": bool(procedure)},
        "autonomy": autonomy,
        "tool_access": live,
        "drift": [],
        "isolation_mode": result["isolation_mode"],
        "leases": result["leases"],
        "plan": result["plan"],
        "recorded": recorded,
        "renewal_overdue": result.get("renewal_overdue", []),
    }


def execute_release(project_value: str, work_order: str, outcome: str, apply: bool) -> dict[str, Any]:
    root, _ = project_root(project_value)
    result = executor.release(root, work_order, outcome, apply=apply)
    if apply:
        result["order"] = record_release(root, work_order, outcome, str(result["lease_status"]))
    return result


def execute_renew(project_value: str, work_order: str, apply: bool) -> dict[str, Any]:
    root, _ = project_root(project_value)
    return executor.renew(root, work_order, apply=apply)


def execute_reconcile(project_value: str, work_order: str, apply: bool) -> dict[str, Any]:
    root, _ = project_root(project_value)
    return executor.reconcile(root, work_order, apply=apply)


def execute_status(project_value: str) -> dict[str, Any]:
    root, _ = project_root(project_value)
    return executor.status(root)


def emit(data: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(data, indent=2, sort_keys=True)
    print(rendered)
    if output:
        target = Path(output).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("survey", "install", "verify", "profile", "next", "bootstrap-check"):
        command = sub.add_parser(name)
        command.add_argument("--project", required=True)
        command.add_argument("--host", help="Override the assigned runtime host for this invocation")
        command.add_argument("--output")
        if name in {"install", "profile"}:
            mode = command.add_mutually_exclusive_group()
            mode.add_argument("--apply", action="store_true")
            mode.add_argument("--dry-run", action="store_true")
    gsd_sync = sub.add_parser("gsd-sync", help="Write GSD's runtime key from the assigned host")
    gsd_sync.add_argument("--project", required=True)
    gsd_sync.add_argument("--host")
    gsd_sync.add_argument("--apply", action="store_true")
    gsd_sync.add_argument("--output")
    host = sub.add_parser("host", help="Inspect or assign the resident runtime host")
    host_sub = host.add_subparsers(dest="host_command", required=True)
    host_list_parser = host_sub.add_parser("list", help="List known runtime hosts and their prerequisites")
    host_list_parser.add_argument("--output")
    host_status_parser = host_sub.add_parser("status", help="Show the assigned runtime and surface freshness")
    host_status_parser.add_argument("--project", required=True)
    host_status_parser.add_argument("--host")
    host_status_parser.add_argument("--output")
    host_set_parser = host_sub.add_parser("set", help="Assign or swap the resident runtime host")
    host_set_parser.add_argument("--project", required=True)
    host_set_parser.add_argument("--host", required=True)
    host_set_parser.add_argument("--apply", action="store_true")
    host_set_parser.add_argument("--output")
    route = sub.add_parser("route")
    route.add_argument("--project", required=True)
    route.add_argument("--host")
    route.add_argument("--request", required=True)
    route.add_argument("--apply", action="store_true", help="Record the decision so `exec acquire` can find it; without this the decision is a preview only")
    route.add_argument("--output")
    for name, help_text in (
        ("route-status", "Report every typed route this project can reach: servers and commands alike"),
        ("mcp-status", "Report this project's typed routes. Retained spelling of route-status"),
    ):
        status_parser = sub.add_parser(name, help=help_text)
        status_parser.add_argument("--project", required=True)
        status_parser.add_argument("--host")
        status_parser.add_argument("--output")
    mcp = sub.add_parser("mcp", help="Declare or amend the typed tool routes this project uses")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    for action in ("add", "remove", "enable", "disable"):
        amend = mcp_sub.add_parser(action)
        amend.add_argument("--project", required=True)
        amend.add_argument("--host")
        amend.add_argument("--id", required=True)
        amend.add_argument("--apply", action="store_true")
        amend.add_argument("--output")
        if action == "add":
            amend.add_argument("--command", dest="server_command", help="Executable that starts the server")
            amend.add_argument("--arg", action="append", dest="args", help="Repeatable argument")
            amend.add_argument("--url", help="Endpoint of a server that is already listening, such as Unreal's editor-hosted route")
            amend.add_argument(
                "--scope", choices=["project", "user", "both"], default="project",
                help="project: this game's session sees it. user/both: agents it spawns see it too, via a consented machine-wide write.",
            )
    sync_user = mcp_sub.add_parser("sync-user", help="Publish user-scoped routes so spawned agents can see them")
    sync_user.add_argument("--project", required=True)
    sync_user.add_argument("--host")
    sync_user.add_argument("--apply", action="store_true")
    sync_user.add_argument("--output")
    procedure = sub.add_parser("procedure", help="Report the build procedure a task class carries: steps, lanes, acceptance, verification, evidence")
    procedure.add_argument("--task-class", dest="task_class", required=True)
    procedure.add_argument("--output")
    validate = sub.add_parser("validate")
    validate.add_argument("--kind", required=True, choices=sorted(SCHEMA_FILES))
    validate.add_argument("--input", required=True)
    validate.add_argument("--output")
    execution = sub.add_parser("exec", help="Hold leases and isolation for a work packet, transactionally")
    execution_sub = execution.add_subparsers(dest="exec_command", required=True)
    acquire_parser = execution_sub.add_parser("acquire", help="Take every lease and isolation the packet declares")
    acquire_parser.add_argument("--project", required=True)
    acquire_parser.add_argument("--packet", required=True)
    acquire_parser.add_argument("--route", dest="route", help="Routing decision that authorised this work; refuses a packet holding less than it requires")
    acquire_parser.add_argument("--owner", help="Who holds the lease; defaults to the assigned host")
    acquire_parser.add_argument("--host")
    acquire_parser.add_argument("--apply", action="store_true")
    acquire_parser.add_argument("--output")
    release_parser = execution_sub.add_parser("release", help="Release a work order's leases and tear down isolation")
    release_parser.add_argument("--project", required=True)
    release_parser.add_argument("--work-order", dest="work_order", required=True)
    release_parser.add_argument("--outcome", required=True, choices=["passed", "failed"])
    release_parser.add_argument("--apply", action="store_true")
    release_parser.add_argument("--output")
    renew_parser = execution_sub.add_parser("renew", help="Extend a lease whose work legitimately outruns the TTL")
    renew_parser.add_argument("--project", required=True)
    renew_parser.add_argument("--work-order", dest="work_order", required=True)
    renew_parser.add_argument("--apply", action="store_true")
    renew_parser.add_argument("--output")
    reconcile_parser = execution_sub.add_parser("reconcile", help="Retry the external teardown a release could not finish")
    reconcile_parser.add_argument("--project", required=True)
    reconcile_parser.add_argument("--work-order", dest="work_order", required=True)
    reconcile_parser.add_argument("--apply", action="store_true")
    reconcile_parser.add_argument("--output")
    exec_status_parser = execution_sub.add_parser("status", help="Report held leases and stale ones awaiting recovery")
    exec_status_parser.add_argument("--project", required=True)
    exec_status_parser.add_argument("--output")
    dispatch = sub.add_parser("dispatch", help="Admit a packet to execution as one decision: contract, routes, leases, record")
    dispatch.add_argument("--project", required=True)
    dispatch.add_argument("--packet", required=True)
    dispatch.add_argument("--route", dest="route", help="Routing decision held outside the ledger; replaces the lookup, never relaxes it")
    dispatch.add_argument("--owner", help="Who holds the lease; defaults to the assigned host")
    dispatch.add_argument("--host")
    dispatch.add_argument("--apply", action="store_true")
    dispatch.add_argument("--output")
    lifecycle = sub.add_parser("lifecycle")
    lifecycle.add_argument("--project", required=True)
    lifecycle.add_argument("--event", default="status", choices=["status"])
    lifecycle.add_argument("--output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "survey":
            result = survey(args.project, args.host)
        elif args.command == "install":
            result = install_overlay(args.project, apply=bool(args.apply), host_override=args.host)
        elif args.command == "verify":
            result = verify_overlay(args.project, args.host)
        elif args.command == "profile":
            result = write_profile(args.project, apply=bool(args.apply), host_override=args.host)
        elif args.command == "next":
            result = forge_next(args.project, host_override=args.host)
        elif args.command == "bootstrap-check":
            root, _ = project_root(args.project)
            result = bootstrap_verdict(root, active_profile(root, args.host))
        elif args.command in {"route-status", "mcp-status"}:
            root, _ = project_root(args.project)
            result = mcp_status(root, active_profile(root, args.host))
        elif args.command == "mcp":
            root, _ = project_root(args.project)
            profile = active_profile(root, args.host)
            if args.mcp_command == "sync-user":
                result = sync_user_mcp(root, profile, apply=bool(args.apply))
            else:
                result = mcp_amend(
                    root,
                    profile,
                    args.mcp_command,
                    args.id,
                    apply=bool(args.apply),
                    command=getattr(args, "server_command", None),
                    args=getattr(args, "args", None),
                    scope=getattr(args, "scope", "project"),
                    url=getattr(args, "url", None),
                )
        elif args.command == "gsd-sync":
            root, _ = project_root(args.project)
            result = sync_gsd_runtime(root, active_profile(root, args.host), apply=bool(args.apply))
            result = {"schema": "forge.gsd-runtime-sync/v1", "project": str(root), **result}
        elif args.command == "host":
            if args.host_command == "list":
                result = host_list()
            elif args.host_command == "status":
                result = host_status(args.project, args.host)
            else:
                result = host_set(args.project, args.host, apply=bool(args.apply))
        elif args.command == "route":
            result = route_work(args.project, args.request, args.host)
            root, _ = project_root(args.project)
            recorded = record_route_decision(root, result, str(active_profile(root, args.host)["id"])) if args.apply else None
            result = {
                **result,
                "recorded": bool(recorded),
                "recorded_at": recorded["recorded_at"] if recorded else None,
                "ledger": str(route_decisions_path(root)),
                "freshness_minutes": decision_freshness_minutes(),
            }
        elif args.command == "exec":
            if args.exec_command == "acquire":
                result = execute_acquire(args.project, args.packet, args.owner, apply=bool(args.apply), host_override=args.host, route_value=getattr(args, "route", None))
            elif args.exec_command == "release":
                result = execute_release(args.project, args.work_order, args.outcome, apply=bool(args.apply))
            elif args.exec_command == "renew":
                result = execute_renew(args.project, args.work_order, apply=bool(args.apply))
            elif args.exec_command == "reconcile":
                result = execute_reconcile(args.project, args.work_order, apply=bool(args.apply))
            else:
                result = execute_status(args.project)
        elif args.command == "dispatch":
            result = dispatch_work(
                args.project, args.packet, args.owner, apply=bool(args.apply),
                host_override=args.host, route_value=getattr(args, "route", None),
            )
        elif args.command == "procedure":
            result = procedure_brief(args.task_class)
        elif args.command == "lifecycle":
            result = lifecycle_state(args.project, args.event)
        else:
            result = validate_payload(args.kind, args.input)
        command_path = " ".join(
            part
            for part in (
                args.command,
                getattr(args, "host_command", None),
                getattr(args, "mcp_command", None),
                getattr(args, "exec_command", None),
            )
            if part
        )
        carries_verdict = "ok" in result
        if command_path in VERDICT_COMMANDS and not carries_verdict:
            raise fail(
                f"{command_path!r} is declared verdict-bearing but returned no 'ok'",
                reason=ERROR_REASON["RESULT_CONTRACT_VIOLATED"],
            )
        if command_path not in VERDICT_COMMANDS and carries_verdict:
            raise fail(
                f"{command_path!r} is not verdict-bearing but returned 'ok'; report the outcome in its own field",
                reason=ERROR_REASON["RESULT_CONTRACT_VIOLATED"],
            )
        if not result.get("schema"):
            raise fail(
                f"{command_path!r} returned a payload with no schema identity",
                reason=ERROR_REASON["RESULT_CONTRACT_VIOLATED"],
            )
        emit(result, args.output)
        if command_path in VERDICT_COMMANDS:
            return EXIT_OK if result["ok"] else EXIT_CONTRACT
        return EXIT_OK
    except executor.ExecutorError as exc:
        translated = fail(str(exc), reason=exc.reason, code=EXIT_CONTRACT, **exc.extra)
        print(json.dumps({**translated.payload(), "command": args.command}), file=sys.stderr)
        return translated.code
    except ForgeExit as exc:
        print(json.dumps({**exc.payload(), "command": args.command}), file=sys.stderr)
        return exc.code
    except OSError as exc:
        print(
            json.dumps({"ok": False, "reason": ERROR_REASON["JSON_UNREADABLE"], "message": str(exc), "command": args.command}),
            file=sys.stderr,
        )
        return EXIT_FAILURE
    except ValueError as exc:
        print(
            json.dumps({"ok": False, "reason": ERROR_REASON["UNKNOWN"], "message": str(exc), "command": args.command}),
            file=sys.stderr,
        )
        return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
