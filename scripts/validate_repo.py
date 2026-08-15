#!/usr/bin/env python3
"""Validate the Forge repository without third-party packages."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "forge-ue-studio"
IGNORED_PARTS = {".git", ".tmp", "__pycache__"}

# Canon must never name a runtime vendor. These are the only places allowed to.
NEUTRALITY_EXEMPT_FILES = {
    PLUGIN / "hosts" / "registry.json",
}

# "OpenAI-compatible" is the ecosystem's name for a wire protocol, not a
# dependency on a vendor. Anything else matching a banned token is a leak.
NEUTRALITY_ALLOWED_SUBSTRINGS = ("openai-compatible",)

# Skill spellings belong to a host, never to canon. The leading boundary keeps
# path segments such as "plugins/forge-ue-studio" and "open-gsd/gsd-core" from
# matching, since only a real invocation is preceded by whitespace or nothing.
HOST_SKILL_INVOCATION = re.compile(r"(?<![\w./\\-])[$/](?:forge|gsd)-[a-z0-9-]+")


def neutrality_banned_tokens(hosts: list) -> list[str]:
    """Derive banned vendor tokens from the host registry itself.

    Keyed off the registry so adding a host automatically extends the guard.
    Hosts with no CLI executables (the `generic` placeholder profile) contribute
    nothing, because their identifiers are common words rather than vendor names.
    """
    tokens: set[str] = set()
    for host in hosts:
        if not host.get("cli", {}).get("executables"):
            continue
        surface = host.get("project_surface", {})
        for value in (
            host.get("id"),
            host.get("display_name"),
            host.get("vendor"),
            host.get("home", {}).get("dir"),
            surface.get("instruction_file"),
            surface.get("agent_dir"),
        ):
            if value:
                tokens.add(str(value).casefold())
    return sorted(tokens, key=len, reverse=True)


def neutrality_violations(text: str, banned: list[str]) -> list[str]:
    haystack = text.casefold()
    for allowed in NEUTRALITY_ALLOWED_SUBSTRINGS:
        haystack = haystack.replace(allowed, "~" * len(allowed))
    found = [token for token in banned if token in haystack]
    found.extend(sorted({match for match in HOST_SKILL_INVOCATION.findall(text)}))
    return found


def repository_files(pattern: str):
    return (path for path in ROOT.rglob(pattern) if not any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts))


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def main() -> int:
    failures: list[str] = []

    json_files = sorted(repository_files("*.json"))
    parsed = {}
    for path in json_files:
        try:
            parsed[path] = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"Invalid JSON {path.relative_to(ROOT)}: {exc}", failures)

    # Every host that declares a plugin manifest directory must actually ship one,
    # so the repo installs cleanly under any supported runtime.
    registry_path = PLUGIN / "hosts" / "registry.json"
    registry = parsed.get(registry_path, {})
    hosts = registry.get("hosts", [])
    if not hosts:
        fail("Host registry declares no hosts", failures)
    host_ids = [host.get("id") for host in hosts]
    if len(host_ids) != len(set(host_ids)) or any(not item for item in host_ids):
        fail("Host IDs must be non-empty and unique", failures)
    if registry.get("default_host") not in host_ids:
        fail("Host registry default_host is not a declared host", failures)
    contract = registry.get("prerequisite_contract", {})
    if not contract.get("required"):
        fail("Host registry must declare a required prerequisite contract", failures)

    prefixes = {}
    for host in hosts:
        host_id = host.get("id")
        for field in ("display_name", "resident_capability", "cli", "skill_invocation", "discovery", "project_surface", "plugin", "gsd", "provides"):
            if not host.get(field):
                fail(f"Host {host_id} missing {field}", failures)
        surface = host.get("project_surface", {})
        if surface.get("agent_format") not in {"markdown-frontmatter", "toml"}:
            fail(f"Host {host_id} declares an unsupported agent format", failures)
        missing = [item for item in contract.get("required", []) if item not in host.get("provides", [])]
        if missing:
            fail(f"Host {host_id} cannot satisfy the Forge prerequisite contract: {', '.join(missing)}", failures)
        prefix = host.get("skill_invocation", {}).get("prefix")
        if prefix in prefixes:
            fail(f"Hosts {prefixes[prefix]} and {host_id} share skill prefix {prefix!r}", failures)
        prefixes[prefix] = host_id

    for host in hosts:
        manifest_dir = host.get("plugin", {}).get("manifest_dir")
        if not manifest_dir or host.get("id") == "generic":
            continue
        manifest_path = PLUGIN / manifest_dir / "plugin.json"
        if not manifest_path.is_file():
            fail(f"Host {host.get('id')} declares {manifest_dir} but no plugin.json exists there", failures)
            continue
        manifest = parsed.get(manifest_path, {})
        if manifest.get("name") != PLUGIN.name:
            fail(f"Plugin folder and manifest name differ in {manifest_dir}", failures)
        if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", str(manifest.get("version", ""))):
            fail(f"Plugin version is not semver in {manifest_dir}", failures)
        for field in ("description", "author"):
            if not manifest.get(field):
                fail(f"Plugin manifest in {manifest_dir} missing {field}", failures)

        marketplace_path = ROOT / host.get("plugin", {}).get("marketplace_manifest", "")
        if not marketplace_path.is_file():
            fail(f"Host {host.get('id')} declares a marketplace manifest that does not exist", failures)
            continue
        marketplace = parsed.get(marketplace_path, {})
        entries = [entry for entry in marketplace.get("plugins", []) if entry.get("name") == PLUGIN.name]
        if len(entries) != 1:
            fail(f"Marketplace {marketplace_path.name} must contain exactly one Forge entry", failures)
        else:
            source = entries[0].get("source")
            path_value = source.get("path") if isinstance(source, dict) else source
            if path_value != "./plugins/forge-ue-studio":
                fail(f"Marketplace source path is incorrect in {marketplace_path.name}", failures)

    catalog_path = PLUGIN / "dependencies" / "catalog.json"
    dependencies = parsed.get(catalog_path, {}).get("dependencies", [])
    ids = [item.get("id") for item in dependencies]
    if len(ids) != len(set(ids)) or any(not item for item in ids):
        fail("Dependency IDs must be non-empty and unique", failures)
    for item in dependencies:
        if not item.get("classification") or not item.get("capabilities"):
            fail(f"Dependency {item.get('id')} is incomplete", failures)

    # Typed tool routes. The registry is the only place a server is declared, so
    # every reference leaving it must resolve: to a dependency, to a lane, to a
    # probe kind, to an acceptance suite, and to a host capability. A row that
    # points at nothing would render an agent that silently cannot work.
    mcp_path = PLUGIN / "dependencies" / "mcp-registry.json"
    mcp_registry = parsed.get(mcp_path, {})
    mcp_providers = mcp_registry.get("providers", [])
    mcp_lanes = set(mcp_registry.get("lanes", {}))
    mcp_probe_kinds = set(mcp_registry.get("probe_kinds", {}))
    dependency_by_id = {item.get("id"): item for item in dependencies}
    acceptance_path = PLUGIN / "assets" / "project-template" / ".forge" / "acceptance" / "registry.json"
    acceptance_ids = {suite.get("id") for suite in parsed.get(acceptance_path, {}).get("suites", [])}
    contract_capabilities = set(contract.get("required", [])) | set(contract.get("optional", []))
    isolation_modes = {"read-only", "git-worktree", "lfs-lock", "project-exclusive"}
    mcp_required = ("id", "server", "kind", "capabilities", "lane", "isolation_mode", "requires_host_provides", "probe", "fallbacks", "permissions", "acceptance_suites", "invalidation_triggers")

    if not mcp_providers:
        fail("MCP registry declares no providers", failures)
    seen_servers: dict[str, str] = {}
    seen_capabilities: dict[str, str] = {}
    for provider in mcp_providers:
        provider_id = provider.get("id")
        missing_fields = [field for field in mcp_required if not provider.get(field)]
        if missing_fields:
            fail(f"MCP provider {provider_id!r} missing {', '.join(missing_fields)}", failures)
            continue
        if provider.get("kind") != "mcp":
            fail(f"MCP provider {provider_id!r} must declare kind 'mcp'", failures)
        dependency = dependency_by_id.get(provider_id)
        if dependency is None:
            fail(f"MCP provider {provider_id!r} is not a declared dependency in catalog.json", failures)
        else:
            # One dependency truth: the route a server degrades to must be the
            # route the catalog already promises for that dependency.
            if dependency.get("fallback") not in provider.get("fallbacks", []):
                fail(f"MCP provider {provider_id!r} fallbacks do not include the catalog fallback {dependency.get('fallback')!r}", failures)
            unknown_caps = [item for item in provider.get("capabilities", []) if item not in dependency.get("capabilities", [])]
            if unknown_caps:
                fail(f"MCP provider {provider_id!r} serves capabilities the catalog does not declare: {', '.join(unknown_caps)}", failures)
        server = provider.get("server", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(server)):
            fail(f"MCP provider {provider_id!r} declares a malformed server id {server!r}", failures)
        if server in seen_servers:
            fail(f"MCP server {server!r} is declared by both {seen_servers[server]!r} and {provider_id!r}", failures)
        seen_servers[str(server)] = str(provider_id)
        for capability in provider.get("capabilities", []):
            if capability in seen_capabilities:
                fail(f"Capability {capability!r} is served by both {seen_capabilities[capability]!r} and {provider_id!r}; routing would be ambiguous", failures)
            seen_capabilities[str(capability)] = str(provider_id)
        if provider.get("lane") not in mcp_lanes:
            fail(f"MCP provider {provider_id!r} names undeclared lane {provider.get('lane')!r}", failures)
        if provider.get("isolation_mode") not in isolation_modes:
            fail(f"MCP provider {provider_id!r} declares an unsupported isolation mode {provider.get('isolation_mode')!r}", failures)
        if provider.get("probe") not in mcp_probe_kinds:
            fail(f"MCP provider {provider_id!r} names undeclared probe kind {provider.get('probe')!r}", failures)
        for suite in provider.get("acceptance_suites", []):
            if suite not in acceptance_ids:
                fail(f"MCP provider {provider_id!r} names unknown acceptance suite {suite!r}", failures)
        for capability in provider.get("requires_host_provides", []):
            if capability not in contract_capabilities:
                fail(f"MCP provider {provider_id!r} requires host capability {capability!r}, which the prerequisite contract does not declare", failures)

    # A new game project starts with a declaration file it can amend, not with
    # servers it never chose. The template must parse and start empty.
    project_mcp_path = PLUGIN / "assets" / "project-template" / ".forge" / "mcp.json"
    project_mcp = parsed.get(project_mcp_path, {})
    if project_mcp.get("schema") != "forge.project-mcp/v1":
        fail("Project MCP template must declare schema forge.project-mcp/v1", failures)
    if not isinstance(project_mcp.get("servers"), list):
        fail("Project MCP template must declare a servers array", failures)
    elif project_mcp["servers"]:
        fail("Project MCP template must ship empty; a project declares its own routes", failures)

    # A host either speaks MCP and knows how to spell a namespace, or it does
    # neither. Half a declaration renders agents with tools that cannot bind.
    for host in hosts:
        host_id = host.get("id")
        mcp = host.get("mcp", {})
        speaks = "mcp-client" in host.get("provides", [])
        if speaks and not mcp:
            fail(f"Host {host_id} provides mcp-client but declares no mcp block", failures)
        if mcp and not speaks:
            fail(f"Host {host_id} declares an mcp block without providing mcp-client", failures)
        if not mcp:
            continue
        template = mcp.get("tool_namespace_template", "")
        if "{server}" not in str(template):
            fail(f"Host {host_id} mcp.tool_namespace_template must interpolate {{server}}", failures)
        if not mcp.get("config_paths"):
            fail(f"Host {host_id} declares no MCP config paths, so no server can ever be probed", failures)
        # Where a project's own routes land is a deliberate decision per host,
        # including "nowhere". An absent key is a forgotten one.
        if "project_surface" not in mcp:
            fail(f"Host {host_id} declares no mcp.project_surface; state the path or state null", failures)
        project_surface = mcp.get("project_surface")
        if project_surface is None and not mcp.get("project_surface_note"):
            fail(f"Host {host_id} renders no project MCP surface but records no reason", failures)
        # Publishing to user scope writes outside every project on the machine,
        # so a host must say where that lands and whether Forge may write it.
        if "user_surface" not in mcp:
            fail(f"Host {host_id} declares no mcp.user_surface; state the path or state null", failures)
        user_surface = mcp.get("user_surface")
        if isinstance(user_surface, dict):
            for field in ("path", "format", "server_key"):
                if not user_surface.get(field):
                    fail(f"Host {host_id} mcp.user_surface missing {field}", failures)
            if "writable" not in user_surface:
                fail(f"Host {host_id} mcp.user_surface must state writable", failures)
            if user_surface.get("writable") and user_surface.get("format") != "json":
                fail(f"Host {host_id} marks a non-JSON user surface writable; Forge only rewrites JSON it can merge safely", failures)
            if not user_surface.get("writable") and not user_surface.get("note"):
                fail(f"Host {host_id} declares an unwritable user surface with no reason", failures)
        if isinstance(project_surface, dict):
            for field in ("path", "format", "server_key"):
                if not project_surface.get(field):
                    fail(f"Host {host_id} mcp.project_surface missing {field}", failures)
            if project_surface.get("format") not in {"json", "toml-table"}:
                fail(f"Host {host_id} declares an unsupported project MCP format {project_surface.get('format')!r}", failures)
        for entry in mcp.get("config_paths", []):
            for field in ("path", "format", "server_key", "scope"):
                if not entry.get(field):
                    fail(f"Host {host_id} MCP config path missing {field}", failures)
            if entry.get("format") not in {"json", "toml-table"}:
                fail(f"Host {host_id} declares an unsupported MCP config format {entry.get('format')!r}", failures)
            if "subagent_visible" not in entry:
                fail(f"Host {host_id} MCP config path {entry.get('path')!r} must state subagent_visible", failures)

    # Every dependency states whether anything actually dispatches to it. An
    # aspirational entry is fine; an entry that is silently unreachable is not,
    # because nothing distinguishes it from one that was meant to be wired.
    routing_states = set(parsed.get(catalog_path, {}).get("routing_states", {}))
    if not routing_states:
        fail("Catalog must declare its routing_states vocabulary", failures)
    served_capabilities = {c for p in mcp_providers for c in p.get("capabilities", [])}
    for item in dependencies:
        state = item.get("routing")
        if state not in routing_states:
            fail(f"Dependency {item.get('id')!r} declares unknown routing state {state!r}", failures)
            continue
        caps = set(item.get("capabilities", []))
        if state == "routed" and not (caps & served_capabilities):
            fail(f"Dependency {item.get('id')!r} claims routed but no provider serves any of its capabilities", failures)
        if state == "declared" and not item.get("routing_note"):
            fail(f"Dependency {item.get('id')!r} is unrouted and must record how it is actually exercised", failures)
        if state == "declared" and (caps & served_capabilities):
            fail(f"Dependency {item.get('id')!r} is marked declared but a provider serves its capabilities", failures)

    # Activation can only turn on a capability some dependency provides.
    activation_path = PLUGIN / "assets" / "project-template" / ".forge" / "context" / "activation-policy.json"
    activation = parsed.get(activation_path, {})
    declared_capabilities = {c for item in dependencies for c in item.get("capabilities", [])}
    activation_capabilities = set(activation.get("always_on", []))
    for entries in activation.get("profiles", {}).values():
        activation_capabilities |= set(entries)
    for capability in sorted(activation_capabilities - declared_capabilities):
        fail(f"Activation policy names capability {capability!r}, which no dependency declares", failures)

    # Lanes and capabilities are separate namespaces. Keeping the prefix on lane
    # ids is what stops one being read as the other.
    for lane in mcp_lanes:
        if not str(lane).startswith("lane."):
            fail(f"Lane id {lane!r} must carry the lane. prefix so it cannot collide with a capability", failures)
    for lane in mcp_lanes:
        if lane in declared_capabilities:
            fail(f"Lane {lane!r} collides with a declared capability", failures)

    schemas = sorted((PLUGIN / "schemas").glob("*.schema.json"))
    for schema_path in schemas:
        schema = parsed.get(schema_path, {})
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            fail(f"Schema declaration missing or unsupported: {schema_path.relative_to(ROOT)}", failures)
        if not schema.get("$id") or schema.get("type") != "object" or not schema.get("required"):
            fail(f"Schema contract incomplete: {schema_path.relative_to(ROOT)}", failures)

    route_policy_path = PLUGIN / "dependencies" / "route-policy.json"
    route_policy = parsed.get(route_policy_path, {})
    resident = route_policy.get("resident_default", {})
    if resident.get("provider") != "resident":
        fail("Route policy must declare a host-neutral 'resident' default provider", failures)
    if not resident.get("provider_is_host_assigned"):
        fail("Route policy must mark the resident provider as host-assigned", failures)
    offload = route_policy.get("offload_policy", {})
    if not offload.get("require_task_and_complexity_eval") or not offload.get("packet"):
        fail("Route policy must constrain local offload by evaluation and bounded packet", failures)
    if not offload.get("keep_on_resident_by_default"):
        fail("Route policy must list task classes kept on the resident host", failures)
    if "user_scope_config_write" not in route_policy.get("never_implicit", []):
        fail("Route policy must forbid an implicit machine-wide config write", failures)
    swap = route_policy.get("host_swap", {})
    if not swap.get("allowed_at_any_stage") or not swap.get("preserves"):
        fail("Route policy must permit a host swap at any stage and declare what it preserves", failures)

    skills = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
    if not skills:
        fail("No skills found", failures)
    for skill_path in skills:
        text = skill_path.read_text(encoding="utf-8")
        match = re.match(r"^---\nname: ([a-z0-9-]+)\ndescription: (.+?)\n---\n", text, re.DOTALL)
        if not match:
            fail(f"Invalid skill frontmatter: {skill_path.relative_to(ROOT)}", failures)
        elif match.group(1) != skill_path.parent.name:
            fail(f"Skill folder/name mismatch: {skill_path.relative_to(ROOT)}", failures)
        agent_metadata = skill_path.parent / "agents" / "openai.yaml"
        if not agent_metadata.is_file():
            fail(f"Skill missing agents/openai.yaml: {skill_path.relative_to(ROOT)}", failures)
        else:
            metadata_text = agent_metadata.read_text(encoding="utf-8")
            if f"${skill_path.parent.name}" not in metadata_text:
                fail(f"Skill default prompt must mention its skill name: {agent_metadata.relative_to(ROOT)}", failures)

    required_template = [
        PLUGIN / "assets" / "project-template" / ".forge" / "config.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "mcp.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "capabilities" / "registry.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "capabilities" / "consent-ledger.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "capabilities" / "qualifications.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "context" / "activation-policy.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "state" / "leases.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "state" / "lifecycle.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "state" / "packet-registry.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "reviews" / "registry.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "research" / "index.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "learnings" / "registry.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "directives.md",
        PLUGIN / "assets" / "project-template" / ".forge" / "agents" / "studio-director.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "templates" / "project-instructions.md",
    ]
    for path in required_template:
        if not path.is_file():
            fail(f"Missing project template file: {path.relative_to(ROOT)}", failures)

    # Every schema that ships is validatable through the CLI, and the installer's
    # ValidateSet must match. A PowerShell ValidateSet has to be a literal, so it
    # cannot derive itself the way forge.py does — this is what keeps it honest.
    schema_kinds = {path.name[: -len(".schema.json")] for path in (PLUGIN / "schemas").glob("*.schema.json")}
    installer = (ROOT / "install.ps1").read_text(encoding="utf-8-sig")
    contract_block = re.search(r"\[ValidateSet\(([^)]*)\)\]\s*\r?\n\s*\[string\]\$ContractKind", installer)
    if not contract_block:
        fail("install.ps1 declares no ContractKind ValidateSet", failures)
    else:
        declared_kinds = set(re.findall(r"'([^']+)'", contract_block.group(1)))
        for missing in sorted(schema_kinds - declared_kinds):
            fail(f"install.ps1 -ContractKind cannot validate shipped schema {missing!r}", failures)
        for extra in sorted(declared_kinds - schema_kinds):
            fail(f"install.ps1 -ContractKind offers {extra!r}, which ships no schema", failures)

    # Every CLI verb is reachable from the installer, which is the entry point the
    # documentation points Windows users at.
    forge_source = (PLUGIN / "scripts" / "forge.py").read_text(encoding="utf-8")
    # Top-level verbs only: `sub` is the root subparser, while `host_sub` and
    # `mcp_sub` hold subcommands reached through their parent mode.
    cli_verbs = set(re.findall(r'(?<![\w])sub\.add_parser\(\s*"([a-z][a-z-]*)"', forge_source))
    grouped = re.search(r'for name in \(([^)]*)\):', forge_source)
    if grouped:
        cli_verbs |= set(re.findall(r'"([a-z][a-z-]*)"', grouped.group(1)))
    if not cli_verbs:
        fail("No CLI verbs found in forge.py; the installer-mode check would assert over nothing", failures)
    mode_block = re.search(r"\[ValidateSet\(([^)]*)\)\]\s*\r?\n\s*\[string\]\$Mode", installer)
    modes = {m.lower() for m in re.findall(r"'([^']+)'", mode_block.group(1))} if mode_block else set()
    verb_map = dict(re.findall(r"'([A-Za-z]+)'\s*=\s*'([a-z][a-z-]*)'", installer))
    mapped = {verb for verb in verb_map.values()}
    for verb in sorted(cli_verbs):
        if verb.replace("-", "") not in modes and verb not in mapped:
            fail(f"forge.py verb {verb!r} has no install.ps1 -Mode", failures)

    # A studio role nothing dispatches to is a role that never runs.
    project_template = PLUGIN / "assets" / "project-template"
    agent_names = {path.stem for path in (project_template / ".forge" / "agents").glob("*.json")}
    skill_corpus = "\n".join(path.read_text(encoding="utf-8-sig") for path in (PLUGIN / "skills").glob("*/SKILL.md"))
    for name in sorted(agent_names):
        if name not in skill_corpus:
            fail(f"Agent {name!r} is defined but no skill names it as a dispatch target", failures)

    # The failure vocabulary is one list. A call site that invents a reason
    # inline puts a code on the wire that no test can assert against and no
    # caller can branch on, which is the state typed reasons exist to end.
    reason_block = re.search(r"ERROR_REASON = MappingProxyType\(\s*\{(.*?)\}\s*\)", forge_source, re.DOTALL)
    if not reason_block:
        fail("forge.py declares no ERROR_REASON vocabulary", failures)
    else:
        declared_reasons = dict(re.findall(r'"([A-Z0-9_]+)":\s*"([a-z0-9_]+)"', reason_block.group(1)))
        if not declared_reasons:
            fail("ERROR_REASON is declared but empty", failures)
        for key, value in sorted(declared_reasons.items()):
            if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
                fail(f"Error reason {key} has non-snake_case wire value {value!r}", failures)
        # Every reason passed to fail()/ForgeExit must come from the enum.
        for literal in sorted(set(re.findall(r"reason=\"([^\"]+)\"", forge_source))):
            fail(f"forge.py passes an inline reason string {literal!r}; use ERROR_REASON", failures)
        used = {key for key in declared_reasons if f'ERROR_REASON["{key}"]' in forge_source}
        for unused in sorted(set(declared_reasons) - used):
            fail(f"Error reason {unused} is declared but never raised", failures)

    # `ok` is a verdict, not decoration. The declaration and the assertion that
    # enforces it must both exist, or a missing verdict quietly becomes success.
    verdict_block = re.search(r"VERDICT_COMMANDS = frozenset\(\s*\{(.*?)\}\s*\)", forge_source, re.DOTALL)
    if not verdict_block:
        fail("forge.py declares no VERDICT_COMMANDS set", failures)
    else:
        verdict_commands = re.findall(r'"([a-z][a-z -]*)"', verdict_block.group(1))
        if not verdict_commands:
            fail("VERDICT_COMMANDS is declared but empty", failures)
        # Checked against the parser's own declarations, not against the whole
        # source: a bare substring search is satisfied by the VERDICT_COMMANDS
        # entry itself, so the gate would confirm every name including invented
        # ones.
        declared_commands = set(re.findall(r'(?<![\w])sub\.add_parser\(\s*"([a-z][a-z-]*)"', forge_source))
        grouped_commands = re.search(r'for name in \(([^)]*)\):', forge_source)
        if grouped_commands:
            declared_commands |= set(re.findall(r'"([a-z][a-z-]*)"', grouped_commands.group(1)))
        sub_commands = set(re.findall(r'_sub\.add_parser\(\s*"([a-z][a-z-]*)"', forge_source))
        for command in verdict_commands:
            parts = command.split()
            if parts[0] not in declared_commands:
                fail(f"VERDICT_COMMANDS names {command!r}, which is not a declared CLI command", failures)
            elif len(parts) > 1 and parts[1] not in sub_commands:
                fail(f"VERDICT_COMMANDS names {command!r}, whose subcommand is not declared", failures)
        for needed in ("command_path in VERDICT_COMMANDS", "command_path not in VERDICT_COMMANDS"):
            if needed not in forge_source:
                fail(f"forge.py does not assert the result contract ({needed})", failures)
        if 'result.get("ok", True)' in forge_source:
            fail("forge.py still defaults a missing verdict to success", failures)

    # A document nothing links to is a document nobody finds.
    doc_sources = {
        path: path.read_text(encoding="utf-8-sig", errors="replace")
        for path in repository_files("*")
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".py", ".ps1"}
    }
    for path in sorted(ROOT.glob("docs/**/*.md")):
        # Counted across every other file, so a document that happens to name
        # itself is not thereby considered reachable.
        if not any(path.name in text for source, text in doc_sources.items() if source != path):
            fail(f"Document {path.relative_to(ROOT)} is not linked from anywhere", failures)

    # A state file nothing reads is state nothing resumes from.
    state_readers = skill_corpus + forge_source
    for path in sorted((project_template / ".forge" / "state").glob("*.json")):
        if path.name not in state_readers:
            fail(f"Project state file {path.name!r} has no reader in any skill or in forge.py", failures)

    # The project template must stay host-neutral: no host-specific surface may be
    # shipped verbatim, because those are rendered per host at install time.
    template_root = PLUGIN / "assets" / "project-template"
    host_dirs = {host.get("project_surface", {}).get("agent_dir", "").split("/")[0] for host in hosts}
    host_files = {host.get("project_surface", {}).get("instruction_file") for host in hosts}
    for path in template_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(template_root)
        if relative.parts[0] in host_dirs and relative.parts[0]:
            fail(f"Project template ships a host-specific directory: {relative}", failures)
        if str(relative) in host_files:
            fail(f"Project template ships a host-specific instruction file: {relative}", failures)

    agent_defs = sorted((template_root / ".forge" / "agents").glob("*.json"))
    if len(agent_defs) < 9:
        fail(f"Expected at least 9 neutral agent definitions, found {len(agent_defs)}", failures)
    for path in agent_defs:
        definition = parsed.get(path, {})
        if definition.get("name") != path.stem:
            fail(f"Agent definition name/file mismatch: {path.relative_to(ROOT)}", failures)
        if not definition.get("description") or not definition.get("instructions"):
            fail(f"Agent definition incomplete: {path.relative_to(ROOT)}", failures)
        declared_caps = definition.get("mcp_capabilities", [])
        if declared_caps:
            # An agent that names a capability no provider serves would render
            # with a tool it can never bind, and its fallback prose would never
            # be reached because nothing reports the gap.
            if definition.get("schema") != "forge.agent-definition/v2":
                fail(f"Agent {path.stem!r} declares mcp_capabilities but not schema v2", failures)
            if not definition.get("tools"):
                fail(f"Agent {path.stem!r} declares mcp_capabilities without a built-in tool surface", failures)
            for capability in declared_caps:
                if capability not in seen_capabilities:
                    fail(f"Agent {path.stem!r} declares capability {capability!r}, which no MCP provider serves", failures)
            instructions = str(definition.get("instructions", ""))
            if "fallback" not in instructions.casefold():
                fail(f"Agent {path.stem!r} routes typed tools but names no fallback route", failures)

    # Verb registry: Forge owns the whole user-facing vocabulary, so every verb it
    # promises must exist as a skill, and every GSD command Forge may encounter
    # must map to one. A gap here leaks a gsd- name to the user.
    verb_registry_path = PLUGIN / "verbs" / "registry.json"
    verb_registry = parsed.get(verb_registry_path, {})
    verbs = verb_registry.get("verbs", [])
    if not verbs:
        fail("Verb registry declares no verbs", failures)
    if verb_registry.get("policy", {}).get("unmapped_action") != "fail":
        fail("Verb registry must declare unmapped_action: fail", failures)
    modes = set(verb_registry.get("delegation_modes", {}))
    skill_names = {path.parent.name for path in (PLUGIN / "skills").glob("*/SKILL.md")}
    seen_gsd = set()
    dispositions = set(verb_registry.get("policy", {}).get("dispositions", {}))
    for entry in verbs:
        forge_verb, gsd_verb = entry.get("forge"), entry.get("gsd")
        disposition = entry.get("disposition")
        if not gsd_verb:
            fail(f"Verb entry has no GSD command: {entry}", failures)
            continue
        if disposition not in dispositions:
            fail(f"Verb entry {gsd_verb!r} declares unknown disposition {disposition!r}", failures)
        if gsd_verb in seen_gsd:
            fail(f"GSD command {gsd_verb!r} is mapped more than once", failures)
        seen_gsd.add(gsd_verb)

        if disposition == "drop":
            # A deliberate exclusion carries no Forge verb and must say why.
            if forge_verb is not None:
                fail(f"Dropped GSD command {gsd_verb!r} must not name a Forge verb", failures)
            if not entry.get("reason"):
                fail(f"Dropped GSD command {gsd_verb!r} must record a reason", failures)
            continue

        if not forge_verb:
            fail(f"Fronted GSD command {gsd_verb!r} names no Forge verb", failures)
            continue
        if forge_verb not in skill_names:
            fail(f"Verb registry maps to {forge_verb!r} but no such skill exists", failures)
        if entry.get("delegation") not in modes:
            fail(f"Verb {forge_verb!r} declares an unknown delegation mode {entry.get('delegation')!r}", failures)
        if not entry.get("gsd_workflow") or not entry.get("adaptation"):
            fail(f"Verb {forge_verb!r} missing gsd_workflow or adaptation", failures)

    # Drift check: every gsd_workflow the registry names must exist in an
    # installed GSD. Skipped when GSD is absent (CI), because the reference is a
    # runtime dependency, not a repository one.
    workflow_dirs = [
        Path(str(host.get("gsd", {}).get("runtime_root", ""))).expanduser() / "workflows"
        for host in hosts
        if host.get("gsd", {}).get("runtime_root")
    ]
    workflow_root = next((path for path in workflow_dirs if path.is_dir()), None)
    if workflow_root is None:
        print("SKIP: GSD is not installed; gsd_workflow drift check not run")
    else:
        available = {path.name for path in workflow_root.iterdir()}
        for entry in verbs:
            if entry.get("disposition") != "front":
                continue
            workflow = entry.get("gsd_workflow")
            if workflow and workflow not in available:
                fail(
                    f"Verb {entry.get('forge')!r} references GSD workflow {workflow!r}, "
                    f"which is not present in {workflow_root}",
                    failures,
                )

    # Canon neutrality: no vendor name, host path, host instruction file, or host
    # skill prefix may appear anywhere in the shipped canon. Banned tokens come
    # from the registry, so this guard extends itself when a host is added.
    banned = neutrality_banned_tokens(hosts)
    canon_files = [
        *(p for p in template_root.rglob("*") if p.is_file()),
        *sorted((PLUGIN / "dependencies").glob("*.json")),
        *sorted((PLUGIN / "schemas").glob("*.json")),
        *sorted((PLUGIN / "verbs").glob("*.json")),
    ]
    for path in canon_files:
        if path in NEUTRALITY_EXEMPT_FILES:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for token in neutrality_violations(text, banned):
            fail(f"Canon leaks host-specific token {token!r}: {path.relative_to(ROOT)}", failures)

    for path in repository_files("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".py", ".toml", ".yml", ".yaml", ".ps1"}:
            placeholder = "[" + "TODO:"
            if placeholder in path.read_text(encoding="utf-8-sig", errors="replace"):
                fail(f"Unresolved placeholder in {path.relative_to(ROOT)}", failures)

    if failures:
        for message in failures:
            print(f"ERROR: {message}")
        return 1
    print(f"OK: {len(json_files)} JSON files, {len(schemas)} schemas, {len(skills)} skills, {len(dependencies)} dependency declarations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
