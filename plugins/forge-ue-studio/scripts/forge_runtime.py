"""Assigning and reporting the resident runtime seat."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_core import ERROR_REASON, executable, fail, project_root
from forge_gsd import sync_gsd_runtime
from forge_hosts import (
    active_host_id,
    active_profile,
    apply_host_surfaces,
    host_command,
    host_prerequisites,
    host_profile,
    host_registry,
    read_runtime,
    rendered_surfaces,
    retire_host_surfaces,
    write_runtime,
)


def host_status(project_value: str, host_override: str | None = None) -> dict[str, Any]:
    root, _ = project_root(project_value)
    profile = active_profile(root, host_override)
    runtime = read_runtime(root)
    surfaces = []
    for destination, payload in rendered_surfaces(root, profile):
        if not destination.exists():
            state = "MISSING"
        elif destination.read_bytes() == payload:
            state = "CURRENT"
        else:
            state = "STALE"
        surfaces.append({"path": str(destination), "status": state})
    return {
        "schema": "forge.host-status/v1",
        "project": str(root),
        "active_host": profile["id"],
        "display_name": profile.get("display_name"),
        "assigned": bool(runtime),
        "resident_capability": profile.get("resident_capability"),
        "skill_prefix": profile.get("skill_invocation", {}).get("prefix", ""),
        "instruction_file": profile.get("project_surface", {}).get("instruction_file"),
        "agent_dir": profile.get("project_surface", {}).get("agent_dir"),
        "prerequisites": host_prerequisites(profile),
        "surfaces": surfaces,
        "history": (runtime or {}).get("history", []),
        "ok": all(item["status"] == "CURRENT" for item in surfaces) if surfaces else False,
    }


def host_list() -> dict[str, Any]:
    registry = host_registry()
    return {
        "schema": "forge.host-list/v1",
        "default_host": registry.get("default_host"),
        "prerequisite_contract": registry.get("prerequisite_contract", {}),
        "hosts": [
            {
                "id": profile["id"],
                "display_name": profile.get("display_name"),
                "vendor": profile.get("vendor"),
                "skill_prefix": profile.get("skill_invocation", {}).get("prefix", ""),
                "instruction_file": profile.get("project_surface", {}).get("instruction_file"),
                "agent_format": profile.get("project_surface", {}).get("agent_format"),
                "cli_detected": bool(executable(*profile.get("cli", {}).get("executables", []))) if profile.get("cli", {}).get("executables") else None,
                "prerequisites": host_prerequisites(profile),
            }
            for profile in registry.get("hosts", [])
        ],
    }


def host_set(project_value: str, host_id: str, apply: bool) -> dict[str, Any]:
    """Assign or swap the resident runtime, re-rendering host surfaces from canon."""
    root, _ = project_root(project_value)
    if not (root / ".forge" / "config.json").is_file():
        raise fail("Forge is not adopted in this directory; run the install overlay before assigning a runtime", reason=ERROR_REASON["PROJECT_NOT_ADOPTED"])
    profile = host_profile(host_id)
    prerequisites = host_prerequisites(profile)
    if not prerequisites["satisfied"]:
        raise fail(
            f"Host {host_id!r} does not satisfy the Forge prerequisite contract; missing: "
            + ", ".join(prerequisites["missing_required"]),
            reason=ERROR_REASON["HOST_SURFACE_UNSUPPORTED"],
        )
    previous_id = active_host_id(root)
    actions = apply_host_surfaces(root, profile, apply)
    keep = {str(Path(item["target"]).relative_to(root)).replace("\\", "/") for item in actions if Path(item["target"]).is_absolute()}
    if previous_id != host_id:
        actions.extend(retire_host_surfaces(root, host_profile(previous_id), keep, apply))
    gsd_sync = sync_gsd_runtime(root, profile, apply)
    actions.append({"action": gsd_sync["action"], "target": gsd_sync["target"], "source": "forge-gsd-runtime-sync"})

    surfaces = [destination for destination, _ in rendered_surfaces(root, profile)]
    state = write_runtime(root, profile, surfaces, apply, note="host set" if previous_id == host_id else f"swapped from {previous_id}")
    return {
        "schema": "forge.host-swap/v1",
        "gsd_runtime": gsd_sync,
        "mode": "apply" if apply else "dry-run",
        "project": str(root),
        "previous_host": previous_id,
        "active_host": host_id,
        "swapped": previous_id != host_id,
        "actions": actions,
        "runtime": state,
        "follow_up": [
            f"Start a fresh {profile.get('display_name', host_id)} session in {root}.",
            f"Run {host_command(profile, 'forge-next')} so Forge resumes from files rather than chat.",
            "Re-run capability detection; qualification evidence from the previous host is stale.",
        ],
    }
