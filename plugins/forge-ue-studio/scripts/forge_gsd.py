"""The pinned phase engine: its runtime key, its smart entry, and the verbs Forge fronts."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from forge_core import ForgeExit, executable, expand_host_path, load_json, plugin_root
from forge_hosts import active_profile, host_profiles


def gsd_runtime_roots(preferred: dict[str, Any] | None = None) -> list[Path]:
    """GSD runtime locations, active host first, then every other known host."""
    ordered: list[Path] = []
    profiles = list(host_profiles().values())
    if preferred:
        profiles = [preferred] + [item for item in profiles if item["id"] != preferred["id"]]
    for profile in profiles:
        location = profile.get("gsd", {}).get("runtime_root")
        if location:
            candidate = expand_host_path(str(location))
            if candidate not in ordered:
                ordered.append(candidate)
    return ordered


def gsd_runtime(root: Path, profile: dict[str, Any] | None = None) -> tuple[str | None, str | None]:
    """Return the executable and runtime script for the installed GSD engine."""
    profile = profile or active_profile(root)
    runtime_candidates = [root / "gsd-core" / "bin" / "gsd-tools.cjs"]
    home_dir = profile.get("home", {}).get("dir")
    if home_dir:
        runtime_candidates.append(root / str(home_dir) / "gsd-core" / "bin" / "gsd-tools.cjs")
    runtime_candidates.extend(base / "bin" / "gsd-tools.cjs" for base in gsd_runtime_roots(profile))
    node = executable("node", "node.exe")
    if node:
        for candidate in runtime_candidates:
            if candidate.is_file():
                return node, str(candidate.resolve())
    cli = executable("gsd-tools", "gsd-tools.cmd", "gsd-tools.exe")
    return (cli, None) if cli else (None, None)


def gsd_runtime_name(profile: dict[str, Any]) -> str | None:
    """The identifier GSD uses for this host, or None when GSD has no name for it."""
    return profile.get("gsd", {}).get("runtime_name")


def gsd_environment(profile: dict[str, Any]) -> dict[str, str]:
    """Process environment for a gsd_run call, carrying the assigned host."""
    env = dict(os.environ)
    name = gsd_runtime_name(profile)
    if name:
        env["GSD_RUNTIME"] = name
    return env


def sync_gsd_runtime(root: Path, profile: dict[str, Any], apply: bool) -> dict[str, Any]:
    """Write GSD's `runtime` key so its emissions match the assigned host."""
    name = gsd_runtime_name(profile)
    path = root / ".planning" / "config.json"
    if not name:
        return {"action": "skipped", "reason": f"host {profile['id']!r} declares no GSD runtime name", "target": str(path)}
    if not path.is_file():
        return {"action": "deferred", "reason": "GSD .planning/config.json does not exist yet", "target": str(path)}
    try:
        config = load_json(path)
    except ForgeExit as exc:
        return {"action": "error", "reason": str(exc), "target": str(path)}
    if config.get("runtime") == name:
        return {"action": "unchanged", "runtime": name, "target": str(path)}
    config["runtime"] = name
    if apply:
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return {
        "action": "update" if apply else "would-update",
        "runtime": name,
        "previous": config.get("runtime"),
        "target": str(path),
    }


def gsd_smart_entry(root: Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read GSD's authoritative project state without mutating the project."""
    profile = profile or active_profile(root)
    runner, script = gsd_runtime(root, profile)
    if not runner:
        return {"ok": False, "error": "GSD runtime was not found", "snapshot": None}
    command = [runner, script, "smart-entry", "--json"] if script else [runner, "smart-entry", "--json"]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
            env=gsd_environment(profile),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc), "snapshot": None, "command": command}
    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        return {"ok": False, "error": error, "snapshot": None, "command": command}
    try:
        snapshot = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"GSD smart-entry returned invalid JSON: {exc}", "snapshot": None, "command": command}
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("actions"), list):
        return {"ok": False, "error": "GSD smart-entry returned no actions", "snapshot": None, "command": command}
    return {"ok": True, "error": "", "snapshot": snapshot, "command": command}


def verb_registry() -> dict[str, Any]:
    return load_json(plugin_root() / "verbs" / "registry.json")


def gsd_to_forge_verbs() -> dict[str, str]:
    """Map every GSD command Forge fronts to its Forge verb."""
    return {
        str(item["gsd"]): str(item["forge"])
        for item in verb_registry().get("verbs", [])
        if item.get("disposition", "front") == "front"
    }


def dropped_gsd_verbs() -> dict[str, str]:
    """GSD commands deliberately outside Forge's surface, with the reason."""
    return {
        str(item["gsd"]): str(item.get("reason", "outside Forge's surface"))
        for item in verb_registry().get("verbs", [])
        if item.get("disposition") == "drop"
    }


def gsd_command_name(command: str) -> str:
    """The bare `gsd-name` a command carries, before any translation."""
    return re.sub(r"^[$/]", "", command).split()[0].replace("gsd:", "gsd-")


def translate_gsd_verb(name: str) -> str | None:
    """Return the Forge verb fronting a GSD command, or None when unmapped."""
    return gsd_to_forge_verbs().get(name)


def normalize_gsd_command(command: str, profile: dict[str, Any] | None = None) -> str:
    """Render a command in Forge vocabulary, spelled for the active host."""
    prefix = (profile or {}).get("skill_invocation", {}).get("prefix", "")
    text = command.strip()

    match = re.match(r"^/gsd:([a-z0-9-]+)(.*)$", text)
    if match:
        name, tail = f"gsd-{match.group(1)}", match.group(2)
    else:
        match = re.match(r"^[$/]?((?:gsd|forge)-[a-z0-9-]+)(.*)$", text)
        if not match:
            return text
        name, tail = match.group(1), match.group(2)

    if name.startswith("gsd-"):
        translated = translate_gsd_verb(name)
        if translated is None:
            return f"{prefix}{name}{tail}  [UNMAPPED: add {name} to verbs/registry.json]"
        name = translated
    return f"{prefix}{name}{tail}"


def forge_action(
    action_id: str,
    label: str,
    command: str,
    recommended: bool = False,
    reason: str = "",
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "command": normalize_gsd_command(command, profile),
        "recommended": recommended,
        "reason": reason,
    }
