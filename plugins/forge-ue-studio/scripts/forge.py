#!/usr/bin/env python3
"""Forge survey, state-aware routing, and reversible project overlay installer."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from types import MappingProxyType
from typing import Any


def load_sibling_module(name: str) -> Any:
    """Load a module that ships beside this one, without depending on sys.path."""
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


executor = load_sibling_module("forge_executor")


STATUSES = {
    "AVAILABLE_VERIFIED",
    "AVAILABLE_UNVERIFIED",
    "UNAVAILABLE_OPTIONAL",
    "UNAVAILABLE_BLOCKING",
    "STALE",
}

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
        "MCP_FIELD_RESTATED": "mcp_field_restated",
        "MCP_INCOMPLETE_DECLARATION": "mcp_incomplete_declaration",
        "MCP_ALREADY_DECLARED": "mcp_already_declared",
        "MCP_NOT_DECLARED": "mcp_not_declared",
        "MCP_MISSING_TRANSPORT": "mcp_missing_transport",
        "MCP_NO_DECLARATION_FILE": "mcp_no_declaration_file",
        "AGENT_INVALID": "agent_invalid",
        "OVERLAY_MISSING": "overlay_missing",
        "USAGE": "usage",
        "UNKNOWN": "unknown",
        **executor.ERROR_REASONS,
    }
)

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_CONTRACT = 2
EXIT_USAGE = 3

VERDICT_COMMANDS = frozenset(
    {
        "verify",
        "bootstrap-check",
        "validate",
        "host status",
    }
)


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


def expand_host_path(value: str) -> Path:
    return Path(value).expanduser()


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


def toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def mcp_registry() -> dict[str, Any]:
    return load_json(plugin_root() / "dependencies" / "mcp-registry.json")


def mcp_providers() -> list[dict[str, Any]]:
    return list(mcp_registry().get("providers", []))


def mcp_capability_index() -> dict[str, dict[str, Any]]:
    """Capability id -> the provider row that serves it."""
    index: dict[str, dict[str, Any]] = {}
    for provider in mcp_providers():
        for capability in provider.get("capabilities", []):
            index[str(capability)] = provider
    return index


def host_speaks_mcp(profile: dict[str, Any]) -> bool:
    """A host routes typed tools only if it declares the client AND the spelling."""
    template = profile.get("mcp", {}).get("tool_namespace_template")
    return bool(template) and "mcp-client" in profile.get("provides", [])


def mcp_tool_namespace(profile: dict[str, Any], server: str) -> str | None:
    """Spell a server's tool namespace the way the active host expects."""
    template = profile.get("mcp", {}).get("tool_namespace_template")
    if not template or not server:
        return None
    return str(template).replace("{server}", str(server))


def agent_tool_surface(definition: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    """Compose an agent's tool allowlist from built-ins plus typed tool routes."""
    tools = [str(item) for item in definition.get("tools", []) if str(item).strip()]
    declared = [str(item) for item in definition.get("mcp_capabilities", []) if str(item).strip()]
    if not declared:
        return tools
    index = mcp_capability_index()
    unknown = [item for item in declared if item not in index]
    if unknown:
        known = ", ".join(sorted(index)) or "none"
        raise fail(
            f"Agent {definition.get('name')!r} declares MCP capabilities with no provider: "
            f"{', '.join(sorted(unknown))}; declared capabilities: {known}",
            reason=ERROR_REASON["MCP_UNKNOWN_CAPABILITY"],
        )
    if not host_speaks_mcp(profile):
        return tools
    for capability in declared:
        namespace = mcp_tool_namespace(profile, index[capability].get("server", ""))
        if namespace and namespace not in tools:
            tools.append(namespace)
    return tools


def _toml_table_header_declares(text: str, server_key: str, server: str) -> bool:
    """Whether an unparsed TOML config carries the `[key.server]` table header."""
    header = rf"^\s*\[{re.escape(server_key)}\.{re.escape(server)}\]"
    return re.search(header, text, re.MULTILINE) is not None


def _mcp_config_declares(path: Path, entry: dict[str, Any], server: str) -> bool:
    """Read one MCP client configuration and report whether it declares a server."""
    server_key = str(entry.get("server_key", ""))
    fmt = str(entry.get("format", "json"))
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return False
    if fmt == "json":
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            return False
        servers = document.get(server_key) if isinstance(document, dict) else None
        return isinstance(servers, dict) and server in servers
    if fmt == "toml-table":
        try:
            import tomllib

            document = tomllib.loads(text)
        except (ImportError, ValueError):
            return _toml_table_header_declares(text, server_key, server)
        servers = document.get(server_key)
        return isinstance(servers, dict) and server in servers
    return False


def mcp_endpoint_url(root: Path, provider: dict[str, Any]) -> str | None:
    """The endpoint to handshake: what the project declared, else the catalog default."""
    provider_id = str(provider.get("id", ""))
    try:
        for entry in project_mcp(root).get("servers", []):
            if str(entry.get("id")) == provider_id:
                url = str((entry.get("transport") or {}).get("url", "")).strip()
                if url:
                    return url
    except ForgeExit:
        pass
    return str(provider.get("transport_default", {}).get("url", "")).strip() or None


def probe_mcp_endpoint(url: str, timeout: float = 3.0) -> dict[str, Any]:
    """Ask a running MCP endpoint to initialize. Contacts it; never starts or writes anything."""
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "forge-capability-probe", "version": "1"},
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(8192).decode("utf-8", "replace")
            speaks_mcp = '"result"' in payload or "serverInfo" in payload
            return {
                "reachable": True,
                "speaks_mcp": speaks_mcp,
                "code": getattr(response, "status", None),
                "detail": "initialize returned an MCP result" if speaks_mcp else "endpoint answered but did not return an MCP result",
            }
    except urllib.error.HTTPError as exc:
        return {
            "reachable": True,
            "speaks_mcp": False,
            "code": exc.code,
            "detail": f"endpoint answered HTTP {exc.code}; something is listening but it did not complete an MCP initialize",
        }
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"reachable": False, "speaks_mcp": False, "code": None, "detail": f"no endpoint answered at {url}: {exc}"}


def probe_mcp_server(root: Path, profile: dict[str, Any], server: str, provider: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read-only detection: is this server declared where the host would read it?"""
    if not host_speaks_mcp(profile):
        return {
            "server": server,
            "found": False,
            "status": "UNAVAILABLE_OPTIONAL",
            "reason": f"host {profile.get('id')!r} declares no MCP client surface",
            "scope": None,
            "subagent_visible": False,
            "searched": [],
        }
    searched: list[str] = []
    result: dict[str, Any] | None = None
    for entry in profile.get("mcp", {}).get("config_paths", []):
        raw = str(entry.get("path", ""))
        if not raw:
            continue
        path = expand_host_path(raw) if raw.startswith("~") else (root / raw)
        searched.append(str(path))
        if not path.is_file():
            continue
        if _mcp_config_declares(path, entry, server):
            visible = bool(entry.get("subagent_visible"))
            result = {
                "server": server,
                "found": True,
                "status": "AVAILABLE_UNVERIFIED",
                "reason": "declared in an MCP client configuration the host reads",
                "scope": entry.get("scope"),
                "subagent_visible": visible,
                "config_path": str(path),
                "searched": searched,
                "note": None if visible else (
                    "Declared at a scope a spawned agent does not inherit. The resident session "
                    "can use it; delegated work must take the declared fallback route."
                ),
            }
            break
    if result is None:
        result = {
            "server": server,
            "found": False,
            "status": "UNAVAILABLE_OPTIONAL",
            "reason": "not declared in any MCP client configuration the host reads",
            "scope": None,
            "subagent_visible": False,
            "searched": searched,
        }
    return _apply_handshake(root, result, provider)


def _apply_handshake(root: Path, result: dict[str, Any], provider: dict[str, Any] | None) -> dict[str, Any]:
    """Upgrade a declaration to verified evidence when the provider declares a live probe."""
    if not provider or provider.get("probe") != "mcp-http-handshake":
        return result
    url = mcp_endpoint_url(root, provider)
    if not url:
        return {**result, "live": False, "endpoint": None, "note": "no http endpoint declared, so the live probe could not run"}
    handshake = probe_mcp_endpoint(url)
    live = bool(handshake["speaks_mcp"])
    enriched = {**result, "live": live, "endpoint": url, "handshake": handshake}
    if result["found"] and live:
        enriched["status"] = "AVAILABLE_VERIFIED"
        enriched["reason"] = f"declared to the host and answered an MCP initialize at {url}"
        return enriched
    if result["found"]:
        enriched["status"] = "UNAVAILABLE_OPTIONAL"
        enriched["reason"] = f"declared to the host but did not answer an MCP initialize at {url}"
        enriched["note"] = (
            f"{handshake['detail']}. A route with a live probe that fails is unavailable, not unverified, "
            "so work degrades to the declared fallback instead of dispatching into nothing. For Unreal's "
            "first-party server the editor must be open with the ModelContextProtocol and AllToolsets plugins enabled."
        )
        return enriched
    if live:
        enriched["note"] = (
            f"A live MCP server answered at {url} but no configuration the host reads declares it. "
            "Declare it with `forge.py mcp add` so this session can route to it."
        )
    return enriched


def mcp_capability_contracts(root: Path, profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Emit one forge.capability-contract/v2 per capability of every declared server."""
    contracts: list[dict[str, Any]] = []
    for provider in mcp_providers():
        server = str(provider.get("server", ""))
        probe = probe_mcp_server(root, profile, server, provider)
        missing = [item for item in provider.get("requires_host_provides", []) if item not in profile.get("provides", [])]
        if missing:
            status = "UNAVAILABLE_OPTIONAL"
        elif probe["found"]:
            status = probe["status"]
        else:
            status = "UNAVAILABLE_OPTIONAL"
        namespace = mcp_tool_namespace(profile, server)
        for capability in provider.get("capabilities", []):
            contracts.append(
                {
                    "capability": capability,
                    "provider": provider.get("id"),
                    "kind": "mcp",
                    "status": status,
                    "health": "HEALTHY" if status.startswith("AVAILABLE") else "UNAVAILABLE",
                    "lane": provider.get("lane"),
                    "locality": provider.get("locality", "local"),
                    "executable_surfaces": [namespace] if namespace else [],
                    "permissions": provider.get("permissions", {}),
                    "integrity": {"verified": False, "method": "none", "note": "MCP servers are user-installed; Forge does not vouch for them."},
                    "provenance": {"declared_by": "dependencies/mcp-registry.json", "detected_by": f"{provider.get('probe')}:{server}", "config_path": probe.get("config_path")},
                    "qualification": {"state": "UNQUALIFIED", "task_classes": []},
                    "cost": {"monetary": 0, "note": "Local server; cost is host context plus latency."},
                    "context_cost": {"measured": False, "note": "Measure on the active host; never copy another runtime's estimate."},
                    "fallbacks": provider.get("fallbacks", []),
                    "probe": f"{provider.get('probe')}:{server}",
                    "acceptance_suites": provider.get("acceptance_suites", []),
                    "invalidation_triggers": provider.get("invalidation_triggers", []),
                    "subagent_visible": probe["subagent_visible"],
                    "detection_note": probe.get("note") or probe.get("reason"),
                }
            )
    return contracts


def render_agent(definition: dict[str, Any], profile: dict[str, Any]) -> str:
    """Render a neutral agent definition into the active host's agent format."""
    name = str(definition.get("name", "")).strip()
    description = render_tokens(str(definition.get("description", "")).strip(), profile)
    instructions = render_tokens(str(definition.get("instructions", "")).strip(), profile)
    if not name:
        raise fail("Agent definition is missing a name", reason=ERROR_REASON["AGENT_INVALID"])
    tools = agent_tool_surface(definition, profile)
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


def project_mcp_path(canon_root: Path) -> Path:
    return canon_root / ".forge" / "mcp.json"


def project_mcp(canon_root: Path) -> dict[str, Any]:
    path = project_mcp_path(canon_root)
    if not path.is_file():
        return {"schema": "forge.project-mcp/v1", "servers": []}
    return load_json(path)


def resolve_project_servers(canon_root: Path) -> list[dict[str, Any]]:
    """Resolve the servers declared on disk against the shipped catalog."""
    return resolve_declared_servers(project_mcp(canon_root))


def resolve_declared_servers(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve a project MCP document against the shipped catalog."""
    catalog = {str(item.get("id")): item for item in mcp_providers()}
    inherited = ("server", "capabilities", "lane", "isolation_mode", "fallbacks")
    resolved: list[dict[str, Any]] = []
    for entry in document.get("servers", []):
        entry_id = str(entry.get("id", ""))
        if not entry_id:
            raise fail("Project MCP entry has no id", reason=ERROR_REASON["MCP_INCOMPLETE_DECLARATION"])
        row = catalog.get(entry_id)
        if row is not None:
            restated = [field for field in inherited if field in entry]
            if restated:
                raise fail(
                    f"Project MCP entry {entry_id!r} restates catalog-owned field(s): "
                    f"{', '.join(sorted(restated))}. Remove them; the catalog is the single truth.",
                    reason=ERROR_REASON["MCP_FIELD_RESTATED"],
                )
            merged = {field: row.get(field) for field in inherited}
            source = "catalog"
        else:
            missing = [field for field in inherited if not entry.get(field)]
            if missing:
                raise fail(
                    f"Project MCP entry {entry_id!r} is not in the catalog and must declare "
                    f"{', '.join(sorted(missing))} so routing can resolve it.",
                    reason=ERROR_REASON["MCP_INCOMPLETE_DECLARATION"],
                )
            merged = {field: entry.get(field) for field in inherited}
            source = "project"
        resolved.append(
            {
                "id": entry_id,
                "enabled": bool(entry.get("enabled", True)),
                "transport": entry.get("transport", {}),
                "scope": str(entry.get("scope", "project")),
                "source": source,
                **merged,
            }
        )
    return resolved


def render_project_mcp(root: Path, profile: dict[str, Any], canon_root: Path) -> tuple[Path, bytes] | None:
    """Render the project's MCP surface, preserving servers Forge does not own."""
    surface = profile.get("mcp", {}).get("project_surface")
    if not surface:
        return None
    servers = resolve_project_servers(canon_root)
    managed = {
        str(item["server"]): item
        for item in servers
        if str(item.get("scope", "project")) in {"project", "both"}
    }
    target = root / str(surface.get("path"))
    server_key = str(surface.get("server_key", "mcpServers"))
    if not managed and not target.is_file():
        return None

    document: dict[str, Any] = {}
    if target.is_file():
        try:
            existing = load_json(target)
            if isinstance(existing, dict):
                document = existing
        except ForgeExit:
            document = {}
    current = document.get(server_key)
    entries = dict(current) if isinstance(current, dict) else {}

    for name in list(entries):
        if name in managed and not managed[name]["enabled"]:
            del entries[name]
    for name, item in managed.items():
        if not item["enabled"]:
            continue
        entries[name] = _mcp_transport_entry(item)

    document[server_key] = dict(sorted(entries.items()))
    body = json.dumps(document, indent=2, sort_keys=True) + "\n"
    return target, body.encode("utf-8")


def _mcp_transport_entry(item: dict[str, Any]) -> dict[str, Any]:
    """Render one server the way an MCP client reads it: a command it starts, or a url it calls."""
    transport = item.get("transport") or {}
    url = str(transport.get("url", "")).strip()
    if url:
        return {"type": str(transport.get("type") or "http"), "url": url}
    rendered: dict[str, Any] = {"command": transport.get("command", "")}
    if transport.get("args"):
        rendered["args"] = list(transport["args"])
    if transport.get("env"):
        rendered["env"] = dict(transport["env"])
    return rendered


def sync_user_mcp(root: Path, profile: dict[str, Any], apply: bool) -> dict[str, Any]:
    """Publish user-scoped routes so agents this session spawns can see them."""
    surface = profile.get("mcp", {}).get("user_surface")
    wanted = {
        str(item["server"]): item
        for item in resolve_project_servers(root)
        if item["enabled"] and str(item.get("scope", "project")) in {"user", "both"}
    }
    if not surface:
        return {
            "schema": "forge.mcp-user-sync/v1", "mode": "unsupported", "applied": False,
            "reason": f"host {profile.get('id')!r} declares no user-scope MCP surface",
            "wanted": sorted(wanted), "planned": [], "target": None,
        }
    target = expand_host_path(str(surface.get("path")))
    server_key = str(surface.get("server_key", "mcpServers"))
    if not surface.get("writable"):
        return {
            "schema": "forge.mcp-user-sync/v1", "mode": "report-only", "applied": False,
            "reason": surface.get("note") or "this host's user surface is not machine-writable by Forge",
            "target": str(target), "wanted": sorted(wanted),
            "planned": [
                {"action": "declare-by-hand", "server": name, "entry": _mcp_transport_entry(item)}
                for name, item in sorted(wanted.items())
            ],
        }

    document: dict[str, Any] = {}
    if target.is_file():
        try:
            loaded = load_json(target)
            if isinstance(loaded, dict):
                document = loaded
        except ForgeExit:
            return {
                "schema": "forge.mcp-user-sync/v1", "mode": "blocked", "applied": False,
                "reason": f"{target} is not readable JSON; refusing to rewrite a config we cannot parse",
                "target": str(target), "wanted": sorted(wanted), "planned": [],
            }
    current = document.get(server_key)
    entries = dict(current) if isinstance(current, dict) else {}

    declared_servers = {str(item["server"]) for item in resolve_project_servers(root)}
    planned: list[dict[str, Any]] = []
    for name, item in sorted(wanted.items()):
        rendered = _mcp_transport_entry(item)
        if name not in entries:
            planned.append({"action": "add", "server": name, "entry": rendered})
        elif entries[name] != rendered:
            planned.append({"action": "update", "server": name, "entry": rendered, "existing": entries[name]})
    for name in sorted(entries):
        if name in wanted or name not in declared_servers:
            continue
        item = next((i for i in resolve_project_servers(root) if str(i["server"]) == name), None)
        if item is not None and entries[name] == _mcp_transport_entry(item):
            planned.append({"action": "remove", "server": name})
        else:
            planned.append({"action": "retain-modified", "server": name, "reason": "entry differs from what Forge renders"})

    if not apply:
        return {
            "schema": "forge.mcp-user-sync/v1", "mode": "dry-run", "applied": False,
            "target": str(target), "wanted": sorted(wanted), "planned": planned,
            "consent_required": bool(planned),
        }

    for change in planned:
        if change["action"] in {"add", "update"}:
            entries[change["server"]] = change["entry"]
        elif change["action"] == "remove":
            entries.pop(change["server"], None)
    document[server_key] = entries
    backup = None
    if target.is_file():
        backup = target.with_suffix(target.suffix + ".forge-backup")
        backup.write_bytes(target.read_bytes())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    record_consent(
        root,
        "mcp.user-scope-write",
        f"Wrote {len([c for c in planned if c['action'] in {'add', 'update', 'remove'}])} server entr(ies) to {target}",
        [change["server"] for change in planned],
    )
    return {
        "schema": "forge.mcp-user-sync/v1", "mode": "apply", "applied": True,
        "target": str(target), "backup": str(backup) if backup else None,
        "wanted": sorted(wanted), "planned": planned,
    }


def record_consent(root: Path, scope: str, detail: str, subjects: list[str]) -> None:
    """Append a scoped consent entry recording an external write."""
    path = root / ".forge" / "capabilities" / "consent-ledger.json"
    if not path.is_file():
        return
    try:
        ledger = load_json(path)
    except ForgeExit:
        return
    ledger.setdefault("entries", []).append(
        {"scope": scope, "detail": detail, "subjects": subjects, "granted_at": utc_now()}
    )
    path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


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
    outputs: list[tuple[Path, bytes]] = []

    template = canon / ".forge" / "templates" / "project-instructions.md"
    if template.is_file():
        body = render_tokens(template.read_text(encoding="utf-8-sig"), profile)
        outputs.append((root / str(surface.get("instruction_file", "AGENTS.md")), body.encode("utf-8")))

    agent_dir = root / str(surface.get("agent_dir", ".agents/agents"))
    extension = str(surface.get("agent_extension", ".md"))
    for definition in agent_definitions(canon):
        target = agent_dir / f"{definition['name']}{extension}"
        outputs.append((target, render_agent(definition, profile).encode("utf-8")))

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

    has_profile = record(
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
    _ = has_profile
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
                forge_action("planning-health", "Inspect planning health", "gsd-health", False, "Use only if the GSD skill surface is available.", profile),
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
            forge_action("project-discovery", "Start with plain project discovery", "gsd-new-project", False, "Use when Forge-specific design inception is not needed.", profile),
        ]

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
        "gsd_snapshot": snapshot,
        "gsd_error": "" if gsd.get("ok") else str(gsd.get("error", "")),
        "dispatch_contract": "choose exactly one action, dispatch it, then stop",
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


def route_work(project_value: str, request_value: str, host_override: str | None = None) -> dict[str, Any]:
    root, _ = project_root(project_value)
    profile = active_profile(root, host_override)
    request_path = Path(request_value).expanduser().resolve()
    request = load_json(request_path)
    required = {"work_order", "task_class", "complexity", "bounded", "required_capabilities", "required_lanes", "mutation_risk"}
    missing = sorted(required - set(request))
    if missing:
        raise fail("Route request missing: " + ", ".join(missing), reason=ERROR_REASON["CONTRACT_INVALID"], code=EXIT_USAGE)

    packet_registry_path = root / ".forge" / "state" / "packet-registry.json"
    if not packet_registry_path.is_file():
        raise fail("Canonical packet registry is missing; apply the Forge overlay before routing", reason=ERROR_REASON["OVERLAY_MISSING"])
    packet_registry = load_json(packet_registry_path)
    packets = {str(item.get("id")): item for item in packet_registry.get("packets", [])}
    aliases = {str(item.get("alias")): str(item.get("canonical")) for item in packet_registry.get("aliases", [])}
    requested_order = str(request["work_order"])
    canonical_order = aliases.get(requested_order, requested_order)
    if canonical_order not in packets:
        raise fail(f"Unregistered work_order {requested_order!r}; register the canonical packet or an explicit alias before routing", reason=ERROR_REASON["CONTRACT_INVALID"])

    policy = load_json(plugin_root() / "dependencies" / "route-policy.json")
    offload = policy["offload_policy"]
    keep_on_resident = set(offload["keep_on_resident_by_default"])
    hard_resident = (
        not bool(request["bounded"])
        or request["task_class"] in keep_on_resident
        or request["complexity"] == "critical"
        or request["mutation_risk"] in {"external-write", "destructive"}
    )

    detected_path = root / ".forge" / "capabilities" / "detected.json"
    qualification_path = root / ".forge" / "capabilities" / "qualifications.json"
    detected = load_json(detected_path) if detected_path.exists() else {"providers": []}
    qualifications = load_json(qualification_path) if qualification_path.exists() else {"evaluations": []}
    provider_status = {str(item.get("id")): item.get("status") for item in detected.get("providers", [])}

    candidates = [
        {
            "provider": RESIDENT_PROVIDER,
            "host": profile["id"],
            "eligible": True,
            "score": 0.0,
            "reason": f"resident baseline ({profile.get('display_name', profile['id'])})",
        }
    ]
    required_capabilities = set(request.get("required_capabilities", []))
    required_lanes = set(request.get("required_lanes", []))
    resident_aliases = {RESIDENT_PROVIDER, profile["id"]}
    for evaluation in qualifications.get("evaluations", []):
        provider = str(evaluation.get("provider", ""))
        if not provider or provider in resident_aliases:
            continue
        reasons = []
        if evaluation.get("verdict") != "PASS":
            reasons.append("evaluation did not pass")
        evidence_host = evaluation.get("host")
        if evidence_host and evidence_host != profile["id"]:
            reasons.append(f"qualification recorded under host {evidence_host!r}; re-probe under {profile['id']!r}")
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
                "host": evidence_host,
                "eligible": not reasons,
                "score": round(score, 6),
                "reason": "; ".join(reasons) if reasons else "exact qualification passed",
            }
        )

    eligible_optional = sorted(
        (item for item in candidates if item["provider"] != RESIDENT_PROVIDER and item["eligible"]),
        key=lambda item: (item["score"], item["provider"]),
        reverse=True,
    )
    if hard_resident:
        selected = RESIDENT_PROVIDER
        decision = "resident-required-by-policy"
    elif eligible_optional and eligible_optional[0]["score"] > 0:
        selected = eligible_optional[0]["provider"]
        decision = "qualified-optional-advantage"
    else:
        selected = RESIDENT_PROVIDER
        decision = "no-qualified-positive-advantage"
    return {
        "schema": "forge.route-decision/v1",
        "project": str(root.resolve()),
        "request": request,
        "canonical_work_order": canonical_order,
        "selected": selected,
        "resident_host": profile["id"],
        "decision": decision,
        "candidates": candidates,
        "fallback": RESIDENT_PROVIDER,
        "requires_independent_verification": True,
    }


def execute_acquire(project_value: str, packet_value: str, owner: str | None, apply: bool, host_override: str | None = None) -> dict[str, Any]:
    """Take the leases and isolation a work packet declares, as one transaction."""
    root, _ = project_root(project_value)
    profile = active_profile(root, host_override)
    packet_path = Path(packet_value).expanduser().resolve()
    packet = load_json(packet_path)
    result = executor.acquire(root, packet, owner or str(profile["id"]), apply=apply)
    return {**result, "packet": str(packet_path), "host": profile["id"]}


def execute_release(project_value: str, work_order: str, outcome: str, apply: bool) -> dict[str, Any]:
    root, _ = project_root(project_value)
    return executor.release(root, work_order, outcome, apply=apply)


def execute_status(project_value: str) -> dict[str, Any]:
    root, _ = project_root(project_value)
    return executor.status(root)


def emit(data: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(data, indent=2, sort_keys=True)
    print(rendered)
    if output:
        target = Path(output).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")


def mcp_amend(
    root: Path,
    profile: dict[str, Any],
    action: str,
    server_id: str,
    apply: bool,
    command: str | None = None,
    args: list[str] | None = None,
    scope: str = "project",
    url: str | None = None,
) -> dict[str, Any]:
    """Add, remove, enable or disable one of this project's typed tool routes."""
    path = project_mcp_path(root)
    if not path.is_file():
        raise fail(f"{path} does not exist; run the Forge overlay install first", reason=ERROR_REASON["MCP_NO_DECLARATION_FILE"])
    document = load_json(path)
    servers = list(document.get("servers", []))
    index = next((i for i, item in enumerate(servers) if str(item.get("id")) == server_id), None)
    catalog = {str(item.get("id")): item for item in mcp_providers()}

    if action == "add":
        if index is not None:
            raise fail(f"{server_id!r} is already declared; use enable or remove", reason=ERROR_REASON["MCP_ALREADY_DECLARED"], code=EXIT_USAGE)
        default_url = str((catalog.get(server_id, {}).get("transport_default") or {}).get("url", "")).strip()
        endpoint = (url or "").strip() or ("" if command else default_url)
        if not command and not endpoint:
            raise fail(
                f"Declare how {server_id!r} is reached: --command for a server Forge starts, "
                "--url for one that is already listening",
                reason=ERROR_REASON["MCP_MISSING_TRANSPORT"],
                code=EXIT_USAGE,
            )
        if command and endpoint:
            raise fail(
                f"{server_id!r} cannot be both started and connected to; pass --command or --url, not both",
                reason=ERROR_REASON["MCP_MISSING_TRANSPORT"],
                code=EXIT_USAGE,
            )
        transport: dict[str, Any] = {"type": "http", "url": endpoint} if endpoint else {"command": command}
        entry: dict[str, Any] = {"id": server_id, "enabled": True, "transport": transport}
        if args and command:
            entry["transport"]["args"] = list(args)
        if scope != "project":
            entry["scope"] = scope
        servers.append(entry)
    elif action == "remove":
        if index is None:
            raise fail(f"{server_id!r} is not declared", reason=ERROR_REASON["MCP_NOT_DECLARED"], code=EXIT_USAGE)
        servers.pop(index)
    elif action in {"enable", "disable"}:
        if index is None:
            raise fail(f"{server_id!r} is not declared", reason=ERROR_REASON["MCP_NOT_DECLARED"], code=EXIT_USAGE)
        servers[index] = {**servers[index], "enabled": action == "enable"}
    else:
        raise fail(f"Unknown amend action {action!r}", reason=ERROR_REASON["USAGE"], code=EXIT_USAGE)

    staged = {**document, "servers": servers}
    resolve_declared_servers(staged)
    if apply:
        path.write_text(json.dumps(staged, indent=2) + "\n", encoding="utf-8")
        rendered = render_project_mcp(root, profile, root)
        if rendered is not None:
            target, body = rendered
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
    return {
        "schema": "forge.mcp-amend/v1",
        "action": action,
        "id": server_id,
        "mode": "apply" if apply else "dry-run",
        "declared": [item.get("id") for item in staged["servers"]],
        "target": str(path),
    }


def mcp_status(root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    """Report every typed tool route: what it serves, its lane, and whether it is bound."""
    contracts = mcp_capability_contracts(root, profile)
    declared = resolve_project_servers(root)
    declared_ids = {item["id"] for item in declared}
    surface = profile.get("mcp", {}).get("project_surface")
    catalog = {str(row.get("id")): row for row in mcp_providers()}
    routes = []
    for item in declared:
        server = str(item.get("server", ""))
        probe = probe_mcp_server(root, profile, server, catalog.get(str(item["id"])))
        routes.append(
            {
                "provider": item["id"],
                "server": server,
                "source": item["source"],
                "enabled": item["enabled"],
                "scope": item.get("scope", "project"),
                "capabilities": item.get("capabilities", []),
                "lane": item.get("lane"),
                "isolation_mode": item.get("isolation_mode"),
                "tool_namespace": mcp_tool_namespace(profile, server),
                "declared_in_project": True,
                "rendered_to_host": bool(surface) and item["enabled"],
                "session_visible": bool(surface) and item["enabled"] and probe["found"],
                "subagent_visible": probe["subagent_visible"],
                "found": probe["found"],
                "found_in_scope": probe["scope"],
                "endpoint": probe.get("endpoint"),
                "live": probe.get("live"),
                "status": probe["status"],
                "fallbacks": item.get("fallbacks", []),
                "note": probe.get("note") or probe.get("reason"),
            }
        )
    return {
        "schema": "forge.mcp-status/v1",
        "project": str(root),
        "host": profile.get("id"),
        "host_speaks_mcp": host_speaks_mcp(profile),
        "project_surface": (surface or {}).get("path") if surface else None,
        "project_surface_note": profile.get("mcp", {}).get("project_surface_note"),
        "routes": routes,
        "available_uncommitted": [
            {"provider": row.get("id"), "server": row.get("server"), "capabilities": row.get("capabilities", [])}
            for row in mcp_providers()
            if row.get("id") not in declared_ids
        ],
        "contracts": contracts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("survey", "install", "verify", "profile", "next", "bootstrap-check"):
        command = sub.add_parser(name)
        command.add_argument("--project", required=True)
        command.add_argument("--host", help="Override the assigned runtime host for this invocation")
        command.add_argument("--output")
        if name in {"install", "profile"}:
            mode = command.add_mutually_exclusive_group()
            mode.add_argument("--apply", action="store_true")
            mode.add_argument("--dry-run", action="store_true")
    gsd_sync = sub.add_parser("gsd-sync", help="Write GSD's runtime key from the assigned host")
    gsd_sync.add_argument("--project", required=True)
    gsd_sync.add_argument("--host")
    gsd_sync.add_argument("--apply", action="store_true")
    gsd_sync.add_argument("--output")
    host = sub.add_parser("host", help="Inspect or assign the resident runtime host")
    host_sub = host.add_subparsers(dest="host_command", required=True)
    host_list_parser = host_sub.add_parser("list", help="List known runtime hosts and their prerequisites")
    host_list_parser.add_argument("--output")
    host_status_parser = host_sub.add_parser("status", help="Show the assigned runtime and surface freshness")
    host_status_parser.add_argument("--project", required=True)
    host_status_parser.add_argument("--host")
    host_status_parser.add_argument("--output")
    host_set_parser = host_sub.add_parser("set", help="Assign or swap the resident runtime host")
    host_set_parser.add_argument("--project", required=True)
    host_set_parser.add_argument("--host", required=True)
    host_set_parser.add_argument("--apply", action="store_true")
    host_set_parser.add_argument("--output")
    route = sub.add_parser("route")
    route.add_argument("--project", required=True)
    route.add_argument("--host")
    route.add_argument("--request", required=True)
    route.add_argument("--output")
    mcp_status_parser = sub.add_parser("mcp-status", help="Report this project's typed tool routes")
    mcp_status_parser.add_argument("--project", required=True)
    mcp_status_parser.add_argument("--host")
    mcp_status_parser.add_argument("--output")
    mcp = sub.add_parser("mcp", help="Declare or amend the typed tool routes this project uses")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    for action in ("add", "remove", "enable", "disable"):
        amend = mcp_sub.add_parser(action)
        amend.add_argument("--project", required=True)
        amend.add_argument("--host")
        amend.add_argument("--id", required=True)
        amend.add_argument("--apply", action="store_true")
        amend.add_argument("--output")
        if action == "add":
            amend.add_argument("--command", dest="server_command", help="Executable that starts the server")
            amend.add_argument("--arg", action="append", dest="args", help="Repeatable argument")
            amend.add_argument("--url", help="Endpoint of a server that is already listening, such as Unreal's editor-hosted route")
            amend.add_argument(
                "--scope", choices=["project", "user", "both"], default="project",
                help="project: this game's session sees it. user/both: agents it spawns see it too, via a consented machine-wide write.",
            )
    sync_user = mcp_sub.add_parser("sync-user", help="Publish user-scoped routes so spawned agents can see them")
    sync_user.add_argument("--project", required=True)
    sync_user.add_argument("--host")
    sync_user.add_argument("--apply", action="store_true")
    sync_user.add_argument("--output")
    validate = sub.add_parser("validate")
    validate.add_argument("--kind", required=True, choices=sorted(SCHEMA_FILES))
    validate.add_argument("--input", required=True)
    validate.add_argument("--output")
    execution = sub.add_parser("exec", help="Hold leases and isolation for a work packet, transactionally")
    execution_sub = execution.add_subparsers(dest="exec_command", required=True)
    acquire_parser = execution_sub.add_parser("acquire", help="Take every lease and isolation the packet declares")
    acquire_parser.add_argument("--project", required=True)
    acquire_parser.add_argument("--packet", required=True)
    acquire_parser.add_argument("--owner", help="Who holds the lease; defaults to the assigned host")
    acquire_parser.add_argument("--host")
    acquire_parser.add_argument("--apply", action="store_true")
    acquire_parser.add_argument("--output")
    release_parser = execution_sub.add_parser("release", help="Release a work order's leases and tear down isolation")
    release_parser.add_argument("--project", required=True)
    release_parser.add_argument("--work-order", dest="work_order", required=True)
    release_parser.add_argument("--outcome", required=True, choices=["passed", "failed"])
    release_parser.add_argument("--apply", action="store_true")
    release_parser.add_argument("--output")
    exec_status_parser = execution_sub.add_parser("status", help="Report held leases and stale ones awaiting recovery")
    exec_status_parser.add_argument("--project", required=True)
    exec_status_parser.add_argument("--output")
    lifecycle = sub.add_parser("lifecycle")
    lifecycle.add_argument("--project", required=True)
    lifecycle.add_argument("--event", default="status", choices=["status"])
    lifecycle.add_argument("--output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "survey":
            result = survey(args.project, args.host)
        elif args.command == "install":
            result = install_overlay(args.project, apply=bool(args.apply), host_override=args.host)
        elif args.command == "verify":
            result = verify_overlay(args.project, args.host)
        elif args.command == "profile":
            result = write_profile(args.project, apply=bool(args.apply), host_override=args.host)
        elif args.command == "next":
            result = forge_next(args.project, host_override=args.host)
        elif args.command == "bootstrap-check":
            root, _ = project_root(args.project)
            result = bootstrap_verdict(root, active_profile(root, args.host))
        elif args.command == "mcp-status":
            root, _ = project_root(args.project)
            result = mcp_status(root, active_profile(root, args.host))
        elif args.command == "mcp":
            root, _ = project_root(args.project)
            profile = active_profile(root, args.host)
            if args.mcp_command == "sync-user":
                result = sync_user_mcp(root, profile, apply=bool(args.apply))
            else:
                result = mcp_amend(
                    root,
                    profile,
                    args.mcp_command,
                    args.id,
                    apply=bool(args.apply),
                    command=getattr(args, "server_command", None),
                    args=getattr(args, "args", None),
                    scope=getattr(args, "scope", "project"),
                    url=getattr(args, "url", None),
                )
        elif args.command == "gsd-sync":
            root, _ = project_root(args.project)
            result = sync_gsd_runtime(root, active_profile(root, args.host), apply=bool(args.apply))
            result = {"schema": "forge.gsd-runtime-sync/v1", "project": str(root), **result}
        elif args.command == "host":
            if args.host_command == "list":
                result = host_list()
            elif args.host_command == "status":
                result = host_status(args.project, args.host)
            else:
                result = host_set(args.project, args.host, apply=bool(args.apply))
        elif args.command == "route":
            result = route_work(args.project, args.request, args.host)
        elif args.command == "exec":
            if args.exec_command == "acquire":
                result = execute_acquire(args.project, args.packet, args.owner, apply=bool(args.apply), host_override=args.host)
            elif args.exec_command == "release":
                result = execute_release(args.project, args.work_order, args.outcome, apply=bool(args.apply))
            else:
                result = execute_status(args.project)
        elif args.command == "lifecycle":
            result = lifecycle_state(args.project, args.event)
        else:
            result = validate_payload(args.kind, args.input)
        command_path = " ".join(
            part
            for part in (
                args.command,
                getattr(args, "host_command", None),
                getattr(args, "mcp_command", None),
                getattr(args, "exec_command", None),
            )
            if part
        )
        carries_verdict = "ok" in result
        if command_path in VERDICT_COMMANDS and not carries_verdict:
            raise fail(
                f"{command_path!r} is declared verdict-bearing but returned no 'ok'",
                reason=ERROR_REASON["RESULT_CONTRACT_VIOLATED"],
            )
        if command_path not in VERDICT_COMMANDS and carries_verdict:
            raise fail(
                f"{command_path!r} is not verdict-bearing but returned 'ok'; report the outcome in its own field",
                reason=ERROR_REASON["RESULT_CONTRACT_VIOLATED"],
            )
        if not result.get("schema"):
            raise fail(
                f"{command_path!r} returned a payload with no schema identity",
                reason=ERROR_REASON["RESULT_CONTRACT_VIOLATED"],
            )
        emit(result, args.output)
        if command_path in VERDICT_COMMANDS:
            return EXIT_OK if result["ok"] else EXIT_CONTRACT
        return EXIT_OK
    except executor.ExecutorError as exc:
        translated = fail(str(exc), reason=exc.reason, code=EXIT_CONTRACT, **exc.extra)
        print(json.dumps({**translated.payload(), "command": args.command}), file=sys.stderr)
        return translated.code
    except ForgeExit as exc:
        print(json.dumps({**exc.payload(), "command": args.command}), file=sys.stderr)
        return exc.code
    except OSError as exc:
        print(
            json.dumps({"ok": False, "reason": ERROR_REASON["JSON_UNREADABLE"], "message": str(exc), "command": args.command}),
            file=sys.stderr,
        )
        return EXIT_FAILURE
    except ValueError as exc:
        print(
            json.dumps({"ok": False, "reason": ERROR_REASON["UNKNOWN"], "message": str(exc), "command": args.command}),
            file=sys.stderr,
        )
        return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
