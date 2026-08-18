"""The host registry and the surfaces Forge renders into whichever runtime holds the resident seat."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from forge_core import (
    ERROR_REASON,
    EXIT_USAGE,
    ForgeExit,
    fail,
    find_uproject,
    load_json,
    plugin_root,
    proposal_payload_path,
    template_root,
    toml_escape,
    utc_now,
)
from forge_mcp import agent_route_briefing, agent_tool_surface, project_engine_version, render_project_mcp


def host_registry() -> dict[str, Any]:
    return load_json(plugin_root() / "hosts" / "registry.json")


def host_profiles() -> dict[str, dict[str, Any]]:
    return {str(profile["id"]): profile for profile in host_registry().get("hosts", [])}


def host_profile(host_id: str) -> dict[str, Any]:
    profiles = host_profiles()
    if host_id not in profiles:
        known = ", ".join(sorted(profiles))
        raise fail(f"Unknown host {host_id!r}; known hosts: {known}", reason=ERROR_REASON["HOST_UNKNOWN"], code=EXIT_USAGE)
    return profiles[host_id]


def host_command(profile: dict[str, Any], skill: str) -> str:
    """Spell a skill invocation the way the active host expects."""
    return f"{profile.get('skill_invocation', {}).get('prefix', '')}{skill}"


def render_tokens(text: str, profile: dict[str, Any]) -> str:
    """Resolve host-neutral canon tokens into host-specific text."""
    rendered = re.sub(
        r"\{\{skill:([a-z0-9:-]+)\}\}",
        lambda match: host_command(profile, match.group(1)),
        text,
    )
    surface = profile.get("project_surface", {})
    replacements = {
        "{{resident}}": str(profile.get("display_name", profile.get("id", "the resident host"))),
        "{{host_id}}": str(profile.get("id", "")),
        "{{host_display_name}}": str(profile.get("display_name", "")),
        "{{host_agent_dir}}": str(surface.get("agent_dir", "")),
        "{{host_instruction_file}}": str(surface.get("instruction_file", "")),
    }
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    return rendered


def render_agent(definition: dict[str, Any], profile: dict[str, Any], engine_version: str | None = None) -> str:
    """Render a neutral agent definition into the active host's agent format."""
    name = str(definition.get("name", "")).strip()
    description = render_tokens(str(definition.get("description", "")).strip(), profile)
    instructions = render_tokens(str(definition.get("instructions", "")).strip(), profile)
    if not name:
        raise fail("Agent definition is missing a name", reason=ERROR_REASON["AGENT_INVALID"])
    tools = agent_tool_surface(definition, profile)
    briefing = agent_route_briefing(definition, engine_version)
    if briefing:
        instructions = f"{instructions}\n\n{briefing}"
    fmt = profile.get("project_surface", {}).get("agent_format", "markdown-frontmatter")
    if fmt == "toml":
        rendered = (
            f'name = "{toml_escape(name)}"\n'
            f'description = "{toml_escape(description)}"\n'
        )
        if tools:
            rendered += "tools = [" + ", ".join(f'"{toml_escape(item)}"' for item in tools) + "]\n"
        return rendered + f'developer_instructions = "{toml_escape(instructions)}"\n'
    if fmt == "markdown-frontmatter":
        inherits_every_host_tool = not tools
        tools_line = "" if inherits_every_host_tool else f"tools: {', '.join(tools)}\n"
        return (
            "---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"{tools_line}"
            "---\n\n"
            f"{instructions}\n"
        )
    raise fail(f"Unsupported agent format: {fmt!r}", reason=ERROR_REASON["HOST_SURFACE_UNSUPPORTED"])


def agent_definitions(canon_root: Path) -> list[dict[str, Any]]:
    directory = canon_root / ".forge" / "agents"
    if not directory.is_dir():
        return []
    return [load_json(path) for path in sorted(directory.glob("*.json"))]


def canon_source(root: Path) -> Path:
    """Prefer the project's own canon; fall back to the plugin template before install."""
    return root if (root / ".forge" / "agents").is_dir() else template_root()


def rendered_surfaces(
    root: Path,
    profile: dict[str, Any],
    canon_root: Path | None = None,
) -> list[tuple[Path, bytes]]:
    """Build every host-specific file this project needs, from the neutral canon."""
    canon = canon_root or canon_source(root)
    surface = profile.get("project_surface", {})
    engine_version = project_engine_version(find_uproject(root))
    outputs: list[tuple[Path, bytes]] = []

    template = canon / ".forge" / "templates" / "project-instructions.md"
    if template.is_file():
        body = render_tokens(template.read_text(encoding="utf-8-sig"), profile)
        outputs.append((root / str(surface.get("instruction_file", "AGENTS.md")), body.encode("utf-8")))

    agent_dir = root / str(surface.get("agent_dir", ".agents/agents"))
    extension = str(surface.get("agent_extension", ".md"))
    for definition in agent_definitions(canon):
        target = agent_dir / f"{definition['name']}{extension}"
        outputs.append((target, render_agent(definition, profile, engine_version).encode("utf-8")))

    mcp_surface = render_project_mcp(root, profile, canon)
    if mcp_surface is not None:
        outputs.append(mcp_surface)
    return outputs


def runtime_path(root: Path) -> Path:
    return root / ".forge" / "runtime.json"


def read_runtime(root: Path) -> dict[str, Any] | None:
    path = runtime_path(root)
    if not path.is_file():
        return None
    try:
        return load_json(path)
    except ForgeExit:
        return None


def active_host_id(root: Path, override: str | None = None) -> str:
    """Resolve the runtime for a project: explicit override, recorded state, then default."""
    if override:
        return override
    runtime = read_runtime(root)
    if runtime and runtime.get("active_host"):
        return str(runtime["active_host"])
    return str(host_registry().get("default_host", "generic"))


def active_profile(root: Path, override: str | None = None) -> dict[str, Any]:
    return host_profile(active_host_id(root, override))


def host_prerequisites(profile: dict[str, Any]) -> dict[str, Any]:
    contract = host_registry().get("prerequisite_contract", {})
    provided = set(profile.get("provides", []))
    required = list(contract.get("required", []))
    optional = list(contract.get("optional", []))
    missing = [item for item in required if item not in provided]
    return {
        "satisfied": not missing,
        "required": required,
        "missing_required": missing,
        "optional_available": [item for item in optional if item in provided],
        "optional_missing": [item for item in optional if item not in provided],
    }


def write_runtime(root: Path, profile: dict[str, Any], surfaces: list[Path], apply: bool, note: str) -> dict[str, Any]:
    existing = read_runtime(root) or {}
    history = list(existing.get("history", []))
    previous = existing.get("active_host")
    if previous != profile["id"]:
        history.append(
            {
                "at": utc_now(),
                "from": previous,
                "to": profile["id"],
                "note": note,
            }
        )
    state = {
        "schema": "forge.runtime-state/v1",
        "active_host": profile["id"],
        "display_name": profile.get("display_name", profile["id"]),
        "portable": True,
        "prerequisites": host_prerequisites(profile),
        "canon": {
            "agents": ".forge/agents",
            "directives": ".forge/directives.md",
            "instruction_template": ".forge/templates/project-instructions.md",
            "phase_state": ".planning",
        },
        "rendered_surfaces": sorted(str(path.relative_to(root)).replace("\\", "/") for path in surfaces),
        "history": history,
        "updated_at": utc_now(),
    }
    if apply:
        path = runtime_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return state


def apply_host_surfaces(root: Path, profile: dict[str, Any], apply: bool) -> list[dict[str, str]]:
    """Write the active host's generated surfaces, preserving unrelated local files."""
    actions: list[dict[str, str]] = []
    for destination, payload in rendered_surfaces(root, profile):
        if not destination.exists():
            action, target = "create", destination
        elif destination.read_bytes() == payload:
            action, target = "unchanged", destination
        else:
            existing = destination.read_text(encoding="utf-8-sig", errors="replace")
            if "<!-- FORGE:generated" in existing or destination.parent.name == "agents":
                action, target = "regenerate", destination
            else:
                action, target = "propose", proposal_payload_path(destination, payload)
        actions.append({"action": action, "target": str(target), "source": "forge-host-render"})
        if apply and action in {"create", "regenerate"}:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        elif apply and action == "propose" and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    return actions


def retire_host_surfaces(root: Path, profile: dict[str, Any], keep: set[str], apply: bool) -> list[dict[str, str]]:
    """Remove generated surfaces belonging to a host the project no longer uses."""
    actions: list[dict[str, str]] = []
    surface = profile.get("project_surface", {})
    instruction = root / str(surface.get("instruction_file", ""))
    candidates: list[Path] = []
    if instruction.is_file() and str(instruction.relative_to(root)).replace("\\", "/") not in keep:
        if "<!-- FORGE:generated" in instruction.read_text(encoding="utf-8-sig", errors="replace"):
            candidates.append(instruction)
    agent_dir = root / str(surface.get("agent_dir", ""))
    extension = str(surface.get("agent_extension", ".md"))
    if agent_dir.is_dir():
        known = {str(item.get("name")) for item in agent_definitions(root)}
        for path in sorted(agent_dir.glob(f"*{extension}")):
            if path.stem in known and str(path.relative_to(root)).replace("\\", "/") not in keep:
                candidates.append(path)
    for path in candidates:
        actions.append({"action": "retire", "target": str(path), "source": "forge-host-swap"})
        if apply:
            path.unlink()
            parent = path.parent
            while parent != root and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
    return actions
