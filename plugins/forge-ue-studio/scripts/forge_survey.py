"""Read-only detection of what this workstation can actually do."""

from __future__ import annotations

import os
import platform
import re
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
    uproject_modules,
    utc_now,
)
from forge_hosts import active_profile, host_prerequisites, host_profiles
from forge_mcp import project_engine_version


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


CONTENT_SCAN_LIMIT = 200000


IMPORT_SOURCE_SUFFIXES = frozenset(
    {
        ".fbx", ".obj", ".abc", ".dae", ".blend", ".gltf", ".glb", ".usd", ".usda", ".usdz",
        ".psd", ".tga", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".hdr",
        ".wav", ".aif", ".aiff", ".mp3", ".ogg",
    }
)


CONTENT_NOT_OPENED = (
    "No .uasset or .umap is opened. Nothing is claimed about what an asset contains: its class, its LOD "
    "count, its Nanite setting, its material slots, its skeleton, or what it references.",
    "Only this project's own Content/ is walked. Import sources kept beside it, in a RawAssets or Art "
    "folder, are not counted, and neither is plugin content under Plugins/*/Content.",
    "Files are counted, not resolved. An asset present only in source control, a cooked copy, and an "
    "authored asset are the same file to this report.",
    f"The walk stops after {CONTENT_SCAN_LIMIT} files and says so under 'truncated'; every count below it "
    "is then a floor rather than a total.",
)


CONTENT_REQUIRES_ASSET_INSPECTION = (
    {
        "task_class": "ik-retarget",
        "needs": "whether a skeletal mesh has AnimSequences against it, or an IK Rig or IK Retargeter asset exists",
    },
    {
        "task_class": "lod-generation",
        "needs": "how many LODs a static mesh carries, and whether Nanite is enabled on the dense ones",
    },
    {
        "task_class": "bulk-property-edit",
        "needs": "the property values an asset class actually holds, which is what makes an edit bulk",
    },
)


def _ini_setting(paths: list[Path], key: str) -> str | None:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(\S.*)$", re.MULTILINE)
    for path in paths:
        if not path.is_file():
            continue
        match = pattern.search(path.read_text(encoding="utf-8-sig", errors="replace"))
        if match:
            return match.group(1).strip()
    return None


def content_survey(root: Path) -> dict[str, Any]:
    """What this project's Content tree implies, counted rather than opened.

    Onboarding an existing game means recognising which task classes it already
    needs, and that recognition was a directory walk a workflow described in
    prose. It is counted here instead: top-level folders, the .uasset and .umap
    distribution across them, and the import sources sitting beside them.

    A real game's Content/ holds tens of thousands of files, so the walk reads
    directory entries and never a file body. That ceiling is the report's
    honesty as much as its speed: three of the eight task classes cannot be
    decided without opening an asset, so they come back undetermined with what
    would settle them rather than guessed at from a filename. Raising the
    ceiling means running asset-audit in the editor, not walking harder here.
    """
    content = root / "Content"
    folders: dict[str, dict[str, Any]] = {}
    totals = {"uasset": 0, "umap": 0, "other": 0, "directories": 0}
    import_sources: dict[str, int] = {}
    scanned = 0
    truncated = False
    if content.is_dir():
        for current, directories, files in os.walk(content):
            parts = Path(current).relative_to(content).parts
            top = parts[0] if parts else "."
            bucket = folders.setdefault(top, {"name": top, "uasset": 0, "umap": 0, "other": 0, "directories": 0})
            bucket["directories"] += len(directories)
            totals["directories"] += len(directories)
            for name in files:
                if scanned >= CONTENT_SCAN_LIMIT:
                    truncated = True
                    break
                scanned += 1
                suffix = Path(name).suffix.casefold()
                kind = "uasset" if suffix == ".uasset" else "umap" if suffix == ".umap" else "other"
                bucket[kind] += 1
                totals[kind] += 1
                if suffix in IMPORT_SOURCE_SUFFIXES:
                    import_sources[suffix] = import_sources.get(suffix, 0) + 1
            if truncated:
                break

    config = [root / "Config" / "DefaultEngine.ini", root / "Config" / "DefaultGame.ini"]
    targets = sorted(path.name for path in root.glob("Source/*.Target.cs"))
    build_evidence = sorted(
        name for name in ("Binaries", "DerivedDataCache", "Intermediate", "Saved")
        if (root / name).is_dir()
    )
    signals = {
        "default_map": _ini_setting(config, "GameDefaultMap"),
        "default_game_mode": _ini_setting(config, "GlobalDefaultGameMode"),
        "config_files": [str(path) for path in config if path.is_file()],
        "targets": targets,
        "build_evidence": build_evidence,
    }

    named_folders = sorted(name for name in folders if name != ".")
    implies: list[dict[str, str]] = []
    if content.is_dir():
        implies.append(
            {
                "task_class": "asset-audit",
                "evidence": f"Content/ holds {totals['uasset']} .uasset and {totals['umap']} .umap across "
                            f"{len(named_folders)} top-level folder(s), and what any of them contains is unread",
            }
        )
        if import_sources:
            named = ", ".join(f"{count} {suffix}" for suffix, count in sorted(import_sources.items()))
            implies.append(
                {"task_class": "batch-import", "evidence": f"import sources sit beside the assets: {named}"}
            )
        if totals["umap"]:
            implies.append(
                {"task_class": "world-blockout", "evidence": f"{totals['umap']} .umap level(s) under Content/"}
            )
    if signals["default_map"] and signals["default_game_mode"]:
        implies.append(
            {
                "task_class": "pie-verification",
                "evidence": f"Config names a default map ({signals['default_map']}) and a default game mode "
                            f"({signals['default_game_mode']}), so a session has somewhere to enter",
            }
        )
    if targets or build_evidence:
        reasons = [f"build target(s): {', '.join(targets)}"] if targets else []
        if build_evidence:
            reasons.append(f"{', '.join(build_evidence)} present, so this project has been built")
        implies.append({"task_class": "cook-and-build-preparation", "evidence": "; ".join(reasons)})

    return {
        "root": str(content) if content.is_dir() else None,
        "present": content.is_dir(),
        "scanned_files": scanned,
        "truncated": truncated,
        "scan_limit": CONTENT_SCAN_LIMIT,
        "totals": totals,
        "top_level": [folders[name] for name in sorted(folders)],
        "top_level_names": named_folders,
        "import_sources": dict(sorted(import_sources.items())),
        "signals": signals,
        "implies": implies,
        "undetermined": [
            {**item, "settled_by": "asset-audit"} for item in CONTENT_REQUIRES_ASSET_INSPECTION
        ] if content.is_dir() else [],
        "not_opened": list(CONTENT_NOT_OPENED),
    }


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
        "The Content survey counts files and opens none, so a task class it leaves undetermined is undetermined rather than absent.",
    ]

    return {
        "schema": "forge.environment-snapshot/v1",
        "generated_at": utc_now(),
        "host": {"os": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
        "project": {"requested": str(requested), "root": str(project), "uproject": str(uproject) if uproject else None},
        "tools": tools,
        "content": content_survey(project),
        "unreal": {
            "engine_association": project_engine_version(uproject),
            "modules": uproject_modules(uproject),
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
