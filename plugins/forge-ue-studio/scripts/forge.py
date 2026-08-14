#!/usr/bin/env python3
"""Read-only Forge survey plus a reversible, no-download project overlay installer."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


STATUSES = {
    "AVAILABLE_VERIFIED",
    "AVAILABLE_UNVERIFIED",
    "UNAVAILABLE_OPTIONAL",
    "UNAVAILABLE_BLOCKING",
    "STALE",
}

SCHEMA_FILES = {
    "attempt-result": "attempt-result.schema.json",
    "capability-contract": "capability-contract.schema.json",
    "lane-lease": "lane-lease.schema.json",
    "learning-record": "learning-record.schema.json",
    "provider-evaluation": "provider-evaluation.schema.json",
    "research-record": "research-record.schema.json",
    "review-cycle": "review-cycle.schema.json",
    "route-request": "route-request.schema.json",
    "work-packet": "work-packet.schema.json",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def executable(*names: str) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return str(Path(found).resolve())
    return None


def command_probe(command: list[str], timeout: int = 8) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "exit_code": None, "output": "", "error": str(exc)}
    output = completed.stdout.strip()
    error_lines = [line.strip() for line in completed.stderr.splitlines() if line.strip()]
    actionable_error = next((line for line in error_lines if "Error:" in line or "ENOENT" in line), error_lines[-1] if error_lines else "")
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "output": output,
        "error": actionable_error,
    }


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


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON {path}: {exc}") from exc


def find_uproject(project: Path) -> Path | None:
    if project.is_file() and project.suffix.lower() == ".uproject":
        return project.resolve()
    if not project.is_dir():
        return None
    files = sorted(project.glob("*.uproject"))
    return files[0].resolve() if len(files) == 1 else None


def plugin_names(uproject: Path | None) -> list[str]:
    if not uproject:
        return []
    data = load_json(uproject)
    names = []
    for item in data.get("Plugins", []):
        if isinstance(item, dict) and item.get("Enabled") is not False and item.get("Name"):
            names.append(str(item["Name"]))
    return sorted(set(names), key=str.casefold)


def capability(name: str, provider: str, status: str, lane: str, reason: str) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"Invalid status: {status}")
    if provider == "codex":
        kind, locality = "resident-model", "resident"
    elif provider in {"local-model-runtime", "kimi-k3-local"} or provider.startswith("ollama:"):
        kind, locality = "local-model", "local"
    elif provider == "kimi-k3-api":
        kind, locality = "remote-model", "remote"
    elif provider in {"blender", "unreal-control-rig"}:
        kind, locality = "dcc", "local"
    elif lane.startswith("ue-") or provider in {"uproject", "unreal-native-mcp", "vibeue", "unreal-python"}:
        kind, locality = "engine", "local"
    else:
        kind, locality = "cli", "local"
    qualified = status == "AVAILABLE_VERIFIED"
    return {
        "capability": name,
        "provider": provider,
        "kind": kind,
        "status": status,
        "lane": lane,
        "locality": locality,
        "executable_surfaces": [],
        "permissions": {"read": [], "write": [], "network": locality == "remote", "secrets": False},
        "integrity": {"state": "UNRECORDED"},
        "provenance": {"source": "forge-survey"},
        "license": None,
        "health": "HEALTHY" if qualified else "UNKNOWN",
        "qualification": {"state": "QUALIFIED" if qualified else "UNQUALIFIED", "task_classes": [name] if qualified else []},
        "cost": {"class": "unknown"},
        "context_cost": {"measured": False},
        "enables": [],
        "constraints": [],
        "fallbacks": ["resident-codex"] if provider != "codex" else [],
        "probe": "detection-only" if not qualified else "safe-host-probe",
        "acceptance_suites": ["FORGE-CAP-01"],
        "invalidation_triggers": ["version", "path", "schema", "permissions", "environment"],
        "reason": reason,
    }


def survey(project_value: str) -> dict[str, Any]:
    requested = Path(project_value).expanduser()
    uproject = find_uproject(requested)
    project = (uproject.parent if uproject else requested).resolve()
    plugins = plugin_names(uproject)
    lower_plugins = {name.casefold() for name in plugins}

    tools = {
        "python": sys.executable,
        "node": executable("node", "node.exe"),
        "codex": executable("codex", "codex.exe"),
        "gsd_tools": executable("gsd-tools", "gsd-tools.cmd", "gsd-tools.exe"),
        "git": executable("git", "git.exe"),
        "blender": executable("blender", "blender.exe"),
        "ollama": executable("ollama", "ollama.exe"),
        "lm_studio": executable("lms", "lms.exe", "lm-studio", "lm-studio.exe"),
        "llama_server": executable("llama-server", "llama-server.exe"),
        "kimi_cli": executable("kimi", "kimi.exe", "kimi-cli", "kimi-cli.exe"),
        "unreal_editor": executable("UnrealEditor", "UnrealEditor.exe"),
        "unreal_editor_cmd": executable("UnrealEditor-Cmd", "UnrealEditor-Cmd.exe"),
    }
    installed_ollama_models = ollama_models(tools["ollama"])
    lm_studio_probe = command_probe([tools["lm_studio"], "ls"]) if tools["lm_studio"] else None
    codex_root = Path.home() / ".codex"
    gsd_skill_roots = [Path.home() / ".agents" / "skills", codex_root / "skills"]
    gsd_skills = sorted(
        {path.name for root in gsd_skill_roots for path in root.glob("gsd-*") if path.is_dir()}
    )
    gsd_agents = sorted(path.name for path in (codex_root / "agents").glob("gsd-*.toml") if path.is_file())
    gsd_core = codex_root / "gsd-core"
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
            "worker.codex.resident",
            "codex",
            "AVAILABLE_UNVERIFIED",
            "codex-host",
            "Forge declares Codex as resident default; current model, image generation and tool scopes require host introspection",
        ),
        capability(
            "workflow.gsd",
            "gsd-core",
            "AVAILABLE_UNVERIFIED" if gsd_detected else "UNAVAILABLE_BLOCKING",
            "codex-host",
            (
                f"Detected GSD Core {gsd_version}, {len(gsd_skills)} GSD skills, {len(gsd_agents)} GSD agents"
                + (f", and gsd-tools at {tools['gsd_tools']}" if tools["gsd_tools"] else "; gsd-tools was not found on PATH")
                + (f"; version probe: {gsd_probe['output'] or gsd_probe['error']}" if gsd_probe else "")
                + "; fresh-session compatibility still requires verification"
            )
            if gsd_detected
            else "GSD Core was not detected; install the pinned Codex runtime before full phase execution",
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
        capability(
            "model.kimi.local",
            "kimi-k3-local",
            "AVAILABLE_UNVERIFIED" if tools["kimi_cli"] else "UNAVAILABLE_OPTIONAL",
            "model-local",
            "Kimi-like CLI detected; model identity, modality and performance need probes" if tools["kimi_cli"] else "No Kimi CLI was found on PATH",
        ),
        capability(
            "model.kimi.api",
            "kimi-k3-api",
            "AVAILABLE_UNVERIFIED" if os.environ.get("KIMI_API_KEY") else "UNAVAILABLE_OPTIONAL",
            "network",
            "Credential presence detected; value was not read or stored" if os.environ.get("KIMI_API_KEY") else "KIMI_API_KEY is not present",
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
        "Codex is the resident default, but this standalone survey cannot prove the host's current image generation or tool scopes.",
        "A local runtime, Kimi executable, or credential does not prove model identity, task quality, complexity ceiling, context savings, or tool access.",
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
        "providers": {
            "resident_default": "codex",
            "codex_cli_detected": bool(tools["codex"]),
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
            "codex_capabilities_require_host_probe": ["visual-generation", "image-editing", "blender-operation", "unreal-operation"],
            "local_worker_candidates": [name for name in ("ollama", "lm_studio", "llama_server", "kimi_cli") if tools[name]],
            "kimi_local_detected": bool(tools["kimi_cli"]),
            "kimi_api_credential_present": bool(os.environ.get("KIMI_API_KEY")),
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


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def template_root() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "project-template"


def template_files() -> list[tuple[Path, Path]]:
    root = template_root()
    return [(source, source.relative_to(root)) for source in sorted(root.rglob("*")) if source.is_file()]


def proposal_path(destination: Path, source: Path) -> Path:
    candidate = destination.with_name(destination.name + ".forge-proposed")
    if not candidate.exists() or file_digest(candidate) == file_digest(source):
        return candidate
    index = 2
    while True:
        candidate = destination.with_name(destination.name + f".forge-proposed-{index}")
        if not candidate.exists() or file_digest(candidate) == file_digest(source):
            return candidate
        index += 1


def proposal_payload_path(destination: Path, payload: bytes) -> Path:
    candidate = destination.with_name(destination.name + ".forge-proposed")
    if not candidate.exists() or hashlib.sha256(candidate.read_bytes()).digest() == hashlib.sha256(payload).digest():
        return candidate
    index = 2
    while True:
        candidate = destination.with_name(destination.name + f".forge-proposed-{index}")
        if not candidate.exists() or hashlib.sha256(candidate.read_bytes()).digest() == hashlib.sha256(payload).digest():
            return candidate
        index += 1


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
        "activation": {"mode": "phase-scoped-on-demand", "active": ["worker.codex.resident", "forge.state"]},
        "snapshot": snapshot,
    }


def write_profile(project_value: str, apply: bool) -> dict[str, Any]:
    snapshot = survey(project_value)
    profile = profile_registry(snapshot)
    project = Path(snapshot["project"]["root"])
    destination = project / ".forge" / "capabilities" / "detected.json"
    payload = (json.dumps(profile, indent=2, sort_keys=True) + "\n").encode("utf-8")
    action = "create"
    target = destination
    if destination.exists():
        try:
            existing = load_json(destination)
        except ValueError:
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


def install_overlay(project_value: str, apply: bool) -> dict[str, Any]:
    requested = Path(project_value).expanduser()
    uproject = find_uproject(requested)
    if not uproject:
        raise ValueError("Install requires a directory containing exactly one .uproject, or a .uproject path")
    root = uproject.parent
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

    detected = write_profile(str(root), apply=apply)
    actions.append({"action": detected["action"], "target": detected["target"], "source": "forge-survey"})

    return {
        "mode": "apply" if apply else "dry-run",
        "project": str(root.resolve()),
        "uproject": str(uproject),
        "actions": actions,
        "optional_changes_applied": [],
        "next": [
            "Run Survey and save a snapshot when desired.",
            "Review .forge/capabilities/detected.json and qualify optional providers by task and complexity.",
            "Review each optional dependency proposal independently.",
            "Use $forge-init to conduct the design interview and launch the playable and visual DAGs.",
        ],
    }


def verify_overlay(project_value: str) -> dict[str, Any]:
    requested = Path(project_value).expanduser()
    uproject = find_uproject(requested)
    if not uproject:
        raise ValueError("Verify requires a directory containing exactly one .uproject, or a .uproject path")
    root = uproject.parent
    checks = []
    for source, relative in template_files():
        destination = root / relative
        if not destination.exists():
            status = "MISSING"
        elif file_digest(destination) == file_digest(source):
            status = "MATCH"
        else:
            status = "LOCAL_VARIANT"
        checks.append({"path": str(destination), "status": status})
    return {"project": str(root.resolve()), "checks": checks, "ok": all(c["status"] != "MISSING" for c in checks)}


def schema_root() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas"


def validate_payload(kind: str, input_value: str) -> dict[str, Any]:
    if kind not in SCHEMA_FILES:
        raise ValueError(f"Unknown contract kind: {kind}")
    payload_path = Path(input_value).expanduser().resolve()
    payload = load_json(payload_path)
    schema = load_json(schema_root() / SCHEMA_FILES[kind])
    errors = []
    for field in schema.get("required", []):
        if field not in payload:
            errors.append(f"missing required field: {field}")
    for field, definition in schema.get("properties", {}).items():
        if field not in payload:
            continue
        if "enum" in definition and payload[field] not in definition["enum"]:
            errors.append(f"invalid {field}: {payload[field]!r}")
        if definition.get("type") == "array" and not isinstance(payload[field], list):
            errors.append(f"{field} must be an array")
        if definition.get("type") == "object" and not isinstance(payload[field], dict):
            errors.append(f"{field} must be an object")
    return {
        "schema": schema.get("$id"),
        "kind": kind,
        "input": str(payload_path),
        "ok": not errors,
        "errors": errors,
    }


def route_work(project_value: str, request_value: str) -> dict[str, Any]:
    requested = Path(project_value).expanduser()
    uproject = find_uproject(requested)
    if not uproject:
        raise ValueError("Route requires a directory containing exactly one .uproject, or a .uproject path")
    root = uproject.parent
    request_path = Path(request_value).expanduser().resolve()
    request = load_json(request_path)
    required = {"task_class", "complexity", "bounded", "required_capabilities", "required_lanes", "mutation_risk"}
    missing = sorted(required - set(request))
    if missing:
        raise ValueError("Route request missing: " + ", ".join(missing))

    policy = load_json(Path(__file__).resolve().parent.parent / "dependencies" / "route-policy.json")
    keep_on_codex = set(policy["offload_policy"]["keep_on_codex_by_default"])
    hard_resident = (
        not bool(request["bounded"])
        or request["task_class"] in keep_on_codex
        or request["complexity"] == "critical"
        or request["mutation_risk"] in {"external-write", "destructive"}
    )

    detected_path = root / ".forge" / "capabilities" / "detected.json"
    qualification_path = root / ".forge" / "capabilities" / "qualifications.json"
    detected = load_json(detected_path) if detected_path.exists() else {"providers": []}
    qualifications = load_json(qualification_path) if qualification_path.exists() else {"evaluations": []}
    provider_status = {str(item.get("id")): item.get("status") for item in detected.get("providers", [])}

    candidates = [{"provider": "codex", "eligible": True, "score": 0.0, "reason": "resident baseline"}]
    required_capabilities = set(request.get("required_capabilities", []))
    required_lanes = set(request.get("required_lanes", []))
    for evaluation in qualifications.get("evaluations", []):
        provider = str(evaluation.get("provider", ""))
        if not provider or provider == "codex":
            continue
        reasons = []
        if evaluation.get("verdict") != "PASS":
            reasons.append("evaluation did not pass")
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
                "eligible": not reasons,
                "score": round(score, 6),
                "reason": "; ".join(reasons) if reasons else "exact qualification passed",
            }
        )

    eligible_optional = sorted(
        (item for item in candidates if item["provider"] != "codex" and item["eligible"]),
        key=lambda item: (item["score"], item["provider"]),
        reverse=True,
    )
    if hard_resident:
        selected = "codex"
        decision = "resident-required-by-policy"
    elif eligible_optional and eligible_optional[0]["score"] > 0:
        selected = eligible_optional[0]["provider"]
        decision = "qualified-optional-advantage"
    else:
        selected = "codex"
        decision = "no-qualified-positive-advantage"
    return {
        "schema": "forge.route-decision/v1",
        "project": str(root.resolve()),
        "request": request,
        "selected": selected,
        "decision": decision,
        "candidates": candidates,
        "fallback": "codex",
        "requires_independent_verification": True,
    }


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
    for name in ("survey", "install", "verify", "profile"):
        command = sub.add_parser(name)
        command.add_argument("--project", required=True)
        command.add_argument("--output")
        if name in {"install", "profile"}:
            mode = command.add_mutually_exclusive_group()
            mode.add_argument("--apply", action="store_true")
            mode.add_argument("--dry-run", action="store_true")
    route = sub.add_parser("route")
    route.add_argument("--project", required=True)
    route.add_argument("--request", required=True)
    route.add_argument("--output")
    validate = sub.add_parser("validate")
    validate.add_argument("--kind", required=True, choices=sorted(SCHEMA_FILES))
    validate.add_argument("--input", required=True)
    validate.add_argument("--output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "survey":
            result = survey(args.project)
        elif args.command == "install":
            result = install_overlay(args.project, apply=bool(args.apply))
        elif args.command == "verify":
            result = verify_overlay(args.project)
        elif args.command == "profile":
            result = write_profile(args.project, apply=bool(args.apply))
        elif args.command == "route":
            result = route_work(args.project, args.request)
        else:
            result = validate_payload(args.kind, args.input)
        emit(result, args.output)
        return 0 if result.get("ok", True) else 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "command": args.command}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
