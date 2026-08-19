"""Failure contract, project and plugin paths, and the primitives every other module builds on."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from types import MappingProxyType
from typing import Any

import forge_executor as executor


STATUSES = {
    "AVAILABLE_VERIFIED",
    "AVAILABLE_UNVERIFIED",
    "UNAVAILABLE_OPTIONAL",
    "UNAVAILABLE_BLOCKING",
    "STALE",
}

OCCUPANCY = {"HELD", "FREE", "UNDETERMINED"}


def is_available(status: Any) -> bool:
    """Whether a capability status means the route can be taken right now."""
    return str(status or "").startswith("AVAILABLE")


def schema_files() -> dict[str, str]:
    """Kind -> schema filename, derived from the schemas that ship."""
    directory = Path(__file__).resolve().parent.parent / "schemas"
    return {
        path.name[: -len(".schema.json")]: path.name
        for path in sorted(directory.glob("*.schema.json"))
    }


SCHEMA_FILES = schema_files()


RESIDENT_PROVIDER = "resident"


ERROR_REASON = MappingProxyType(
    {
        "PROJECT_NOT_FOUND": "project_not_found",
        "PROJECT_NOT_ADOPTED": "project_not_adopted",
        "HOST_UNKNOWN": "host_unknown",
        "HOST_SURFACE_UNSUPPORTED": "host_surface_unsupported",
        "CONTRACT_UNKNOWN_KIND": "contract_unknown_kind",
        "CONTRACT_INVALID": "contract_invalid",
        "RESULT_CONTRACT_VIOLATED": "result_contract_violated",
        "JSON_UNREADABLE": "json_unreadable",
        "MCP_UNKNOWN_CAPABILITY": "mcp_unknown_capability",
        "CATALOG_MISSING": "tool_catalog_missing",
        "CATALOG_STALE": "tool_catalog_stale",
        "MCP_FIELD_RESTATED": "mcp_field_restated",
        "MCP_INCOMPLETE_DECLARATION": "mcp_incomplete_declaration",
        "MCP_ALREADY_DECLARED": "mcp_already_declared",
        "MCP_NOT_DECLARED": "mcp_not_declared",
        "MCP_MISSING_TRANSPORT": "mcp_missing_transport",
        "MCP_NO_DECLARATION_FILE": "mcp_no_declaration_file",
        "AGENT_INVALID": "agent_invalid",
        "OVERLAY_MISSING": "overlay_missing",
        "ROUTE_PACKET_MISMATCH": "route_packet_mismatch",
        "ROUTE_DECISION_MISSING": "route_decision_missing",
        "ROUTE_DECISION_STALE": "route_decision_stale",
        "ROUTE_UNREACHABLE": "route_unreachable",
        "ROUTE_BLOCKED": "route_blocked",
        "PROCEDURE_UNCOVERED": "procedure_uncovered",
        "ENGINE_PREREQUISITE_MISSING": "engine_prerequisite_missing",
        "USAGE": "usage",
        "UNKNOWN": "unknown",
        **executor.ERROR_REASONS,
    }
)


EXIT_OK = 0


EXIT_FAILURE = 1


EXIT_CONTRACT = 2


EXIT_USAGE = 3


class ForgeExit(Exception):
    """A failure carrying its exit code and typed reason."""

    def __init__(self, message: str, reason: str = ERROR_REASON["UNKNOWN"], code: int = EXIT_FAILURE, **extra: Any):
        super().__init__(message)
        if reason not in set(ERROR_REASON.values()):
            raise ValueError(f"ForgeExit reason {reason!r} is not declared in ERROR_REASON")
        self.reason = reason
        self.code = code
        self.extra = extra

    def payload(self) -> dict[str, Any]:
        return {"ok": False, "reason": self.reason, "message": str(self), **self.extra}


def fail(message: str, reason: str = ERROR_REASON["UNKNOWN"], code: int = EXIT_FAILURE, **extra: Any) -> ForgeExit:
    """Build the failure to raise, so a call site reads `raise fail(...)`."""
    return ForgeExit(message, reason=reason, code=code, **extra)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def expand_host_path(value: str) -> Path:
    return Path(value).expanduser()


_TOML_ESCAPES = MappingProxyType(
    {codepoint: f"\\u{codepoint:04X}" for codepoint in range(0x20)}
    | {
        0x08: "\\b",
        0x09: "\\t",
        0x0A: "\\n",
        0x0C: "\\f",
        0x0D: "\\r",
        0x22: '\\"',
        0x5C: "\\\\",
        0x7F: "\\u007F",
    }
)


def toml_escape(value: str) -> str:
    """Escape a value for a TOML basic string, including every control character the spec forbids raw."""
    return value.translate(_TOML_ESCAPES)


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


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise fail(f"Cannot read JSON {path}: {exc}", reason=ERROR_REASON["JSON_UNREADABLE"]) from exc


def find_uproject(project: Path) -> Path | None:
    if project.is_file() and project.suffix.lower() == ".uproject":
        return project.resolve()
    if not project.is_dir():
        return None
    files = sorted(project.glob("*.uproject"))
    return files[0].resolve() if len(files) == 1 else None


def project_root(project_value: str, require_uproject: bool = False) -> tuple[Path, Path | None]:
    requested = Path(project_value).expanduser()
    uproject = find_uproject(requested)
    if uproject:
        return uproject.parent, uproject
    if require_uproject:
        raise fail("This operation requires a directory containing exactly one .uproject, or a .uproject path", reason=ERROR_REASON["PROJECT_NOT_FOUND"], code=EXIT_USAGE)
    if requested.is_file():
        raise fail("Project path must be a directory or a .uproject file", reason=ERROR_REASON["PROJECT_NOT_FOUND"], code=EXIT_USAGE)
    if not requested.is_dir():
        raise fail("Project directory does not exist", reason=ERROR_REASON["PROJECT_NOT_FOUND"], code=EXIT_USAGE)
    return requested.resolve(), None


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
        raise fail(f"Invalid status: {status}", reason=ERROR_REASON["CONTRACT_INVALID"])
    if provider == RESIDENT_PROVIDER:
        kind, locality = "resident-model", "resident"
    elif provider == "local-model-runtime" or provider.startswith("ollama:"):
        kind, locality = "local-model", "local"
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
        "fallbacks": ["resident-host"] if provider != RESIDENT_PROVIDER else [],
        "probe": "detection-only" if not qualified else "safe-host-probe",
        "acceptance_suites": ["FORGE-CAP-01"],
        "invalidation_triggers": ["version", "path", "schema", "permissions", "environment"],
        "reason": reason,
    }


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def template_root() -> Path:
    return plugin_root() / "assets" / "project-template"


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


def schema_root() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas"


def validate_payload(kind: str, input_value: str) -> dict[str, Any]:
    if kind not in SCHEMA_FILES:
        raise fail(f"Unknown contract kind: {kind}", reason=ERROR_REASON["CONTRACT_UNKNOWN_KIND"], code=EXIT_USAGE)
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
