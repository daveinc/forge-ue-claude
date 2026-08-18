"""Typed tool routes: what a project declares, how it renders, and whether a server answers."""

from __future__ import annotations

import http.client
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from types import MappingProxyType
from typing import Any

import forge_executor as executor
from forge_core import (
    ERROR_REASON,
    EXIT_USAGE,
    ForgeExit,
    capability,
    executable,
    expand_host_path,
    fail,
    load_json,
    plugin_root,
    utc_now,
)


def route_registry() -> dict[str, Any]:
    return load_json(plugin_root() / "dependencies" / "route-registry.json")


def route_providers() -> list[dict[str, Any]]:
    """Every declared route, whatever kind it is reached by."""
    return list(route_registry().get("providers", []))


def mcp_providers() -> list[dict[str, Any]]:
    """Only the routes a host reaches by connecting to a server."""
    return [row for row in route_providers() if str(row.get("kind")) == "mcp"]


def process_providers() -> list[dict[str, Any]]:
    """Only the routes a host reaches by running a command."""
    return [row for row in route_providers() if str(row.get("kind")) == "process"]


def mcp_capability_index() -> dict[str, dict[str, Any]]:
    """Capability id -> the route row that serves it."""
    index: dict[str, dict[str, Any]] = {}
    for provider in route_providers():
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


def project_engine_version(uproject: Path | None) -> str | None:
    """The engine a project is associated with, which is what a catalogue is keyed by."""
    if not uproject or not uproject.exists():
        return None
    value = str(load_json(uproject).get("EngineAssociation", "")).strip()
    return value or None


def tool_catalog(server: str, engine_version: str | None = None) -> dict[str, Any]:
    """The shipped tool catalogue for a server, newest engine first when none is named."""
    if not server:
        return {}
    folder = plugin_root() / "dependencies" / "tool-catalog"
    if not folder.is_dir():
        return {}
    candidates = sorted(folder.glob(f"{server}@*.json"), reverse=True)
    if engine_version:
        exact = folder / f"{server}@{engine_version}.json"
        if exact.exists():
            return load_json(exact)
    return load_json(candidates[0]) if candidates else {}


def catalog_staleness(server: str, engine_version: str | None) -> dict[str, Any] | None:
    """Whether the shipped catalogue was written for the engine actually in use."""
    catalogue = tool_catalog(server, engine_version)
    if not catalogue:
        return {"reason": ERROR_REASON["CATALOG_MISSING"], "server": server, "engine_version": engine_version, "catalog_version": None,
                "note": f"No shipped tool catalogue for {server!r}; the agent must discover every tool name through list_toolsets."}
    catalogued = str(catalogue.get("engine_version", ""))
    if engine_version and catalogued and catalogued != engine_version:
        return {"reason": ERROR_REASON["CATALOG_STALE"], "server": server, "engine_version": engine_version, "catalog_version": catalogued,
                "note": f"The catalogue for {server!r} was read off UE {catalogued} and this project is associated with UE {engine_version}; "
                        "confirm names through describe_toolset before trusting them."}
    return None


def catalog_tools_for(server: str, capabilities: list[str], engine_version: str | None = None) -> dict[str, dict[str, Any]]:
    """Toolset -> the tools within it that serve these capabilities, and nothing else."""
    catalogue = tool_catalog(server, engine_version)
    wanted = {str(item) for item in capabilities}
    assorted: dict[str, dict[str, Any]] = {}
    for toolset, body in catalogue.get("toolsets", {}).items():
        tools = {name: spec for name, spec in body.get("tools", {}).items() if str(spec.get("capability")) in wanted}
        if tools:
            assorted[str(toolset)] = {"purpose": body.get("purpose"), "tools": tools}
    return assorted


def catalog_tool_names(provider_id: str | None, capabilities: list[str], engine_version: str | None = None) -> list[str]:
    """Just the call names a capability reaches, for a payload that should stay small."""
    index = {str(row.get("id")): row for row in route_providers()}
    provider = index.get(str(provider_id))
    if not provider:
        return []
    assorted = catalog_tools_for(str(provider.get("server", "")), capabilities, engine_version)
    return sorted(name for body in assorted.values() for name in body["tools"])


def agent_route_briefing(definition: dict[str, Any], engine_version: str | None = None) -> str:
    """What every route this agent's declared capabilities reach is like to call."""
    declared = [str(item) for item in definition.get("mcp_capabilities", []) if str(item).strip()]
    if not declared:
        return ""
    index = mcp_capability_index()
    rows: dict[str, dict[str, Any]] = {}
    for name in declared:
        row = index.get(name)
        if row is not None:
            rows.setdefault(str(row.get("id")), row)
    sections: list[str] = []
    for row in rows.values():
        served = [name for name in declared if name in set(row.get("capabilities", []))]
        surface = str(row.get("tool_surface", "") or "").strip()
        lines = [f"### `{row.get('id')}` on `{row.get('lane')}` — {', '.join(f'`{item}`' for item in served)}"]
        if surface:
            lines.append(surface)
        assorted = catalog_tools_for(str(row.get("server", "")), served, engine_version)
        for toolset, body in assorted.items():
            lines.append(f"**`{toolset}`** — {body['purpose']}")
            for name, spec in body["tools"].items():
                parameters = spec.get("parameters") or {}
                shape = "; ".join(f"`{key}`: {value}" for key, value in parameters.items()) or "no arguments"
                lines.append(f"- `{name}` — {spec.get('purpose')} Arguments: {shape}. Returns: {spec.get('returns')}")
                for known in spec.get("known_errors", []):
                    lines.append(f"  - {known}")
        sections.append(lines[0] + "\n\n" + "\n".join(lines[1:]))
    if not sections:
        return ""
    return "## The routes this agent operates\n\n" + "\n\n".join(sections)


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


def endpoint_is_listening(url: str, timeout: float = 0.35) -> bool:
    """Cheap reachability check so a closed port costs milliseconds, not a full request timeout."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    if not host:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def decode_jsonrpc(payload: str) -> dict[str, Any] | None:
    """One JSON-RPC reply out of `payload`, bare or inside SSE framing, or None."""
    text = payload.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate.startswith("data:"):
            continue
        body = candidate[5:].strip()
        if not body.startswith("{"):
            continue
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            continue
    return None


def read_jsonrpc_frame(response: Any, budget: int = 262_144) -> str:
    """Read until a reply parses, rather than reading to an end that never comes.

    Unreal answers on a `text/event-stream` with no content length and keeps the
    connection open afterwards, so there is no EOF to read to and no length to
    trust. A read that waits for the end of the stream waits until the timeout and
    then reports a live editor as a route that did not answer. Stopping at the
    first frame that decodes is what makes the probe work; a byte budget stops a
    silent stream from hanging it. `read1` matters as much as the loop: a plain
    `read(n)` on a buffered socket waits for exactly n bytes, which on a small
    reply is another way of waiting for an end that never arrives.
    """
    reader = getattr(response, "read1", response.read)
    buffered = b""
    while len(buffered) < budget:
        try:
            chunk = reader(4096)
        except OSError:
            break
        if not chunk:
            break
        buffered += chunk
        if decode_jsonrpc(buffered.decode("utf-8", "replace")) is not None:
            break
    return buffered.decode("utf-8", "replace")


def probe_mcp_endpoint(url: str, timeout: float = 3.0) -> dict[str, Any]:
    """Ask a running MCP endpoint to initialize. Contacts it; never starts or writes anything."""
    if not endpoint_is_listening(url):
        return {"reachable": False, "speaks_mcp": False, "code": None, "detail": f"nothing is listening at {url}"}
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
    parsed = urllib.parse.urlparse(url)
    opener = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = opener(parsed.hostname, parsed.port, timeout=timeout)
    try:
        connection.request(
            "POST",
            parsed.path or "/",
            body=body,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        )
        response = connection.getresponse()
        if response.status >= 400:
            return {
                "reachable": True,
                "speaks_mcp": False,
                "code": response.status,
                "detail": f"endpoint answered HTTP {response.status}; something is listening but it did not complete an MCP initialize",
            }
        answer = decode_jsonrpc(read_jsonrpc_frame(response))
        speaks_mcp = isinstance(answer, dict) and isinstance(answer.get("result"), dict)
        return {
            "reachable": True,
            "speaks_mcp": speaks_mcp,
            "code": response.status,
            "server_info": answer["result"].get("serverInfo") if speaks_mcp else None,
            "detail": "initialize returned an MCP result" if speaks_mcp else "endpoint answered but did not return an MCP result",
        }
    except (OSError, ValueError) as exc:
        return {"reachable": False, "speaks_mcp": False, "code": None, "detail": f"no endpoint answered at {url}: {exc}"}
    finally:
        connection.close()


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
        settings = unreal_mcp_settings(root)
        mismatch = endpoint_disagreement(root, url)
        enriched["engine_settings"] = settings
        enriched["endpoint_disagreement"] = mismatch
        checks = [
            "the editor is open on this project",
            "ModelContextProtocol and AllToolsets are enabled in the .uproject",
        ]
        if mismatch:
            checks.insert(0, f"THE PORT: {mismatch['detail']}")
        elif settings["declared_by_project"] and not settings["auto_start"]:
            checks.append(
                "the server was started: this project sets bAutoStartServer=False, so it does not listen unless "
                "launched with -ModelContextProtocolStartServer or started with ModelContextProtocol.StartServer"
            )
        else:
            checks.append(
                "the server was started: enabling the plugin does not make it listen. Launch with "
                "-ModelContextProtocolStartServer, set bAutoStartServer, or run ModelContextProtocol.StartServer"
            )
        enriched["note"] = (
            f"{handshake['detail']}. A route with a live probe that fails is unavailable, not unverified, "
            "so work degrades to the declared fallback instead of dispatching into nothing. Check, in order: "
            + "; ".join(f"({index}) {item}" for index, item in enumerate(checks, start=1))
            + ". Both settings are read at editor startup, so changing either takes effect only after a restart."
        )
        return enriched
    if live:
        enriched["note"] = (
            f"A live MCP server answered at {url} but no configuration the host reads declares it. "
            "Declare it with `forge.py mcp add` so this session can route to it."
        )
    return enriched


EDITOR_PROCESS_NAMES = ("unrealeditor", "ue4editor", "ue5editor")


MCP_SETTINGS_SECTION = "/Script/ModelContextProtocolEngine.ModelContextProtocolSettings"


MCP_SETTINGS_DEFAULTS = MappingProxyType({"ServerPortNumber": "8000", "ServerUrlPath": "/mcp", "bAutoStartServer": "False"})


def _ini_section(path: Path, section: str) -> dict[str, str]:
    """One INI section as keys, tolerant of Unreal's array prefixes and comments."""
    values: dict[str, str] = {}
    inside = False
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return values
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            inside = stripped[1:-1] == section
            continue
        if not inside or not stripped or stripped.startswith((";", "#")) or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip().lstrip("+-.!")] = value.strip()
    return values


def unreal_mcp_settings(root: Path) -> dict[str, Any]:
    """What the project's own config says the editor's MCP server will do.

    Forge probes an endpoint the project declares, and the editor serves one its
    settings declare. Nothing tied the two together, so a project that moved the
    port read exactly like a project whose editor was closed: a silent endpoint
    and no reason given. This reads the settings so the two can be compared.

    Layered the way Unreal layers them: the project default first, then the
    per-user saved file, which wins.
    """
    sources: list[str] = []
    values = dict(MCP_SETTINGS_DEFAULTS)
    ordered = [root / "Config" / "DefaultEditorPerProjectUserSettings.ini"]
    ordered.extend(sorted(root.glob("Saved/Config/*/EditorPerProjectUserSettings.ini")))
    for path in ordered:
        if not path.is_file():
            continue
        found = _ini_section(path, MCP_SETTINGS_SECTION)
        if found:
            values.update(found)
            sources.append(str(path))
    try:
        port = int(values.get("ServerPortNumber", 8000))
    except ValueError:
        port = None
    return {
        "declared_by_project": bool(sources),
        "sources": sources,
        "port": port,
        "url_path": values.get("ServerUrlPath", "/mcp"),
        "auto_start": str(values.get("bAutoStartServer", "False")).strip().lower() in {"true", "1"},
        "note": "settings are read at editor startup, so a change to either takes effect only after a restart",
    }


def endpoint_disagreement(root: Path, url: str | None) -> dict[str, Any] | None:
    """Whether the endpoint Forge probes is the one the editor was told to serve."""
    if not url:
        return None
    settings = unreal_mcp_settings(root)
    if settings["port"] is None:
        return None
    parsed = urllib.parse.urlparse(url)
    probed_port = parsed.port
    probed_path = parsed.path or "/"
    port_differs = probed_port is not None and probed_port != settings["port"]
    path_differs = probed_path.rstrip("/") != str(settings["url_path"]).rstrip("/")
    if not (port_differs or path_differs):
        return None
    expected = f"{parsed.scheme}://{parsed.hostname}:{settings['port']}{settings['url_path']}"
    return {
        "probed": url,
        "configured": expected,
        "port_differs": port_differs,
        "path_differs": path_differs,
        "sources": settings["sources"],
        "detail": (
            f"Forge probes {url} but this project's Unreal settings serve {expected}. Point the transport url in "
            ".forge/mcp.json at the configured endpoint, or change the project setting to match. Either way the "
            "editor must be restarted, because these settings are read at startup."
        ),
    }


def project_descriptors(root: Path) -> list[str]:
    return [str(path.resolve()) for path in sorted(root.glob("*.uproject"))]


def editor_process_holding(root: Path, table: dict[str, Any] | None = None) -> dict[str, Any]:
    """Any Unreal editor process with this project's descriptor on its command line.

    MCP answering proves an editor is live. MCP being silent proves nothing: a
    frozen editor stops servicing requests while still holding every file it has
    open, and that is exactly when a commandlet must not be let near the project.
    """
    resolved = table if table is not None else executor.process_table()
    if not resolved["resolved"]:
        return {"determined": False, "holder": None, "detail": str(resolved.get("detail", "process inspection did not answer"))}
    descriptors = project_descriptors(root)
    names = {str(root.resolve()).lower(), *(item.lower() for item in descriptors)}
    stems = {Path(item).stem.lower() for item in descriptors}
    for process in resolved["processes"]:
        if not any(marker in process["name"].lower() for marker in EDITOR_PROCESS_NAMES):
            continue
        command_line = process["command_line"].lower().replace("/", "\\")
        if any(needle.lower().replace("/", "\\") in command_line for needle in names):
            return {
                "determined": True,
                "holder": {"pid": process["pid"], "name": process["name"]},
                "detail": f"{process['name']} (pid {process['pid']}) has this project open",
            }
        if not process["command_line"] and stems:
            return {
                "determined": False,
                "holder": {"pid": process["pid"], "name": process["name"]},
                "detail": (
                    f"{process['name']} (pid {process['pid']}) is running but {resolved['mechanism']} did not expose "
                    "its command line, so whether it holds this project cannot be told apart from whether it holds another"
                ),
            }
    editors = [
        process for process in resolved["processes"]
        if any(marker in process["name"].lower() for marker in EDITOR_PROCESS_NAMES)
    ]
    return {
        "determined": True,
        "holder": None,
        "editors_running": len(editors),
        "detail": (
            f"{resolved['mechanism']} found {len(editors)} Unreal editor process(es), none holding this project"
            if editors
            else f"{resolved['mechanism']} found no Unreal editor process at all"
        ),
    }


def live_editor_holds_project(root: Path) -> dict[str, Any]:
    """Whether an editor owns this project: HELD, FREE, or honestly UNDETERMINED.

    Absence of evidence is not evidence of absence. The editor-closed lane may be
    entered only on a positive finding that nothing holds the project, because a
    commandlet run against a project a live editor has open is the corruption the
    super-lock exists to prevent.
    """
    endpoints = [
        url
        for url in (mcp_endpoint_url(root, provider) for provider in mcp_providers())
        if url
    ]
    evidence: list[dict[str, Any]] = []
    answering = next((url for url in endpoints if probe_mcp_endpoint(url, timeout=1.5)["speaks_mcp"]), None)
    process = editor_process_holding(root)
    if answering:
        evidence.append(
            {
                "signal": "mcp-handshake",
                "conclusive": not process["determined"],
                "detail": f"an editor answered an MCP initialize at {answering}, which proves an editor is live "
                          "but not which project it has open: the endpoint is a machine port, not a project's",
            }
        )
        evidence.append({"signal": "process-inspection", "conclusive": process["determined"], "detail": process["detail"]})
        if process["determined"] and not process["holder"]:
            if process.get("editors_running"):
                return {
                    "ownership": "FREE",
                    "held": False,
                    "endpoint": answering,
                    "evidence": evidence,
                    "detail": f"an editor answered at {answering} and {process['editors_running']} editor "
                              "process(es) are running, none of them holding this project, so the answering "
                              "editor has a different project open and this lane is enterable",
                }
            return {
                "ownership": "UNDETERMINED",
                "held": None,
                "endpoint": answering,
                "evidence": evidence,
                "detail": f"something answered an MCP initialize at {answering} while no Unreal editor process "
                          "exists at all; the two signals contradict each other",
                "human_action": (
                    f"Something is serving MCP at {answering} that is not an Unreal editor this machine can see. "
                    "Find out what: another tool on the port, an editor running as a different user, or an "
                    "engine build process inspection does not recognise. Forge will not enter the editor-closed "
                    "lane while a signal it cannot explain says an editor is live."
                ),
            }
        return {
            "ownership": "HELD",
            "held": True,
            "endpoint": answering,
            "holder": process["holder"],
            "evidence": evidence,
            "detail": process["detail"] if process["holder"] else
                      f"an editor answered at {answering} and process inspection could not say whose project it is",
        }
    evidence.append(
        {
            "signal": "mcp-handshake",
            "conclusive": False,
            "detail": "no editor answered on any declared endpoint, which does not prove none is running: "
                      "a frozen editor stops answering while still holding the project",
        }
    )
    evidence.append({"signal": "process-inspection", "conclusive": process["determined"], "detail": process["detail"]})
    if process["determined"] and process["holder"]:
        return {
            "ownership": "HELD",
            "held": True,
            "endpoint": endpoints[0] if endpoints else None,
            "holder": process["holder"],
            "evidence": evidence,
            "detail": process["detail"],
        }
    if not process["determined"]:
        return {
            "ownership": "UNDETERMINED",
            "held": None,
            "endpoint": endpoints[0] if endpoints else None,
            "evidence": evidence,
            "detail": process["detail"],
            "human_action": (
                "Forge cannot tell whether an editor holds this project, and will not guess. Resolve the process "
                "check first: confirm process inspection works on this machine, then re-run. If it cannot be "
                "repaired, decide by hand whether the editor is closed and say how to proceed — Forge will not "
                "decide this for you, because the cost of being wrong is a commandlet writing into a project the "
                "editor has open."
            ),
        }
    return {
        "ownership": "FREE",
        "held": False,
        "endpoint": endpoints[0] if endpoints else None,
        "evidence": evidence,
        "detail": "no editor answered and no Unreal editor process holds this project, so the editor-closed lane is enterable",
    }


def probe_process_route(root: Path, provider: dict[str, Any]) -> dict[str, Any]:
    """Resolve the command, then require the live editor to be silent.

    Readiness here is the inverse of the MCP handshake: a commandlet must not run
    against a project the live editor holds open.
    """
    command = str(provider.get("command", ""))
    resolved = executable(command, f"{command}.exe") if command else None
    if not resolved:
        return {
            "found": False,
            "status": "UNAVAILABLE_OPTIONAL",
            "reason": f"{command!r} is not on PATH; the engine's editor-closed command could not be resolved",
            "command": command,
            "resolved": None,
            "lane_clear": False,
            "searched": [command],
        }
    editor = live_editor_holds_project(root)
    if editor["ownership"] == "HELD":
        return {
            "found": True,
            "status": "UNAVAILABLE_OPTIONAL",
            "reason": "an editor holds this project, so the editor-closed lane is not enterable",
            "note": f"{editor['detail']}. Close the editor, or route this work to the live typed surface instead.",
            "command": command,
            "resolved": resolved,
            "lane_clear": False,
            "ownership": editor["ownership"],
            "ownership_evidence": editor["evidence"],
            "endpoint": editor["endpoint"],
            "searched": [command],
        }
    if editor["ownership"] == "UNDETERMINED":
        return {
            "found": True,
            "status": "UNAVAILABLE_BLOCKING",
            "reason": "whether an editor holds this project could not be determined, so the editor-closed lane stays shut",
            "note": editor["human_action"],
            "command": command,
            "resolved": resolved,
            "lane_clear": False,
            "ownership": editor["ownership"],
            "ownership_evidence": editor["evidence"],
            "human_action": editor["human_action"],
            "endpoint": editor["endpoint"],
            "searched": [command],
        }
    return {
        "found": True,
        "status": "AVAILABLE_UNVERIFIED",
        "reason": f"{command} resolved, and no editor answered or holds this project",
        "note": "Resolving the command is not a round trip. Only an acceptance suite that runs a commandlet and reads its result file earns more than UNVERIFIED.",
        "command": command,
        "resolved": resolved,
        "lane_clear": True,
        "ownership": editor["ownership"],
        "ownership_evidence": editor["evidence"],
        "endpoint": editor["endpoint"],
        "searched": [command],
    }


def mcp_capability_contracts(root: Path, profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Emit one forge.capability-contract/v2 per capability of every declared route."""
    contracts: list[dict[str, Any]] = []
    contracts.extend(_process_contracts(root, profile))
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
                    "lease": provider.get("lease"),
                    "isolation_mode": provider.get("isolation_mode"),
                    "health": "HEALTHY" if status.startswith("AVAILABLE") else "UNAVAILABLE",
                    "lane": provider.get("lane"),
                    "locality": provider.get("locality", "local"),
                    "executable_surfaces": [namespace] if namespace else [],
                    "permissions": provider.get("permissions", {}),
                    "integrity": {"verified": False, "method": "none", "note": "MCP servers are user-installed; Forge does not vouch for them."},
                    "provenance": {"declared_by": "dependencies/route-registry.json", "detected_by": f"{provider.get('probe')}:{server}", "config_path": probe.get("config_path")},
                    "qualification": {"state": "UNQUALIFIED", "task_classes": []},
                    "cost": {"monetary": 0, "note": "Local server; cost is host context plus latency."},
                    "context_cost": {"measured": False, "note": "Measure on the active host; never copy another runtime's estimate."},
                    "fallbacks": provider.get("fallbacks", []),
                    "probe": f"{provider.get('probe')}:{server}",
                    "acceptance_suites": provider.get("acceptance_suites", []),
                    "invalidation_triggers": provider.get("invalidation_triggers", []),
                    "subagent_visible": probe["subagent_visible"],
                    "tool_surface": provider.get("tool_surface"),
                    "detection_note": probe.get("note") or probe.get("reason"),
                }
            )
    return contracts


def _process_contracts(root: Path, profile: dict[str, Any]) -> list[dict[str, Any]]:
    """The same contract shape for a route the host runs rather than connects to."""
    contracts: list[dict[str, Any]] = []
    for provider in process_providers():
        probe = probe_process_route(root, provider)
        missing = [item for item in provider.get("requires_host_provides", []) if item not in profile.get("provides", [])]
        status = "UNAVAILABLE_OPTIONAL" if missing else probe["status"]
        for capability in provider.get("capabilities", []):
            contracts.append(
                {
                    "capability": capability,
                    "provider": provider.get("id"),
                    "kind": "process",
                    "status": status,
                    "lease": provider.get("lease"),
                    "isolation_mode": provider.get("isolation_mode"),
                    "health": "HEALTHY" if status.startswith("AVAILABLE") else "UNAVAILABLE",
                    "lane": provider.get("lane"),
                    "locality": provider.get("locality", "local"),
                    "executable_surfaces": [probe["resolved"]] if probe.get("resolved") else [],
                    "permissions": provider.get("permissions", {}),
                    "integrity": {"verified": False, "method": "none", "note": "The engine is user-installed; Forge does not vouch for it."},
                    "provenance": {"declared_by": "dependencies/route-registry.json", "detected_by": f"{provider.get('probe')}:{provider.get('command')}", "config_path": probe.get("resolved")},
                    "qualification": {"state": "UNQUALIFIED", "task_classes": []},
                    "cost": {"monetary": 0, "note": "Local process; cost is wall clock plus the lane it holds."},
                    "context_cost": {"measured": False, "note": "Measure on the active host; never copy another runtime's estimate."},
                    "fallbacks": provider.get("fallbacks", []),
                    "probe": f"{provider.get('probe')}:{provider.get('command')}",
                    "acceptance_suites": provider.get("acceptance_suites", []),
                    "invalidation_triggers": provider.get("invalidation_triggers", []),
                    "subagent_visible": "shell-execution" in profile.get("provides", []),
                    "lane_clear": probe.get("lane_clear"),
                    "tool_surface": provider.get("tool_surface"),
                    "detection_note": probe.get("note") or probe.get("reason"),
                }
            )
    return contracts


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
            lane = str(entry.get("lane", ""))
            if not lane.startswith("lane."):
                raise fail(
                    f"Project MCP entry {entry_id!r} names lane {lane!r}. Lane ids carry a 'lane.' prefix so a "
                    "lane and a capability cannot collide in one namespace; a lane spelled any other way is not "
                    "the lane the lease ledger enforces.",
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
                "kind": "mcp",
                "server": server,
                "lease": (catalog.get(str(item["id"])) or {}).get("lease"),
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
                "engine_settings": probe.get("engine_settings"),
                "endpoint_disagreement": probe.get("endpoint_disagreement"),
                "note": probe.get("note") or probe.get("reason"),
            }
        )
    for provider in process_providers():
        probe = probe_process_route(root, provider)
        routes.append(
            {
                "provider": provider["id"],
                "kind": "process",
                "command": provider.get("command"),
                "source": "catalog",
                "enabled": True,
                "scope": "project",
                "capabilities": provider.get("capabilities", []),
                "lane": provider.get("lane"),
                "lease": provider.get("lease"),
                "isolation_mode": provider.get("isolation_mode"),
                "declared_in_project": True,
                "session_visible": probe["status"].startswith("AVAILABLE"),
                "found": probe["found"],
                "resolved": probe.get("resolved"),
                "lane_clear": probe.get("lane_clear"),
                "status": probe["status"],
                "fallbacks": provider.get("fallbacks", []),
                "note": probe.get("note") or probe.get("reason"),
            }
        )
    return {
        "schema": "forge.route-status/v1",
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
