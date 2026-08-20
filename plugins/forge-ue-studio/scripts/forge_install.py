"""The reversible project overlay: propose, apply, verify."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from types import MappingProxyType
from typing import Any

from forge_core import (
    ForgeExit,
    file_digest,
    load_json,
    project_root,
    proposal_path,
    proposal_payload_path,
    template_files,
    uproject_modules,
    utc_now,
)
from forge_gsd import sync_gsd_runtime
from forge_hosts import active_profile, apply_host_surfaces, host_command, rendered_surfaces, write_runtime
from forge_mcp import project_engine_version
from forge_survey import survey


def stable_profile(data: dict[str, Any]) -> dict[str, Any]:
    """Strip what records the invocation rather than the machine, so the same
    workstation compares equal however the project path was spelled."""
    normalized = json.loads(json.dumps(data))
    for scope in (normalized, normalized.get("snapshot")):
        if not isinstance(scope, dict):
            continue
        scope.pop("generated_at", None)
        project = scope.get("project")
        if isinstance(project, dict):
            project.pop("requested", None)
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
        "schema": "forge.profile-write/v1",
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


STATE_SCHEMA_VERSION = 2


STATE_MIGRATIONS = MappingProxyType(
    {
        1: "2: install-state gained the capability ledger, qualification registry and phase activation pointers. "
           "Re-run `install --apply`, which writes them without touching recorded decisions.",
    }
)


def state_version(root: Path) -> dict[str, Any]:
    """What `.forge` claims to be, against what this build can operate on.

    A project accumulates months of decisions in `.forge`, so upgrading the
    orchestration layer over it is a real operation. State older than this build
    is migratable. State newer is not: it was written by a Forge that knows
    things this one does not, and guessing at it corrupts the record.
    """
    path = root / ".forge" / "state" / "install-state.json"
    if not path.is_file():
        return {
            "found": None,
            "supported": STATE_SCHEMA_VERSION,
            "status": "ABSENT",
            "detail": f"{path} does not exist; the overlay has not been applied",
            "migrations": [],
        }
    found = int(load_json(path).get("schema_version", 0))
    if found == STATE_SCHEMA_VERSION:
        return {
            "found": found, "supported": STATE_SCHEMA_VERSION, "status": "CURRENT",
            "detail": "the state on disk matches this build", "migrations": [],
        }
    if found > STATE_SCHEMA_VERSION:
        return {
            "found": found, "supported": STATE_SCHEMA_VERSION, "status": "NEWER",
            "detail": f"this .forge was written by a newer Forge (state v{found}; this build supports "
                      f"v{STATE_SCHEMA_VERSION}). Upgrade Forge rather than operating on state it cannot read, "
                      "because what it does not understand it would silently drop",
            "migrations": [],
        }
    return {
        "found": found, "supported": STATE_SCHEMA_VERSION, "status": "MIGRATABLE",
        "detail": f"state v{found} predates this build (v{STATE_SCHEMA_VERSION})",
        "migrations": [STATE_MIGRATIONS[step] for step in sorted(STATE_MIGRATIONS) if step >= found],
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
    state = state_version(root)
    return {
        "schema": "forge.overlay-verify/v1",
        "project": str(root.resolve()),
        "uproject": str(uproject) if uproject else None,
        "project_stage": "unreal-project" if uproject else "pre-project",
        "engine_association": project_engine_version(uproject),
        "modules": uproject_modules(uproject),
        "host": profile["id"],
        "checks": checks,
        "state_version": state,
        "ok": all(c["status"] != "MISSING" for c in checks) and state["status"] != "NEWER",
    }
