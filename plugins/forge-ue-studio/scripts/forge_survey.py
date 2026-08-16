"""Read-only detection of what this workstation can actually do."""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any

from forge_core import (
    RESIDENT_PROVIDER,
    capability,
    command_probe,
    executable,
    expand_host_path,
    find_uproject,
    plugin_names,
    utc_now,
)
from forge_hosts import active_profile, host_prerequisites, host_profiles


def ollama_models(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    probe = command_probe([path, "list"])
    if not probe["ok"]:
        return []
    models = []
    for line in probe["output"].splitlines()[1:]:
        columns = line.split()
        if columns:
            models.append({"id": columns[0], "qualification": "UNQUALIFIED", "source": "ollama list"})
    return models


def survey(project_value: str, host_override: str | None = None) -> dict[str, Any]:
    requested = Path(project_value).expanduser()
    uproject = find_uproject(requested)
    project = (uproject.parent if uproject else requested).resolve()
    plugins = plugin_names(uproject)
    lower_plugins = {name.casefold() for name in plugins}
    profile = active_profile(project, host_override)
    host_display = str(profile.get("display_name", profile["id"]))

    tools = {
        "python": sys.executable,
        "node": executable("node", "node.exe"),
        "gsd_tools": executable("gsd-tools", "gsd-tools.cmd", "gsd-tools.exe"),
        "git": executable("git", "git.exe"),
        "blender": executable("blender", "blender.exe"),
        "ollama": executable("ollama", "ollama.exe"),
        "lm_studio": executable("lms", "lms.exe", "lm-studio", "lm-studio.exe"),
        "llama_server": executable("llama-server", "llama-server.exe"),
        "unreal_editor": executable("UnrealEditor", "UnrealEditor.exe"),
        "unreal_editor_cmd": executable("UnrealEditor-Cmd", "UnrealEditor-Cmd.exe"),
    }
    installed_ollama_models = ollama_models(tools["ollama"])
    lm_studio_probe = command_probe([tools["lm_studio"], "ls"]) if tools["lm_studio"] else None

    host_detection = []
    for candidate in host_profiles().values():
        executables = candidate.get("cli", {}).get("executables", [])
        path = executable(*executables) if executables else None
        host_detection.append(
            {
                "id": candidate["id"],
                "display_name": candidate.get("display_name"),
                "cli_detected": bool(path) if executables else None,
                "cli_path": path,
                "gsd_runtime_present": (expand_host_path(str(candidate.get("gsd", {}).get("runtime_root", "~/.nonexistent"))) / "bin" / "gsd-tools.cjs").is_file(),
                "prerequisites": host_prerequisites(candidate),
                "active": candidate["id"] == profile["id"],
            }
        )
    for entry in host_detection:
        tools[f"host.{entry['id']}"] = entry["cli_path"]

    discovery = profile.get("discovery", {})
    gsd_skill_roots = [expand_host_path(item) for item in discovery.get("skill_roots", [])]
    gsd_skills = sorted(
        {path.name for root in gsd_skill_roots for path in root.glob("gsd-*") if path.is_dir()}
    )
    agent_root = expand_host_path(str(discovery.get("agent_root", "~/.agents/agents")))
    gsd_agents = sorted(path.name for path in agent_root.glob(str(discovery.get("agent_glob", "gsd-*"))) if path.is_file())
    gsd_core = expand_host_path(str(profile.get("gsd", {}).get("runtime_root", "~/.agents/gsd-core")))
    gsd_runtime_script = gsd_core / "bin" / "gsd-tools.cjs"
    gsd_version_file = gsd_core / "VERSION"
    gsd_version = gsd_version_file.read_text(encoding="utf-8").strip() if gsd_version_file.is_file() else None
    gsd_detected = bool(gsd_skills and gsd_agents and gsd_runtime_script.is_file() and gsd_version)
    if tools["gsd_tools"]:
        gsd_probe = command_probe([tools["gsd_tools"], "--version"])
    elif gsd_version:
        gsd_probe = {"ok": True, "exit_code": 0, "output": gsd_version, "error": "", "source": str(gsd_version_file)}
    else:
        gsd_probe = None

    native_mcp = any("mcp" in name and "vibe" not in name for name in lower_plugins)
    vibeue = any("vibeue" in name or "vibe" in name and "ue" in name for name in lower_plugins)
    python_plugin = "pythonscriptplugin" in lower_plugins
    editor_scripting = "editorscriptingutilities" in lower_plugins
    control_rig = "controlrig" in lower_plugins

    caps = [
        capability("host.python", "python", "AVAILABLE_VERIFIED", "host", sys.version.split()[0]),
        capability(
            "worker.resident",
            RESIDENT_PROVIDER,
            "AVAILABLE_UNVERIFIED",
            "resident-host",
            f"Forge declares {host_display} as the assigned resident runtime; current model, image generation and tool scopes require host introspection",
        ),
        capability(
            "workflow.gsd",
            "gsd-core",
            "AVAILABLE_UNVERIFIED" if gsd_detected else "UNAVAILABLE_BLOCKING",
            "resident-host",
            (
                f"Detected GSD Core {gsd_version}, {len(gsd_skills)} GSD skills, {len(gsd_agents)} GSD agents"
                + (f", and gsd-tools at {tools['gsd_tools']}" if tools["gsd_tools"] else "; gsd-tools was not found on PATH")
                + (f"; version probe: {gsd_probe['output'] or gsd_probe['error']}" if gsd_probe else "")
                + "; fresh-session compatibility still requires verification"
            )
            if gsd_detected
            else f"GSD Core was not detected for {host_display}; install the pinned runtime before full phase execution",
        ),
        capability(
            "vcs.git",
            "git",
            "AVAILABLE_VERIFIED" if tools["git"] else "UNAVAILABLE_BLOCKING",
            "vcs",
            tools["git"] or "Git was not found on PATH",
        ),
        capability(
            "ue.project",
            "uproject",
            "AVAILABLE_VERIFIED" if uproject else "UNAVAILABLE_BLOCKING",
            "ue-project-exclusive",
            str(uproject) if uproject else "Exactly one .uproject was not found at the supplied path",
        ),
        capability(
            "ue.live.typed",
            "unreal-native-mcp",
            "AVAILABLE_UNVERIFIED" if native_mcp else "UNAVAILABLE_OPTIONAL",
            "ue-live-native-mcp",
            "Enabled plugin declaration found; live transport and tools still need probes" if native_mcp else "No enabled native MCP-like plugin declaration found",
        ),
        capability(
            "ue.live.python",
            "vibeue",
            "AVAILABLE_UNVERIFIED" if vibeue else "UNAVAILABLE_OPTIONAL",
            "ue-live-python",
            "Enabled plugin declaration found; live execution still needs probes" if vibeue else "No enabled VibeUE-like plugin declaration found",
        ),
        capability(
            "ue.python.commandlet",
            "unreal-python",
            "AVAILABLE_UNVERIFIED" if python_plugin and tools["unreal_editor_cmd"] else "UNAVAILABLE_OPTIONAL",
            "ue-editor-closed-api",
            "Python plugin and command executable detected; result-file probe required" if python_plugin and tools["unreal_editor_cmd"] else "PythonScriptPlugin or UnrealEditor-Cmd was not detected",
        ),
        capability(
            "dcc.blender",
            "blender",
            "AVAILABLE_UNVERIFIED" if tools["blender"] else "UNAVAILABLE_OPTIONAL",
            "dcc:blender",
            "Executable detected; gateway and asset-class eval required" if tools["blender"] else "Blender was not found on PATH",
        ),
        capability(
            "dcc.unreal.animation",
            "unreal-control-rig",
            "AVAILABLE_UNVERIFIED" if control_rig and uproject else "UNAVAILABLE_OPTIONAL",
            "ue-project-exclusive",
            "ControlRig is enabled; authoring probe required" if control_rig and uproject else "ControlRig was not declared enabled",
        ),
        capability(
            "model.local.runtime",
            "local-model-runtime",
            "AVAILABLE_UNVERIFIED" if any(tools[name] for name in ("ollama", "lm_studio", "llama_server")) else "UNAVAILABLE_OPTIONAL",
            "model-local",
            "Local runtime detected; enumerate models and qualify each task/complexity class" if any(tools[name] for name in ("ollama", "lm_studio", "llama_server")) else "No supported local runtime executable was found on PATH",
        ),
    ]
    for model in installed_ollama_models:
        model_id = str(model["id"])
        safe_model_id = "".join(character if character.isalnum() else "." for character in model_id).strip(".")
        caps.append(
            capability(
                f"model.local.{safe_model_id}",
                f"ollama:{model_id}",
                "AVAILABLE_UNVERIFIED",
                "model-local",
                "Installed model detected; all task classes and complexity tiers remain UNQUALIFIED",
            )
        )

    visual_routes = []
    if tools["blender"]:
        visual_routes.append({"route": "blender", "status": "NEEDS_BENCHMARK", "advantage": "independent DCC lane"})
    if uproject:
        visual_routes.append({"route": "unreal", "status": "NEEDS_BENCHMARK", "advantage": "in-engine authoring and reduced round trips"})

    assumptions = [
        "Executable and plugin detection does not prove end-to-end capability.",
        "Unreal plugin names vary; live MCP and VibeUE discovery must inspect the configured tool surface.",
        f"{host_display} is the assigned resident runtime, but this standalone survey cannot prove the host's current image generation or tool scopes.",
        "Host detection reports which runtimes could hold the resident seat; it does not qualify any of them for a task class.",
        "A local runtime, model executable, endpoint, or credential does not prove model identity, task quality, complexity ceiling, context savings, cost, or tool access.",
        "Blender and Unreal visual routes remain unranked until representative asset-class benchmarks pass.",
    ]

    return {
        "schema": "forge.environment-snapshot/v1",
        "generated_at": utc_now(),
        "host": {"os": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
        "project": {"requested": str(requested), "root": str(project), "uproject": str(uproject) if uproject else None},
        "tools": tools,
        "unreal": {
            "plugins": plugins,
            "native_mcp_declared": native_mcp,
            "vibeue_declared": vibeue,
            "python_script_plugin": python_plugin,
            "editor_scripting_utilities": editor_scripting,
            "control_rig": control_rig,
        },
        "runtime": {
            "active_host": profile["id"],
            "display_name": host_display,
            "skill_prefix": profile.get("skill_invocation", {}).get("prefix", ""),
            "instruction_file": profile.get("project_surface", {}).get("instruction_file"),
            "agent_dir": profile.get("project_surface", {}).get("agent_dir"),
            "prerequisites": host_prerequisites(profile),
            "swappable": True,
            "detected_hosts": host_detection,
        },
        "providers": {
            "resident_default": RESIDENT_PROVIDER,
            "resident_host": profile["id"],
            "gsd_detected": gsd_detected,
            "gsd_inventory": {
                "runtime_cli": tools["gsd_tools"],
                "runtime_script": str(gsd_runtime_script) if gsd_runtime_script.is_file() else None,
                "version": gsd_version,
                "skill_roots": [str(root) for root in gsd_skill_roots],
                "skills": gsd_skills,
                "agents": gsd_agents,
                "version_probe": gsd_probe,
            },
            "resident_capabilities_require_host_probe": ["visual-generation", "image-editing", "blender-operation", "unreal-operation"],
            "local_worker_candidates": [name for name in ("ollama", "lm_studio", "llama_server") if tools[name]],
            "ollama_detected": bool(tools["ollama"]),
            "runtime_inventory": {
                "ollama_models": installed_ollama_models,
                "lm_studio": {
                    "detected": bool(tools["lm_studio"]),
                    "cli_healthy": bool(lm_studio_probe and lm_studio_probe["ok"]),
                    "error": lm_studio_probe["error"] if lm_studio_probe and not lm_studio_probe["ok"] else "",
                },
            },
        },
        "visual_route_candidates": visual_routes,
        "capabilities": caps,
        "assumptions": assumptions,
    }
