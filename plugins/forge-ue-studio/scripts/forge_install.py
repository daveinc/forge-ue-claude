"""The reversible project overlay: propose, apply, verify."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from forge_core import (
    ForgeExit,
    file_digest,
    load_json,
    project_root,
    proposal_path,
    proposal_payload_path,
    template_files,
    utc_now,
)
from forge_gsd import sync_gsd_runtime
from forge_hosts import active_profile, apply_host_surfaces, host_command, rendered_surfaces, write_runtime
from forge_survey import survey


def stable_profile(data: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(data))
    normalized.pop("generated_at", None)
    snapshot = normalized.get("snapshot")
    if isinstance(snapshot, dict):
        snapshot.pop("generated_at", None)
    return normalized


def profile_registry(snapshot: dict[str, Any]) -> dict[str, Any]:
    providers: dict[str, dict[str, Any]] = {}
    for item in snapshot.get("capabilities", []):
        provider_id = str(item.get("provider", "unknown"))
        providers.setdefault(
            provider_id,
            {
                "id": provider_id,
                "kind": item.get("kind", "cli"),
                "locality": item.get("locality", "local"),
                "status": item.get("status", "AVAILABLE_UNVERIFIED"),
                "health": item.get("health", "UNKNOWN"),
                "qualification": {"state": "UNQUALIFIED", "task_classes": []},
                "capabilities": [],
            },
        )
        providers[provider_id]["capabilities"].append(item.get("capability"))
    return {
        "schema": "forge.capability-registry/v2",
        "generated_at": snapshot.get("generated_at", utc_now()),
        "project": snapshot.get("project", {}),
        "environment_fingerprint": hashlib.sha256(
            json.dumps(
                {"host": snapshot.get("host"), "tools": snapshot.get("tools"), "unreal": snapshot.get("unreal")},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
        "providers": sorted(providers.values(), key=lambda item: str(item["id"]).casefold()),
        "capabilities": snapshot.get("capabilities", []),
        "activation": {"mode": "phase-scoped-on-demand", "active": ["worker.resident", "forge.state"]},
        "resident_host": snapshot.get("runtime", {}).get("active_host"),
        "snapshot": snapshot,
    }


def write_profile(project_value: str, apply: bool, host_override: str | None = None) -> dict[str, Any]:
    snapshot = survey(project_value, host_override)
    profile = profile_registry(snapshot)
    project = Path(snapshot["project"]["root"])
    destination = project / ".forge" / "capabilities" / "detected.json"
    payload = (json.dumps(profile, indent=2, sort_keys=True) + "\n").encode("utf-8")
    action = "create"
    target = destination
    if destination.exists():
        try:
            existing = load_json(destination)
        except ForgeExit:
            existing = {}
        if stable_profile(existing) == stable_profile(profile):
            action = "unchanged"
        else:
            action = "propose"
            target = proposal_payload_path(destination, payload)
    if apply and action in {"create", "propose"} and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return {
        "mode": "apply" if apply else "dry-run",
        "project": str(project),
        "action": action,
        "target": str(target),
        "profile": profile,
    }


def install_overlay(project_value: str, apply: bool, host_override: str | None = None) -> dict[str, Any]:
    root, uproject = project_root(project_value)
    actions: list[dict[str, str]] = []

    for source, relative in template_files():
        destination = root / relative
        if not destination.exists():
            action = "create"
            target = destination
        elif file_digest(destination) == file_digest(source):
            action = "unchanged"
            target = destination
        else:
            action = "propose"
            target = proposal_path(destination, source)

        actions.append({"action": action, "target": str(target), "source": str(source)})
        if apply and action in {"create", "propose"} and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    profile = active_profile(root, host_override)
    actions.extend(apply_host_surfaces(root, profile, apply))

    detected = write_profile(str(root), apply=apply, host_override=host_override)
    actions.append({"action": detected["action"], "target": detected["target"], "source": "forge-survey"})

    gsd_sync = sync_gsd_runtime(root, profile, apply)
    actions.append({"action": gsd_sync["action"], "target": gsd_sync["target"], "source": "forge-gsd-runtime-sync"})

    surfaces = [destination for destination, _ in rendered_surfaces(root, profile)]
    runtime = write_runtime(root, profile, surfaces, apply, note="initial overlay install")

    instruction_file = profile.get("project_surface", {}).get("instruction_file", "AGENTS.md")
    next_command = host_command(profile, "forge-next")
    return {
        "schema": "forge.overlay-install/v1",
        "mode": "apply" if apply else "dry-run",
        "project": str(root.resolve()),
        "uproject": str(uproject) if uproject else None,
        "project_stage": "unreal-project" if uproject else "pre-project",
        "host": profile["id"],
        "runtime": runtime,
        "actions": actions,
        "optional_changes_applied": [],
        "next": [
            f"Stop and open a fresh {profile.get('display_name', profile['id'])} session in the project so {instruction_file}, project agents, and state are loaded.",
            f"Run {next_command}; it will detect the incomplete bootstrap and route to {host_command(profile, 'forge-bootstrap')} --resume.",
            "Review .forge/capabilities/detected.json; detection does not qualify optional providers.",
            f"After every fresh-session boundary, run {next_command} to recover from persisted Forge and GSD state.",
            "To change runtime later, run: forge.py host set --host <id> --project . --apply",
        ],
    }


def verify_overlay(project_value: str, host_override: str | None = None) -> dict[str, Any]:
    root, uproject = project_root(project_value)
    profile = active_profile(root, host_override)
    checks = []
    for source, relative in template_files():
        destination = root / relative
        if not destination.exists():
            status = "MISSING"
        elif file_digest(destination) == file_digest(source):
            status = "MATCH"
        else:
            status = "LOCAL_VARIANT"
        checks.append({"path": str(destination), "status": status, "kind": "canon"})
    for destination, payload in rendered_surfaces(root, profile):
        if not destination.exists():
            status = "MISSING"
        elif destination.read_bytes() == payload:
            status = "MATCH"
        else:
            status = "LOCAL_VARIANT"
        checks.append({"path": str(destination), "status": status, "kind": "host-rendered"})
    return {
        "schema": "forge.overlay-verify/v1",
        "project": str(root.resolve()),
        "uproject": str(uproject) if uproject else None,
        "project_stage": "unreal-project" if uproject else "pre-project",
        "host": profile["id"],
        "checks": checks,
        "ok": all(c["status"] != "MISSING" for c in checks),
    }
