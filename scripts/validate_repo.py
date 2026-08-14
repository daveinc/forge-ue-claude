#!/usr/bin/env python3
"""Validate the Forge repository without third-party packages."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "forge-ue-studio"


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def main() -> int:
    failures: list[str] = []

    json_files = sorted(ROOT.rglob("*.json"))
    parsed = {}
    for path in json_files:
        try:
            parsed[path] = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"Invalid JSON {path.relative_to(ROOT)}: {exc}", failures)

    manifest_path = PLUGIN / ".codex-plugin" / "plugin.json"
    manifest = parsed.get(manifest_path, {})
    if manifest.get("name") != PLUGIN.name:
        fail("Plugin folder and manifest name differ", failures)
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", str(manifest.get("version", ""))):
        fail("Plugin version is not semver", failures)
    for field in ("description", "author", "skills", "interface"):
        if not manifest.get(field):
            fail(f"Plugin manifest missing {field}", failures)

    marketplace_path = ROOT / ".agents" / "plugins" / "marketplace.json"
    marketplace = parsed.get(marketplace_path, {})
    entries = [entry for entry in marketplace.get("plugins", []) if entry.get("name") == PLUGIN.name]
    if len(entries) != 1:
        fail("Marketplace must contain exactly one Forge entry", failures)
    elif entries[0].get("source", {}).get("path") != "./plugins/forge-ue-studio":
        fail("Marketplace source path is incorrect", failures)

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
    if route_policy.get("resident_default", {}).get("provider") != "codex":
        fail("Route policy must declare Codex as resident default", failures)
    offload = route_policy.get("offload_policy", {})
    if not offload.get("require_task_and_complexity_eval") or not offload.get("packet"):
        fail("Route policy must constrain local offload by evaluation and bounded packet", failures)

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
        PLUGIN / "assets" / "project-template" / ".forge" / "reviews" / "registry.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "research" / "index.json",
        PLUGIN / "assets" / "project-template" / ".forge" / "learnings" / "registry.json",
        PLUGIN / "assets" / "project-template" / ".codex" / "agents" / "studio-director.toml",
    ]
    for path in required_template:
        if not path.is_file():
            fail(f"Missing project template file: {path.relative_to(ROOT)}", failures)

    for path in ROOT.rglob("*"):
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
