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
        for host_prefix in ("$forge-", "/forge-", "$gsd-", "/gsd-"):
            if host_prefix in str(definition.get("instructions", "")):
                fail(f"Agent definition hardcodes a host skill prefix: {path.relative_to(ROOT)}", failures)

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
