"""Where the project stands and what it should do next."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_core import ERROR_REASON, EXIT_USAGE, ForgeExit, fail, load_json, project_root
from forge_gsd import dropped_gsd_verbs, forge_action, gsd_command_name, gsd_smart_entry
from forge_hosts import active_profile, host_command, read_runtime, rendered_surfaces
from forge_routing import reachability


def design_sources(root: Path) -> list[str]:
    candidates = [root / "Docs" / "Design", root / "docs" / "design", root / "Design"]
    found: list[str] = []
    seen: set[str] = set()
    for directory in candidates:
        resolved = str(directory.resolve())
        key = resolved.casefold()
        if key not in seen and directory.is_dir() and any(path.is_file() for path in directory.rglob("*.md")):
            found.append(resolved)
            seen.add(key)
    return found


NEVER_BLOCKED_ACTIONS = frozenset({"doctor", "bootstrap", "bootstrap-resume", "host-render"})


BOOTSTRAP_REPORT_FIELDS = {
    "schema",
    "verdict",
    "jobs",
    "delegation",
    "verified",
    "assumed",
    "unavailable",
    "blocking",
    "human_actions",
    "evidence",
    "next_action",
}


BOOTSTRAP_CLOSABLE_VERDICTS = {"PASS", "DEGRADED_ACCEPTED"}


def bootstrap_verdict(root: Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Decide whether Forge bootstrap is closable."""
    profile = profile or active_profile(root)
    checks: list[dict[str, Any]] = []

    def record(check_id: str, ok: bool, detail: str) -> bool:
        checks.append({"id": check_id, "status": "PASS" if ok else "FAIL", "detail": detail})
        return ok

    detected_path = root / ".forge" / "capabilities" / "detected.json"
    report_path = root / ".forge" / "state" / "bootstrap-report.json"

    record(
        "capability-profile",
        detected_path.is_file(),
        str(detected_path) if detected_path.is_file() else "detected.json is missing; run capability detection",
    )
    if not report_path.is_file():
        record("bootstrap-report", False, "bootstrap-report.json is missing")
        return _bootstrap_result(root, profile, checks)
    try:
        report = load_json(report_path)
    except ForgeExit as exc:
        record("bootstrap-report", False, str(exc))
        return _bootstrap_result(root, profile, checks)
    record("bootstrap-report", True, str(report_path))

    missing_fields = sorted(BOOTSTRAP_REPORT_FIELDS - set(report))
    record(
        "report-schema",
        not missing_fields,
        "all required fields present" if not missing_fields else "missing: " + ", ".join(missing_fields),
    )
    verdict = report.get("verdict")
    record(
        "report-verdict",
        verdict in BOOTSTRAP_CLOSABLE_VERDICTS,
        f"verdict is {verdict!r}" + ("" if verdict in BOOTSTRAP_CLOSABLE_VERDICTS else "; not closable"),
    )
    blocking = report.get("blocking") or []
    record(
        "report-blocking",
        not blocking,
        "no blocking items" if not blocking else f"{len(blocking)} blocking item(s) remain",
    )

    registry_path = root / ".forge" / "state" / "packet-registry.json"
    try:
        packets = load_json(registry_path).get("packets", [])
        expected_jobs = {str(item["id"]) for item in packets if str(item.get("id", "")).startswith("FI-")}
    except (ForgeExit, KeyError) as exc:
        record("packet-coverage", False, f"packet registry is unreadable, so job coverage cannot be checked: {exc}")
        return _bootstrap_result(root, profile, checks)
    reported_jobs = {str(item.get("work_order")) for item in report.get("jobs", []) if isinstance(item, dict)}
    missing_jobs = sorted(expected_jobs - reported_jobs)
    record(
        "installation-jobs",
        not missing_jobs,
        f"{len(reported_jobs & expected_jobs)}/{len(expected_jobs)} canonical jobs reported"
        + ("" if not missing_jobs else "; omitted: " + ", ".join(missing_jobs)),
    )

    instruction_name = str(profile.get("project_surface", {}).get("instruction_file", "AGENTS.md"))
    instruction_path = root / instruction_name
    has_contract = (
        instruction_path.is_file()
        and "## Forge phase contract" in instruction_path.read_text(encoding="utf-8-sig", errors="replace")
    )
    record(
        "phase-contract",
        has_contract,
        f"{instruction_name} carries the Forge phase contract"
        if has_contract
        else f"{instruction_name} is missing or lacks '## Forge phase contract'; review any "
        f"{instruction_name}.forge-proposed file, or re-render with: "
        f"forge.py host set --host {profile['id']} --project . --apply",
    )
    return _bootstrap_result(root, profile, checks)


def _bootstrap_result(root: Path, profile: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [item for item in checks if item["status"] == "FAIL"]
    return {
        "schema": "forge.bootstrap-check/v1",
        "project": str(root),
        "host": profile["id"],
        "ok": not failed,
        "checks": checks,
        "blocking": [f"{item['id']}: {item['detail']}" for item in failed],
        "next_action": (
            f"{host_command(profile, 'forge-bootstrap')} --resume"
            if failed
            else f"{host_command(profile, 'forge-next')}"
        ),
    }


def bootstrap_is_complete(root: Path) -> bool:
    try:
        return bool(bootstrap_verdict(root)["ok"])
    except (OSError, ForgeExit):
        return False


def execution_coverage(root: Path) -> list[dict[str, Any]]:
    """Report GSD phase directories whose plans lack matching summaries."""
    phases = root / ".planning" / "phases"
    if not phases.is_dir():
        return []
    coverage: list[dict[str, Any]] = []
    for directory in sorted(path for path in phases.iterdir() if path.is_dir()):
        plans = sorted(directory.glob("*-PLAN.md"))
        if not plans:
            continue
        missing = [
            path.name
            for path in plans
            if not path.with_name(path.name.replace("-PLAN.md", "-SUMMARY.md")).is_file()
        ]
        coverage.append(
            {
                "phase": directory.name,
                "plans": len(plans),
                "summaries": len(plans) - len(missing),
                "missing_summaries": missing,
                "state": "complete" if not missing else ("partial" if len(missing) < len(plans) else "unstarted"),
            }
        )
    return coverage


def forge_next(project_value: str, gsd_result: dict[str, Any] | None = None, host_override: str | None = None) -> dict[str, Any]:
    """Combine Forge adoption readiness with GSD's authoritative smart-entry snapshot."""
    root, uproject = project_root(project_value)
    profile = active_profile(root, host_override)
    overlay = (root / ".forge" / "config.json").is_file() and (root / ".forge" / "directives.md").is_file()
    bootstrap_complete = bootstrap_is_complete(root)
    planning = root / ".planning"
    has_planning = planning.is_dir()
    sources = design_sources(root)
    has_code = bool(uproject or (root / "Source").is_dir())
    gsd = gsd_result if gsd_result is not None else gsd_smart_entry(root, profile)
    snapshot = gsd.get("snapshot") if isinstance(gsd, dict) else None

    runtime = read_runtime(root)
    surfaces_current = overlay and all(
        destination.exists() and destination.read_bytes() == payload
        for destination, payload in rendered_surfaces(root, profile)
    )

    signals = {
        "forge_overlay": overlay,
        "forge_bootstrap_complete": bootstrap_complete,
        "has_planning": has_planning,
        "has_uproject": bool(uproject),
        "has_source": (root / "Source").is_dir(),
        "design_sources": sources,
        "gsd_available": bool(isinstance(gsd, dict) and gsd.get("ok")),
        "active_host": profile["id"],
        "host_assigned": bool(runtime),
        "host_surfaces_current": bool(surfaces_current),
    }

    suppressed: list[dict[str, str]] = []
    coverage = execution_coverage(root)
    warnings = [
        f"Phase {item['phase']} is partially executed: {item['summaries']}/{item['plans']} plans have summaries "
        f"(missing: {', '.join(item['missing_summaries'])}). GSD does not block completion on this."
        for item in coverage
        if item["state"] == "partial"
    ]

    if not overlay:
        situation = "forge-not-adopted"
        summary = "Forge is not adopted in this directory; install the project overlay before resuming work."
        actions = [
            forge_action("bootstrap", "Adopt this project with Forge", "forge-bootstrap", True, "Creates the reversible project-local control plane, then stops for a fresh session.", profile),
            forge_action("doctor", "Inspect the environment", "forge-doctor", False, "Read-only capability and dependency diagnosis.", profile),
        ]
    elif not surfaces_current:
        situation = "host-surfaces-stale"
        summary = (
            f"Forge state is present, but the generated surfaces for the active runtime ({profile.get('display_name', profile['id'])}) "
            "are missing or out of date. Re-render them from the neutral canon before resuming work."
        )
        actions = [
            forge_action(
                "host-render",
                f"Re-render host surfaces for {profile.get('display_name', profile['id'])}",
                f"python <forge-plugin-root>/scripts/forge.py host set --host {profile['id']} --project . --apply",
                True,
                "Regenerates the project instruction file and project-local agents from .forge canon.",
                profile,
            ),
            forge_action("doctor", "Inspect the environment", "forge-doctor", False, "Read-only diagnosis before re-rendering.", profile),
        ]
    elif not bootstrap_complete:
        situation = "forge-bootstrap-incomplete"
        summary = "Forge is present, but bootstrap evidence is incomplete; resume bootstrap before project work."
        actions = [
            forge_action("bootstrap-resume", "Resume Forge bootstrap", "forge-bootstrap --resume", True, "Completes capability inventory, delegated checks, verification, and the persisted report.", profile),
            forge_action("doctor", "Inspect the environment", "forge-doctor", False, "Read-only diagnosis before resuming bootstrap.", profile),
        ]
    elif not isinstance(gsd, dict) or not gsd.get("ok"):
        situation = "gsd-unavailable"
        summary = "Forge bootstrap was previously accepted, but GSD smart-entry is not currently available."
        actions = [
            forge_action("doctor", "Repair or inspect GSD", "forge-doctor", True, str(gsd.get("error", "GSD state unavailable")) if isinstance(gsd, dict) else "Invalid GSD result", profile),
            forge_action("bootstrap-resume", "Re-evaluate Forge bootstrap", "forge-bootstrap --resume", False, "Refresh stale dependency evidence after GSD changes.", profile),
        ]
    elif has_planning:
        if isinstance(snapshot, dict) and snapshot.get("actions"):
            situation = f"gsd-{snapshot.get('situation', 'unknown')}"
            summary = str(snapshot.get("summary") or "GSD project state detected.")
            actions = []
            dropped = dropped_gsd_verbs()
            for index, item in enumerate(snapshot["actions"]):
                if not isinstance(item, dict) or not item.get("command"):
                    continue
                raw = str(item["command"]).strip()
                untranslated_name = gsd_command_name(raw)
                if untranslated_name in dropped:
                    suppressed.append(
                        {
                            "gsd_command": raw,
                            "reason": dropped[untranslated_name],
                            "run_directly": host_command(profile, untranslated_name),
                        }
                    )
                    continue
                actions.append(
                    forge_action(
                        str(item.get("id") or f"gsd-action-{index + 1}"),
                        str(item.get("label") or raw),
                        raw,
                        bool(item.get("recommended")),
                        "Authoritative route from GSD smart-entry.",
                        profile,
                    )
                )
            if not actions and suppressed:
                actions = [
                    forge_action(
                        "progress",
                        "Review project progress",
                        "forge-progress",
                        True,
                        "Forge fronts none of the actions GSD offered; see suppressed_actions to run them directly.",
                        profile,
                    )
                ]
            if actions and not any(action["recommended"] for action in actions):
                actions[0]["recommended"] = True
        else:
            situation = "gsd-unavailable"
            summary = "GSD planning state exists, but its smart-entry runtime could not be read safely."
            actions = [
                forge_action("doctor", "Repair or inspect GSD", "forge-doctor", True, str(gsd.get("error", "GSD state unavailable")), profile),
            ]
    elif sources:
        source_arg = str(Path(sources[0]).relative_to(root))
        situation = "existing-design-unplanned"
        summary = "Existing design documents were found, but GSD project memory has not been created."
        actions = [
            forge_action("ingest-docs", "Ingest existing design documents", f'gsd-ingest-docs "{source_arg}"', True, "Preserves existing decisions and detects conflicts before planning.", profile),
            forge_action("onboard", "Onboard the existing project", "gsd-onboard", False, "Use when codebase mapping should precede document ingestion.", profile),
        ]
    elif has_code:
        situation = "existing-project-unplanned"
        summary = "An existing Unreal/code project was found without GSD project memory."
        actions = [
            forge_action("onboard", "Onboard the existing project", "gsd-onboard", True, "Maps the codebase and establishes GSD planning state.", profile),
            forge_action("ingest-docs", "Ingest project documents", "gsd-ingest-docs", False, "Use when authoritative planning documents exist outside the standard design folders.", profile),
        ]
    else:
        situation = "greenfield-ready"
        summary = "Forge bootstrap is complete and no existing GSD project, design corpus, or Unreal source was found."
        actions = [
            forge_action("forge-init", "Start Forge project inception", "forge-init", True, "Begins the design interview and creates canonical GSD project memory.", profile),
            forge_action("doctor", "Inspect the environment", "forge-doctor", False, "Read-only capability diagnosis before committing to inception.", profile),
        ]

    reach = reachability(root)
    for action in actions:
        blocking = [] if action["id"] in NEVER_BLOCKED_ACTIONS else reach["blockers"]
        action["reachable"] = not blocking
        action["blocked_by"] = blocking

    recommended = next((action["id"] for action in actions if action["recommended"]), actions[0]["id"] if actions else None)
    return {
        "schema": "forge.smart-entry/v1",
        "project": str(root),
        "situation": situation,
        "summary": summary,
        "recommended": recommended,
        "actions": actions,
        "signals": signals,
        "authority": {"phase_state": "gsd", "forge_scope": "adoption-capability-routing"},
        "execution_coverage": coverage,
        "warnings": warnings,
        "suppressed_actions": suppressed,
        "runtime": {
            "active_host": profile["id"],
            "display_name": profile.get("display_name"),
            "assigned": bool(runtime),
            "surfaces_current": bool(surfaces_current),
            "swappable": True,
        },
        "reachability": {
            "readable": reach["readable"],
            "detail": reach["detail"],
            "blockers": reach["blockers"],
            "sources": reach["sources"],
            "not_checked": reach["not_checked"],
            "never_blocked": sorted(NEVER_BLOCKED_ACTIONS),
        },
        "gsd_snapshot": snapshot,
        "gsd_error": "" if gsd.get("ok") else str(gsd.get("error", "")),
        "dispatch_contract": "choose exactly one action, dispatch it, then stop",
    }


def lifecycle_state(project_value: str, event: str = "status") -> dict[str, Any]:
    """Read the deprecated Forge lifecycle mirror. Never a phase authority."""
    root, _ = project_root(project_value)
    path = root / ".forge" / "state" / "lifecycle.json"
    if not path.is_file():
        raise fail("Forge lifecycle state is missing; apply the project overlay first", reason=ERROR_REASON["OVERLAY_MISSING"])
    state = load_json(path)
    profile = active_profile(root)
    if event != "status":
        raise fail(
            "Forge lifecycle transitions are deprecated; use "
            f"{host_command(profile, 'forge-next')} and let GSD own phase state",
            reason=ERROR_REASON["USAGE"],
            code=EXIT_USAGE,
        )
    stored = str(state.get("next_command") or "")
    head, _, tail = stored.partition(" ")
    spelled = f"{host_command(profile, head)}{' ' + tail if tail else ''}" if head else ""
    return {
        "schema": "forge.lifecycle-status/v1",
        "mode": "read-only",
        "path": str(path),
        "state": state,
        "deprecated": True,
        "host": profile["id"],
        "next_command_for_host": spelled,
        "authority": f"GSD .planning state via {host_command(profile, 'forge-next')}",
    }
