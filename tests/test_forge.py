from __future__ import annotations

import ast
import builtins
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import symtable
import sys
import tempfile
import threading
import unittest
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "plugins" / "forge-ue-studio" / "scripts"
FORGE_PATH = SCRIPTS_DIR / "forge.py"
EXECUTOR_PATH = SCRIPTS_DIR / "forge_executor.py"
CORE_PATH = SCRIPTS_DIR / "forge_core.py"
MODULE_PATHS = sorted(SCRIPTS_DIR.glob("*.py"))
REASON_OWNERS = (CORE_PATH, EXECUTOR_PATH)
TEMP_ROOT = Path(tempfile.gettempdir()) / "forge-ue-studio-tests"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)
SPEC = importlib.util.spec_from_file_location("forge_cli", FORGE_PATH)
assert SPEC and SPEC.loader
forge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(forge)

VALIDATE_PATH = ROOT / "scripts" / "validate_repo.py"
VALIDATE_SPEC = importlib.util.spec_from_file_location("validate_repo", VALIDATE_PATH)
assert VALIDATE_SPEC and VALIDATE_SPEC.loader
validate_repo = importlib.util.module_from_spec(VALIDATE_SPEC)
VALIDATE_SPEC.loader.exec_module(validate_repo)

HOSTS = json.loads(
    (ROOT / "plugins" / "forge-ue-studio" / "hosts" / "registry.json").read_text(encoding="utf-8")
)["hosts"]


@contextmanager
def workspace_tempdir():
    path = TEMP_ROOT / uuid.uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        removed = path.with_name(path.name + "_removed")
        if path.exists():
            path.rename(removed)


class ForgeInstallerTests(unittest.TestCase):
    def setUp(self):
        self.original_command_probe = forge.command_probe
        forge.command_probe = lambda command, timeout=8: {
            "ok": False,
            "exit_code": 1,
            "output": "",
            "error": f"probe isolated in unit test: {command[0]}",
        }

    def tearDown(self):
        forge.command_probe = self.original_command_probe

    def make_project(self, root: Path) -> Path:
        project = root / "ExampleGame"
        project.mkdir()
        data = {
            "FileVersion": 3,
            "EngineAssociation": "5.8",
            "Plugins": [
                {"Name": "PythonScriptPlugin", "Enabled": True},
                {"Name": "EditorScriptingUtilities", "Enabled": True},
                {"Name": "ControlRig", "Enabled": True},
                {"Name": "VibeUE", "Enabled": True},
                {"Name": "UnrealMCP", "Enabled": True},
            ],
        }
        (project / "ExampleGame.uproject").write_text(json.dumps(data), encoding="utf-8")
        return project

    def canonical_jobs(self, project: Path) -> list[dict[str, str]]:
        registry = json.loads(
            (project / ".forge" / "state" / "packet-registry.json").read_text(encoding="utf-8")
        )
        return [
            {"work_order": packet["id"], "result": "NOT_APPLICABLE"}
            for packet in registry.get("packets", [])
            if str(packet.get("id", "")).startswith("FI-")
        ]

    def complete_bootstrap(self, project: Path) -> None:
        report = {
            "schema": "forge.bootstrap-report/v1",
            "verdict": "PASS",
            "jobs": self.canonical_jobs(project),
            "delegation": {"mode": "test-fixture"},
            "verified": [],
            "assumed": [],
            "unavailable": [],
            "blocking": [],
            "human_actions": [],
            "evidence": [],
            "next_action": "forge-next",
        }
        (project / ".forge" / "state" / "bootstrap-report.json").write_text(json.dumps(report), encoding="utf-8")

    def test_survey_separates_detection_from_verification(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            result = forge.survey(str(project))
            self.assertEqual(result["schema"], "forge.environment-snapshot/v1")
            self.assertEqual(result["providers"]["resident_default"], "resident")
            self.assertIn("gsd_detected", result["providers"])
            self.assertIn("gsd_inventory", result["providers"])
            self.assertIn("runtime_script", result["providers"]["gsd_inventory"])
            self.assertIn("skill_roots", result["providers"]["gsd_inventory"])
            self.assertIn("local_worker_candidates", result["providers"])
            self.assertTrue(result["unreal"]["vibeue_declared"])
            statuses = {item["capability"]: item["status"] for item in result["capabilities"]}
            self.assertEqual(statuses["ue.live.python"], "AVAILABLE_UNVERIFIED")
            self.assertEqual(statuses["dcc.unreal.animation"], "AVAILABLE_UNVERIFIED")
            self.assertEqual(statuses["worker.resident"], "AVAILABLE_UNVERIFIED")
            self.assertIn(statuses["workflow.gsd"], {"AVAILABLE_UNVERIFIED", "UNAVAILABLE_BLOCKING"})
            gsd = next(item for item in result["capabilities"] if item["capability"] == "workflow.gsd")
            self.assertEqual(gsd["qualification"]["state"], "UNQUALIFIED")

    def test_survey_reports_every_known_host_without_qualifying_one(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            runtime = forge.survey(str(project))["runtime"]
            self.assertEqual(runtime["active_host"], "claude")
            self.assertTrue(runtime["swappable"])
            self.assertTrue(runtime["prerequisites"]["satisfied"])
            detected = {item["id"]: item for item in runtime["detected_hosts"]}
            self.assertIn("codex", detected)
            self.assertIn("claude", detected)
            self.assertTrue(detected["claude"]["active"])
            self.assertFalse(detected["codex"]["active"])
            self.assertTrue(all("qualification" not in item for item in runtime["detected_hosts"]))

    def test_route_policy_keeps_resident_host_neutral_and_local_workers_optional(self):
        policy_path = ROOT / "plugins" / "forge-ue-studio" / "dependencies" / "route-policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertEqual(policy["resident_default"]["provider"], "resident")
        self.assertTrue(policy["resident_default"]["provider_is_host_assigned"])
        self.assertTrue(policy["resident_default"]["fallback_for_optional_workers"])
        self.assertIn("context-heavy-extraction", policy["offload_policy"]["consider_for"])
        self.assertIn("final-synthesis", policy["offload_policy"]["keep_on_resident_by_default"])
        self.assertTrue(policy["offload_policy"]["require_task_and_complexity_eval"])
        self.assertTrue(policy["host_swap"]["allowed_at_any_stage"])
        self.assertIn(".planning", policy["host_swap"]["preserves"])

    def test_dry_run_does_not_write(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            result = forge.install_overlay(str(project), apply=False)
            self.assertEqual(result["mode"], "dry-run")
            self.assertFalse((project / ".forge").exists())
            self.assertTrue(any(item["action"] == "create" for item in result["actions"]))

    def test_pre_project_overlay_installs_before_uproject_exists(self):
        with workspace_tempdir() as temp:
            project = temp / "PreProject"
            project.mkdir()
            result = forge.install_overlay(str(project), apply=True)
            self.assertEqual(result["project_stage"], "pre-project")
            self.assertIsNone(result["uproject"])
            self.assertTrue((project / ".forge" / "state" / "lifecycle.json").is_file())
            self.assertTrue((project / ".forge" / "state" / "packet-registry.json").is_file())
            self.assertTrue((project / ".forge" / "agents" / "studio-director.json").is_file())
            self.assertTrue((project / ".claude" / "agents" / "studio-director.md").is_file())
            self.assertTrue((project / "CLAUDE.md").is_file())
            self.assertFalse((project / "AGENTS.md").exists())
            self.assertTrue(forge.verify_overlay(str(project))["ok"])

    def test_gsd_install_is_preview_first_and_version_pinned(self):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            self.skipTest("PowerShell is unavailable")
        result = subprocess.run(
            [shell, "-NoProfile", "-File", str(ROOT / "install.ps1"), "-Mode", "GSD"],
            check=True,
            capture_output=True,
            text=True,
        )
        preview = json.loads(result.stdout)
        self.assertEqual(preview["mode"], "dry-run")
        self.assertEqual(preview["package"], "@opengsd/gsd-core@1.10.0")
        self.assertEqual(preview["scope"], "global-claude")
        self.assertIn("--claude", preview["command"])
        self.assertFalse(preview["changed"])

    def test_gsd_install_preview_follows_the_selected_host(self):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            self.skipTest("PowerShell is unavailable")
        result = subprocess.run(
            [shell, "-NoProfile", "-File", str(ROOT / "install.ps1"), "-Mode", "GSD", "-RuntimeHost", "codex"],
            check=True,
            capture_output=True,
            text=True,
        )
        preview = json.loads(result.stdout)
        self.assertEqual(preview["scope"], "global-codex")
        self.assertIn("--codex", preview["command"])
        self.assertFalse(preview["changed"])

    def test_apply_is_idempotent(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            first = forge.install_overlay(str(project), apply=True)
            second = forge.install_overlay(str(project), apply=True)
            self.assertTrue(any(item["action"] == "create" for item in first["actions"]))
            self.assertTrue(all(item["action"] not in {"create", "propose", "regenerate", "update"} for item in second["actions"]))
            self.assertTrue(forge.verify_overlay(str(project))["ok"])

    def test_local_variant_gets_non_destructive_proposal(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            config = project / ".forge" / "config.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"local": true}\n', encoding="utf-8")
            result = forge.install_overlay(str(project), apply=True)
            proposed = [item for item in result["actions"] if item["action"] == "propose"]
            self.assertEqual(len(proposed), 1)
            self.assertEqual(config.read_text(encoding="utf-8"), '{"local": true}\n')
            self.assertTrue(Path(proposed[0]["target"]).is_file())

    def test_install_profiles_detected_capabilities_without_qualifying_optional_workers(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            forge.install_overlay(str(project), apply=True)
            detected = json.loads((project / ".forge" / "capabilities" / "detected.json").read_text(encoding="utf-8"))
            self.assertEqual(detected["schema"], "forge.capability-registry/v2")
            optional = [provider for provider in detected["providers"] if provider["id"] != "python" and provider["id"] != "git"]
            self.assertTrue(optional)
            self.assertTrue(all(provider["qualification"]["state"] == "UNQUALIFIED" for provider in optional))

    def test_route_selects_only_exact_positive_qualified_optional_worker(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            forge.install_overlay(str(project), apply=True)
            detected_path = project / ".forge" / "capabilities" / "detected.json"
            detected = json.loads(detected_path.read_text(encoding="utf-8"))
            detected["providers"].append(
                {
                    "id": "ollama:qualified-model",
                    "status": "AVAILABLE_VERIFIED",
                    "qualification": {"state": "PARTIAL", "task_classes": ["context-heavy-extraction"]},
                }
            )
            detected_path.write_text(json.dumps(detected), encoding="utf-8")
            qualifications = {
                "schema": "forge.provider-qualifications/v1",
                "evaluations": [
                    {
                        "provider": "ollama:qualified-model",
                        "task_class": "context-heavy-extraction",
                        "complexity": "low",
                        "verdict": "PASS",
                        "capabilities": ["worker.context-heavy-bounded"],
                        "lanes": ["model-local"],
                        "metrics": {"expected_quality": 0.9, "locality_advantage": 0.2, "verified_cost_advantage": 0.2, "parallelism_gain": 0.2, "retry_risk": 0.1},
                    }
                ],
            }
            (project / ".forge" / "capabilities" / "qualifications.json").write_text(json.dumps(qualifications), encoding="utf-8")
            request = {
                "work_order": "FI-HOST",
                "task_class": "context-heavy-extraction",
                "complexity": "low",
                "bounded": True,
                "required_capabilities": ["worker.context-heavy-bounded"],
                "required_lanes": ["model-local"],
                "mutation_risk": "read-only",
            }
            request_path = project / "route-request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            result = forge.route_work(str(project), str(request_path))
            self.assertEqual(result["selected"], "ollama:qualified-model")
            request["complexity"] = "critical"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            self.assertEqual(forge.route_work(str(project), str(request_path))["selected"], "resident")

            request["work_order"] = "W1"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            with self.assertRaisesRegex(forge.ForgeExit, "Unregistered work_order"):
                forge.route_work(str(project), str(request_path))

    def test_legacy_lifecycle_is_status_only_and_gsd_is_authoritative(self):
        with workspace_tempdir() as temp:
            project = temp / "LifecycleGame"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)

            result = forge.lifecycle_state(str(project))
            initial = result["state"]
            self.assertTrue(result["deprecated"])
            self.assertIn("GSD", result["authority"])
            self.assertTrue(initial["requires_fresh_task"])
            self.assertEqual(initial["next_command"], "forge-bootstrap --resume")
            self.assertEqual(result["next_command_for_host"], "/forge-bootstrap --resume")
            self.assertEqual(result["host"], "claude")
            with self.assertRaisesRegex(forge.ForgeExit, "transitions are deprecated"):
                forge.lifecycle_state(str(project), "bootstrap-start")

    def test_forge_next_routes_adoption_bootstrap_and_greenfield(self):
        with workspace_tempdir() as temp:
            project = temp / "Greenfield"
            project.mkdir()
            gsd = {"ok": True, "error": "", "snapshot": {"situation": "no-project", "actions": []}}
            self.assertEqual(forge.forge_next(str(project), gsd)["recommended"], "bootstrap")

            forge.install_overlay(str(project), apply=True)
            self.assertEqual(forge.forge_next(str(project), gsd)["recommended"], "bootstrap-resume")

            self.complete_bootstrap(project)
            result = forge.forge_next(str(project), gsd)
            self.assertEqual(result["situation"], "greenfield-ready")
            self.assertEqual(result["actions"][0]["command"], "/forge-init")
            self.assertEqual(result["authority"]["phase_state"], "gsd")

    def test_forge_next_routes_existing_docs_to_ingest(self):
        with workspace_tempdir() as temp:
            project = temp / "ExistingDesign"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            self.complete_bootstrap(project)
            design = project / "Docs" / "Design"
            design.mkdir(parents=True)
            (design / "Foundation-Plan.md").write_text("# Existing plan\n", encoding="utf-8")
            gsd = {"ok": True, "error": "", "snapshot": {"situation": "no-project", "actions": []}}
            result = forge.forge_next(str(project), gsd)
            self.assertEqual(result["situation"], "existing-design-unplanned")
            self.assertEqual(result["actions"][0]["command"], '/forge-ingest-docs "Docs\\Design"')

    def test_forge_next_routes_existing_unreal_project_to_onboard(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            forge.install_overlay(str(project), apply=True)
            self.complete_bootstrap(project)
            gsd = {"ok": True, "error": "", "snapshot": {"situation": "no-project", "actions": []}}
            result = forge.forge_next(str(project), gsd)
            self.assertEqual(result["situation"], "existing-project-unplanned")
            self.assertEqual(result["actions"][0]["command"], "/forge-onboard")

    def test_forge_next_preserves_gsd_smart_entry_as_phase_authority(self):
        with workspace_tempdir() as temp:
            project = temp / "PlannedGame"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            self.complete_bootstrap(project)
            (project / ".planning").mkdir()
            gsd = {
                "ok": True,
                "error": "",
                "snapshot": {
                    "situation": "executing",
                    "summary": "Phase 2 of 5 - executing",
                    "actions": [
                        {"id": "progress-next", "label": "Advance", "command": "/gsd:progress --next", "recommended": True},
                        {"id": "execute-phase", "label": "Continue", "command": "$gsd-execute-phase", "recommended": False},
                    ],
                },
            }
            result = forge.forge_next(str(project), gsd)
            self.assertEqual(result["situation"], "gsd-executing")
            self.assertEqual(result["recommended"], "progress-next")
            self.assertEqual(result["actions"][0]["command"], "/forge-progress --next")
            self.assertEqual(result["gsd_snapshot"]["situation"], "executing")

    def test_forge_next_does_not_route_to_missing_gsd(self):
        with workspace_tempdir() as temp:
            project = temp / "MissingGsd"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            self.complete_bootstrap(project)
            result = forge.forge_next(str(project), {"ok": False, "error": "runtime missing", "snapshot": None})
            self.assertEqual(result["situation"], "gsd-unavailable")
            self.assertEqual(result["actions"][0]["command"], "/forge-doctor")

    def test_host_swap_preserves_canon_and_regenerates_only_host_surfaces(self):
        with workspace_tempdir() as temp:
            project = temp / "PortableGame"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            self.complete_bootstrap(project)

            (project / ".planning").mkdir()
            (project / ".planning" / "STATE.md").write_text("phase 3\n", encoding="utf-8")
            packets = (project / ".forge" / "state" / "packet-registry.json").read_bytes()
            directives = (project / ".forge" / "directives.md").read_bytes()

            result = forge.host_set(str(project), "codex", apply=True)
            self.assertTrue(result["swapped"])
            self.assertEqual(result["previous_host"], "claude")

            self.assertTrue((project / "AGENTS.md").is_file())
            self.assertTrue((project / ".codex" / "agents" / "studio-director.toml").is_file())
            toml_text = (project / ".codex" / "agents" / "studio-director.toml").read_text(encoding="utf-8")
            self.assertIn("developer_instructions = ", toml_text)
            self.assertIn("$forge-plan-convergence", toml_text)

            self.assertFalse((project / "CLAUDE.md").exists())
            self.assertFalse((project / ".claude").exists())

            self.assertEqual((project / ".forge" / "state" / "packet-registry.json").read_bytes(), packets)
            self.assertEqual((project / ".forge" / "directives.md").read_bytes(), directives)
            self.assertEqual((project / ".planning" / "STATE.md").read_text(encoding="utf-8"), "phase 3\n")
            self.assertTrue((project / ".forge" / "agents" / "studio-director.json").is_file())

            self.assertTrue(forge.verify_overlay(str(project))["ok"])

    def test_host_swap_round_trip_is_byte_identical(self):
        with workspace_tempdir() as temp:
            project = temp / "RoundTrip"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            original = (project / "CLAUDE.md").read_bytes()
            agent = (project / ".claude" / "agents" / "researcher.md").read_bytes()

            forge.host_set(str(project), "codex", apply=True)
            forge.host_set(str(project), "claude", apply=True)

            self.assertEqual((project / "CLAUDE.md").read_bytes(), original)
            self.assertEqual((project / ".claude" / "agents" / "researcher.md").read_bytes(), agent)
            self.assertFalse((project / "AGENTS.md").exists())
            self.assertFalse((project / ".codex").exists())

    def test_host_swap_dry_run_writes_nothing(self):
        with workspace_tempdir() as temp:
            project = temp / "PreviewSwap"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            before = sorted(str(p.relative_to(project)) for p in project.rglob("*"))
            result = forge.host_set(str(project), "codex", apply=False)
            self.assertEqual(result["mode"], "dry-run")
            self.assertTrue(any(item["action"] == "retire" for item in result["actions"]))
            self.assertEqual(sorted(str(p.relative_to(project)) for p in project.rglob("*")), before)
            self.assertEqual(forge.host_status(str(project))["active_host"], "claude")

    def test_host_set_refuses_unknown_host_and_unadopted_project(self):
        with workspace_tempdir() as temp:
            project = temp / "Unadopted"
            project.mkdir()
            with self.assertRaisesRegex(forge.ForgeExit, "not adopted"):
                forge.host_set(str(project), "codex", apply=False)
            forge.install_overlay(str(project), apply=True)
            with self.assertRaisesRegex(forge.ForgeExit, "Unknown host"):
                forge.host_set(str(project), "not-a-host", apply=False)

    def test_forge_next_detects_stale_host_surfaces(self):
        with workspace_tempdir() as temp:
            project = temp / "StaleSurfaces"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            self.complete_bootstrap(project)
            gsd = {"ok": True, "error": "", "snapshot": {"situation": "no-project", "actions": []}}
            self.assertEqual(forge.forge_next(str(project), gsd)["situation"], "greenfield-ready")

            (project / "CLAUDE.md").unlink()
            result = forge.forge_next(str(project), gsd)
            self.assertEqual(result["situation"], "host-surfaces-stale")
            self.assertEqual(result["actions"][0]["id"], "host-render")
            self.assertFalse(result["runtime"]["surfaces_current"])

    def test_routing_rejects_qualification_recorded_under_another_host(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            forge.install_overlay(str(project), apply=True)
            detected_path = project / ".forge" / "capabilities" / "detected.json"
            detected = json.loads(detected_path.read_text(encoding="utf-8"))
            detected["providers"].append({"id": "ollama:m", "status": "AVAILABLE_VERIFIED"})
            detected_path.write_text(json.dumps(detected), encoding="utf-8")
            evaluation = {
                "provider": "ollama:m",
                "host": "codex",
                "task_class": "context-heavy-extraction",
                "complexity": "low",
                "verdict": "PASS",
                "capabilities": [],
                "lanes": [],
                "metrics": {"expected_quality": 0.9},
            }
            (project / ".forge" / "capabilities" / "qualifications.json").write_text(
                json.dumps({"evaluations": [evaluation]}), encoding="utf-8"
            )
            request = {
                "work_order": "FI-HOST",
                "task_class": "context-heavy-extraction",
                "complexity": "low",
                "bounded": True,
                "required_capabilities": [],
                "required_lanes": [],
                "mutation_risk": "read-only",
            }
            request_path = project / "route-request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")

            result = forge.route_work(str(project), str(request_path))
            self.assertEqual(result["selected"], "resident")
            self.assertEqual(result["resident_host"], "claude")
            candidate = next(item for item in result["candidates"] if item["provider"] == "ollama:m")
            self.assertFalse(candidate["eligible"])
            self.assertIn("re-probe", candidate["reason"])

            evaluation["host"] = "claude"
            (project / ".forge" / "capabilities" / "qualifications.json").write_text(
                json.dumps({"evaluations": [evaluation]}), encoding="utf-8"
            )
            self.assertEqual(forge.route_work(str(project), str(request_path))["selected"], "ollama:m")

    def test_every_registered_host_can_render_the_full_project_surface(self):
        for host_id in forge.host_profiles():
            with self.subTest(host=host_id), workspace_tempdir() as temp:
                project = temp / "MultiHost"
                project.mkdir()
                forge.install_overlay(str(project), apply=True, host_override=host_id)
                profile = forge.host_profile(host_id)
                surface = profile["project_surface"]
                self.assertTrue((project / surface["instruction_file"]).is_file())
                agents = list((project / surface["agent_dir"]).glob(f"*{surface['agent_extension']}"))
                self.assertEqual(len(agents), len(forge.agent_definitions(forge.template_root())))
                self.assertTrue(forge.verify_overlay(str(project), host_id)["ok"])
                for path in [project / surface["instruction_file"], *agents]:
                    self.assertNotIn("{{", path.read_text(encoding="utf-8"), str(path))

    def test_canon_never_carries_a_host_specific_spelling(self):
        banned = validate_repo.neutrality_banned_tokens(HOSTS)
        self.assertIn("codex", banned)
        self.assertIn("claude", banned)
        self.assertNotIn("generic", banned)

        roots = [
            ROOT / "plugins" / "forge-ue-studio" / "assets" / "project-template",
            ROOT / "plugins" / "forge-ue-studio" / "dependencies",
            ROOT / "plugins" / "forge-ue-studio" / "schemas",
        ]
        for root in roots:
            for path in root.rglob("*"):
                if not path.is_file() or path in validate_repo.NEUTRALITY_EXEMPT_FILES:
                    continue
                found = validate_repo.neutrality_violations(
                    path.read_text(encoding="utf-8-sig"), banned
                )
                self.assertEqual(found, [], f"{path.relative_to(ROOT)} leaks {found}")

    def test_neutrality_guard_catches_planted_leaks(self):
        banned = validate_repo.neutrality_banned_tokens(HOSTS)
        for leak in (
            '{"active": ["worker.codex.resident"]}',
            "Use Claude Code as the resident default.",
            "Run $forge-next to resume.",
            "Run /gsd-execute-phase next.",
            "Read the project AGENTS.md before working.",
        ):
            self.assertNotEqual(
                validate_repo.neutrality_violations(leak, banned), [], f"missed: {leak}"
            )

    def test_neutrality_guard_tolerates_paths_and_protocol_names(self):
        banned = validate_repo.neutrality_banned_tokens(HOSTS)
        for benign in (
            "plugins/forge-ue-studio/hosts/registry.json",
            "https://github.com/open-gsd/gsd-core",
            '"capability": "model.openai-compatible-endpoint"',
            "Use {{skill:forge-next}} after every boundary.",
            "The resident host owns {{resident}} synthesis.",
        ):
            self.assertEqual(
                validate_repo.neutrality_violations(benign, banned), [], f"false positive: {benign}"
            )

    def test_bootstrap_gate_enforces_every_forge_specific_check(self):
        with workspace_tempdir() as temp:
            project = temp / "BootstrapGate"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)

            report_path = project / ".forge" / "state" / "bootstrap-report.json"
            self.assertFalse(forge.bootstrap_verdict(project)["ok"])

            self.complete_bootstrap(project)
            verdict = forge.bootstrap_verdict(project)
            self.assertTrue(verdict["ok"], verdict["blocking"])
            self.assertEqual({c["id"] for c in verdict["checks"] if c["status"] == "FAIL"}, set())

            def failing_ids(mutate):
                report = json.loads(report_path.read_text(encoding="utf-8"))
                mutate(report)
                report_path.write_text(json.dumps(report), encoding="utf-8")
                result = forge.bootstrap_verdict(project)
                self.assertFalse(result["ok"])
                ids = {c["id"] for c in result["checks"] if c["status"] == "FAIL"}
                self.complete_bootstrap(project)
                return ids

            self.assertIn("report-schema", failing_ids(lambda r: r.pop("evidence")))
            self.assertIn("report-verdict", failing_ids(lambda r: r.update(verdict="FAIL")))
            self.assertIn("report-blocking", failing_ids(lambda r: r.update(blocking=["unresolved"])))
            self.assertIn("installation-jobs", failing_ids(lambda r: r.update(jobs=r["jobs"][:-1])))

            (project / "CLAUDE.md").write_text("# Project workflow\n", encoding="utf-8")
            result = forge.bootstrap_verdict(project)
            self.assertFalse(result["ok"])
            self.assertIn("phase-contract", {c["id"] for c in result["checks"] if c["status"] == "FAIL"})

    def test_forge_next_gates_on_the_full_bootstrap_verdict(self):
        with workspace_tempdir() as temp:
            project = temp / "GateWiring"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            gsd = {"ok": True, "error": "", "snapshot": {"situation": "no-project", "actions": []}}

            partial = {
                "schema": "forge.bootstrap-report/v1",
                "verdict": "PASS",
                "jobs": [],
                "delegation": {},
                "verified": [],
                "assumed": [],
                "unavailable": [],
                "blocking": [],
                "human_actions": [],
                "evidence": [],
                "next_action": "forge-next",
            }
            (project / ".forge" / "state" / "bootstrap-report.json").write_text(
                json.dumps(partial), encoding="utf-8"
            )
            self.assertEqual(forge.forge_next(str(project), gsd)["situation"], "forge-bootstrap-incomplete")

            self.complete_bootstrap(project)
            self.assertEqual(forge.forge_next(str(project), gsd)["situation"], "greenfield-ready")

    def test_execution_coverage_reports_partial_phases_without_blocking(self):
        with workspace_tempdir() as temp:
            project = temp / "Coverage"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            self.complete_bootstrap(project)
            phase = project / ".planning" / "phases" / "02-vertical-slice"
            phase.mkdir(parents=True)
            for name in ("02-01-PLAN.md", "02-02-PLAN.md", "02-03-PLAN.md"):
                (phase / name).write_text("# plan\n", encoding="utf-8")
            (phase / "02-01-SUMMARY.md").write_text("# summary\n", encoding="utf-8")

            coverage = forge.execution_coverage(project)
            self.assertEqual(len(coverage), 1)
            self.assertEqual(coverage[0]["state"], "partial")
            self.assertEqual(coverage[0]["summaries"], 1)
            self.assertEqual(coverage[0]["missing_summaries"], ["02-02-PLAN.md", "02-03-PLAN.md"])

            gsd = {"ok": True, "error": "", "snapshot": {"situation": "executing", "actions": [
                {"id": "continue", "label": "Continue", "command": "/gsd:progress", "recommended": True}
            ]}}
            result = forge.forge_next(str(project), gsd)
            self.assertEqual(result["recommended"], "continue")
            self.assertEqual(len(result["warnings"]), 1)
            self.assertIn("partially executed", result["warnings"][0])

            for name in ("02-02-SUMMARY.md", "02-03-SUMMARY.md"):
                (phase / name).write_text("# summary\n", encoding="utf-8")
            self.assertEqual(forge.execution_coverage(project)[0]["state"], "complete")
            self.assertEqual(forge.forge_next(str(project), gsd)["warnings"], [])

    def test_lifecycle_transitions_are_gone_not_merely_guarded(self):
        self.assertFalse(hasattr(forge, "require_artifacts"))
        self.assertFalse(hasattr(forge, "LIFECYCLE_EVENTS"))
        with workspace_tempdir() as temp:
            project = temp / "NoTransitions"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            with self.assertRaisesRegex(forge.ForgeExit, "transitions are deprecated"):
                forge.lifecycle_state(str(project), "execute-complete")

    def test_gsd_commands_are_translated_into_forge_vocabulary(self):
        claude = forge.host_profile("claude")
        codex = forge.host_profile("codex")
        self.assertEqual(forge.normalize_gsd_command("gsd-execute-phase", claude), "/forge-route-work")
        self.assertEqual(forge.normalize_gsd_command("gsd-execute-phase", codex), "$forge-route-work")
        self.assertEqual(forge.normalize_gsd_command("/gsd:progress --next", claude), "/forge-progress --next")
        self.assertEqual(forge.normalize_gsd_command("$gsd-onboard", claude), "/forge-onboard")
        self.assertEqual(forge.normalize_gsd_command("forge-next", codex), "$forge-next")
        leaked = forge.normalize_gsd_command("gsd-not-in-registry", claude)
        self.assertIn("UNMAPPED", leaked)

    def test_every_registry_verb_resolves_to_an_existing_skill(self):
        skills = {p.parent.name for p in (ROOT / "plugins" / "forge-ue-studio" / "skills").glob("*/SKILL.md")}
        for gsd_verb, forge_verb in forge.gsd_to_forge_verbs().items():
            with self.subTest(gsd=gsd_verb):
                self.assertIn(forge_verb, skills)
                self.assertFalse(forge_verb.startswith("gsd-"))

    def test_forge_next_never_surfaces_a_gsd_command(self):
        with workspace_tempdir() as temp:
            project = temp / "NoLeak"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            self.complete_bootstrap(project)
            (project / ".planning").mkdir(exist_ok=True)
            gsd = {
                "ok": True,
                "error": "",
                "snapshot": {
                    "situation": "executing",
                    "summary": "Phase 2 executing",
                    "actions": [
                        {"id": "a", "label": "Continue", "command": "/gsd:execute-phase 2", "recommended": True},
                        {"id": "b", "label": "Verify", "command": "$gsd-verify-work", "recommended": False},
                        {"id": "c", "label": "Onboard", "command": "gsd-onboard", "recommended": False},
                    ],
                },
            }
            result = forge.forge_next(str(project), gsd)
            commands = [action["command"] for action in result["actions"]]
            self.assertEqual(commands, ["/forge-route-work 2", "/forge-verify-work", "/forge-onboard"])
            for command in commands:
                self.assertNotIn("gsd-", command)

    def test_dropped_gsd_actions_are_suppressed_with_a_reason(self):
        with workspace_tempdir() as temp:
            project = temp / "Suppressed"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            self.complete_bootstrap(project)
            (project / ".planning").mkdir(exist_ok=True)
            gsd = {
                "ok": True,
                "error": "",
                "snapshot": {
                    "situation": "executing",
                    "actions": [
                        {"id": "a", "label": "Continue", "command": "gsd-execute-phase", "recommended": True},
                        {"id": "b", "label": "Capture", "command": "gsd-capture", "recommended": False},
                        {"id": "c", "label": "Quick", "command": "/gsd:quick", "recommended": False},
                    ],
                },
            }
            result = forge.forge_next(str(project), gsd)
            self.assertEqual([a["command"] for a in result["actions"]], ["/forge-route-work"])
            self.assertEqual(len(result["suppressed_actions"]), 2)
            for item in result["suppressed_actions"]:
                self.assertTrue(item["reason"])
            self.assertNotIn("UNMAPPED", json.dumps(result))

            spellings = {item["run_directly"] for item in result["suppressed_actions"]}
            self.assertEqual(spellings, {"/gsd-capture", "/gsd-quick"})

    def test_suppression_never_strands_the_user_with_no_action(self):
        with workspace_tempdir() as temp:
            project = temp / "AllSuppressed"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            self.complete_bootstrap(project)
            (project / ".planning").mkdir(exist_ok=True)
            gsd = {
                "ok": True,
                "error": "",
                "snapshot": {
                    "situation": "idle",
                    "actions": [
                        {"id": "a", "label": "Quick", "command": "gsd-quick", "recommended": True},
                        {"id": "b", "label": "Capture", "command": "gsd-capture", "recommended": False},
                    ],
                },
            }
            result = forge.forge_next(str(project), gsd)
            self.assertEqual(len(result["suppressed_actions"]), 2)
            self.assertTrue(result["actions"])
            self.assertIsNotNone(result["recommended"])
            self.assertEqual(result["actions"][0]["command"], "/forge-progress")

    def test_planning_helpers_are_fronted_not_orphaned(self):
        fronted = forge.gsd_to_forge_verbs()
        expected = {
            "gsd-mvp-phase": "forge-mvp-phase",
            "gsd-plan-milestone-gaps": "forge-milestone",
            "gsd-analyze-dependencies": "forge-plan-phase",
            "gsd-discuss-phase-assumptions": "forge-discuss-phase",
            "gsd-discuss-phase-power": "forge-discuss-phase",
            "gsd-list-phase-assumptions": "forge-discuss-phase",
            "gsd-insert-phase": "forge-phase",
            "gsd-remove-phase": "forge-phase",
            "gsd-edit-phase": "forge-phase",
        }
        for gsd_verb, forge_verb in expected.items():
            with self.subTest(gsd=gsd_verb):
                self.assertEqual(fronted.get(gsd_verb), forge_verb)

    def test_onboarding_and_resuming_are_first_class_forge_verbs(self):
        skills = {p.parent.name for p in (ROOT / "plugins" / "forge-ue-studio" / "skills").glob("*/SKILL.md")}
        for gsd_verb, forge_verb in (("gsd-onboard", "forge-onboard"), ("gsd-resume-work", "forge-resume-work")):
            with self.subTest(gsd=gsd_verb):
                self.assertEqual(forge.translate_gsd_verb(gsd_verb), forge_verb)
                self.assertIn(forge_verb, skills)
                self.assertEqual(
                    forge.normalize_gsd_command(gsd_verb, forge.host_profile("claude")), f"/{forge_verb}"
                )

    def test_every_command_smart_entry_can_emit_is_classified(self):
        emittable = {
            "gsd-capture", "gsd-code-review", "gsd-complete-milestone", "gsd-debug",
            "gsd-discuss-phase", "gsd-execute-phase", "gsd-extract-learnings", "gsd-help",
            "gsd-map-codebase", "gsd-new-milestone", "gsd-new-project", "gsd-plan-phase",
            "gsd-progress", "gsd-quick", "gsd-resume-work", "gsd-ship", "gsd-verify-work",
        }
        classified = set(forge.gsd_to_forge_verbs()) | set(forge.dropped_gsd_verbs())
        self.assertEqual(emittable - classified, set())

    def test_gsd_runtime_key_follows_the_assigned_host(self):
        with workspace_tempdir() as temp:
            project = temp / "RuntimeSync"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)

            self.assertEqual(forge.sync_gsd_runtime(project, forge.host_profile("claude"), True)["action"], "deferred")

            config = project / ".planning" / "config.json"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(json.dumps({"runtime": "claude", "other": "preserved"}), encoding="utf-8")

            forge.host_set(str(project), "codex", apply=True)
            written = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(written["runtime"], "codex")
            self.assertEqual(written["other"], "preserved")

            forge.host_set(str(project), "claude", apply=True)
            self.assertEqual(json.loads(config.read_text(encoding="utf-8"))["runtime"], "claude")

    def test_gsd_runtime_sync_is_dry_run_safe_and_skips_unknown_hosts(self):
        with workspace_tempdir() as temp:
            project = temp / "SyncSafety"
            project.mkdir()
            forge.install_overlay(str(project), apply=True)
            config = project / ".planning" / "config.json"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(json.dumps({"runtime": "claude"}), encoding="utf-8")

            result = forge.sync_gsd_runtime(project, forge.host_profile("codex"), apply=False)
            self.assertEqual(result["action"], "would-update")
            self.assertEqual(json.loads(config.read_text(encoding="utf-8"))["runtime"], "claude")

            self.assertEqual(forge.sync_gsd_runtime(project, forge.host_profile("generic"), True)["action"], "skipped")

    def test_packet_registry_has_unique_canonical_ids(self):
        registry_path = ROOT / "plugins" / "forge-ue-studio" / "assets" / "project-template" / ".forge" / "state" / "packet-registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        ids = [packet["id"] for packet in registry["packets"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("FI-HOST", ids)

    def test_contract_validator_preserves_evidence_boundaries(self):
        with workspace_tempdir() as temp:
            payload = {
                "work_order": "WO-1",
                "attempt": 1,
                "provider": "codex",
                "verdict": "PASS",
                "observed_facts": ["test passed"],
                "inferences": [],
                "findings": [],
                "touched": ["Source/Foo.cpp"],
                "evidence": [{"command": "test", "exit_code": 0}],
                "verification": [{"result": "PASS"}],
                "residual_risk": [],
                "next_action": "accept",
            }
            payload_path = temp / "attempt.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(forge.validate_payload("attempt-result", str(payload_path))["ok"])
            del payload["observed_facts"]
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            result = forge.validate_payload("attempt-result", str(payload_path))
            self.assertFalse(result["ok"])
            self.assertIn("missing required field: observed_facts", result["errors"])

    def test_repository_has_no_removed_provider_coupling(self):
        banned = ("ki" + "mi", "moon" + "shot")
        roots = [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "docs", ROOT / "plugins"]
        checked = []
        for root in roots:
            files = [root] if root.is_file() else root.rglob("*")
            for path in files:
                if path.is_file() and path.suffix.lower() in {".md", ".py", ".json", ".toml", ".ps1"}:
                    checked.append(path)
                    text = path.read_text(encoding="utf-8-sig").casefold()
                    self.assertFalse(any(term in text for term in banned), str(path.relative_to(ROOT)))
        self.assertTrue(checked)


class McpRouteTests(unittest.TestCase):
    """Typed tool routes: composition, host neutrality, probing, and the gates."""

    def setUp(self):
        self.registry = forge.route_registry()
        self.providers = self.registry["providers"]
        self.template = forge.template_root()
        self.agents = {item["name"]: item for item in forge.agent_definitions(self.template)}

    def test_every_provider_id_is_a_declared_dependency(self):
        catalog = json.loads(
            (ROOT / "plugins" / "forge-ue-studio" / "dependencies" / "catalog.json").read_text(encoding="utf-8")
        )
        declared = {item["id"] for item in catalog["dependencies"]}
        for provider in self.providers:
            self.assertIn(provider["id"], declared, provider["id"])

    def test_registry_names_no_host_spelling(self):
        """Canon declares servers; only the host registry spells a namespace."""
        text = (ROOT / "plugins" / "forge-ue-studio" / "dependencies" / "route-registry.json").read_text(encoding="utf-8")
        self.assertNotIn("mcp__", text)

    def test_namespace_is_composed_from_the_host(self):
        claude = forge.host_profile("claude")
        self.assertEqual(forge.mcp_tool_namespace(claude, "unreal-mcp"), "mcp__unreal-mcp__*")

    def test_agent_tool_surface_includes_typed_routes_on_an_mcp_host(self):
        surface = forge.agent_tool_surface(self.agents["unreal-operator"], forge.host_profile("claude"))
        self.assertIn("mcp__unreal-mcp__*", surface)
        self.assertIn("Read", surface)

    def test_agent_tool_surface_degrades_on_a_host_without_an_mcp_client(self):
        """generic declares no mcp-client, so no typed tool may be rendered."""
        surface = forge.agent_tool_surface(self.agents["unreal-operator"], forge.host_profile("generic"))
        self.assertFalse([item for item in surface if item.startswith("mcp__")])
        self.assertIn("Read", surface)

    def test_unknown_capability_is_a_hard_error(self):
        broken = dict(self.agents["unreal-operator"], mcp_capabilities=["ue.does.not.exist"])
        with self.assertRaises(forge.ForgeExit) as caught:
            forge.agent_tool_surface(broken, forge.host_profile("claude"))
        self.assertEqual(caught.exception.reason, forge.ERROR_REASON["MCP_UNKNOWN_CAPABILITY"])
        self.assertIn("ue.does.not.exist", str(caught.exception))

    def test_rendered_agent_carries_the_namespace_per_format(self):
        markdown = forge.render_agent(self.agents["unreal-operator"], forge.host_profile("claude"))
        self.assertIn("tools: Read, Write, Edit, Bash, Grep, Glob, mcp__unreal-mcp__*", markdown)
        toml = forge.render_agent(self.agents["unreal-operator"], forge.host_profile("codex"))
        self.assertIn('"mcp__unreal-mcp__*"', toml)

    def test_agents_without_declarations_keep_an_unrestricted_surface(self):
        rendered = forge.render_agent(self.agents["studio-director"], forge.host_profile("claude"))
        self.assertNotIn("tools:", rendered)

    def test_probe_reports_absence_without_guessing(self):
        with workspace_tempdir() as root:
            result = forge.probe_mcp_server(root, forge.host_profile("claude"), "unreal-mcp")
        self.assertFalse(result["found"])
        self.assertEqual(result["status"], "UNAVAILABLE_OPTIONAL")
        self.assertFalse(result["subagent_visible"])

    def test_probe_finds_a_project_scoped_server_but_marks_it_invisible_to_agents(self):
        with workspace_tempdir() as root:
            (root / ".mcp.json").write_text(json.dumps({"mcpServers": {"unreal-mcp": {}}}), encoding="utf-8")
            result = forge.probe_mcp_server(root, forge.host_profile("claude"), "unreal-mcp")
        self.assertTrue(result["found"])
        self.assertEqual(result["scope"], "project")
        self.assertFalse(result["subagent_visible"])
        self.assertIn("fallback", result["note"])

    def test_probe_ignores_a_bare_mention(self):
        with workspace_tempdir() as root:
            (root / ".mcp.json").write_text(json.dumps({"note": "unreal-mcp is great"}), encoding="utf-8")
            result = forge.probe_mcp_server(root, forge.host_profile("claude"), "unreal-mcp")
        self.assertFalse(result["found"])

    def test_probe_on_a_host_without_an_mcp_client_never_searches(self):
        with workspace_tempdir() as root:
            result = forge.probe_mcp_server(root, forge.host_profile("generic"), "unreal-mcp")
        self.assertFalse(result["found"])
        self.assertEqual(result["searched"], [])

    def test_contracts_cover_every_capability_and_never_self_qualify(self):
        with workspace_tempdir() as root:
            contracts = forge.mcp_capability_contracts(root, forge.host_profile("claude"))
        expected = sum(len(provider["capabilities"]) for provider in self.providers)
        self.assertEqual(len(contracts), expected)
        for contract in contracts:
            self.assertEqual(contract["qualification"]["state"], "UNQUALIFIED")
            self.assertIn(contract["status"], forge.STATUSES)
            self.assertTrue(contract["fallbacks"])
            self.assertTrue(contract["acceptance_suites"])

    def test_contract_shape_satisfies_the_capability_contract_schema(self):
        schema = json.loads(
            (ROOT / "plugins" / "forge-ue-studio" / "schemas" / "capability-contract.schema.json").read_text(encoding="utf-8")
        )
        with workspace_tempdir() as root:
            contracts = forge.mcp_capability_contracts(root, forge.host_profile("claude"))
        for contract in contracts:
            for field in schema["required"]:
                self.assertIn(field, contract, field)


class ProjectMcpTests(unittest.TestCase):
    """The game project owns its routes; the machine's config is not the truth."""

    def setUp(self):
        self.original_command_probe = forge.command_probe
        forge.command_probe = lambda command, timeout=8: {
            "ok": False, "exit_code": 1, "output": "", "error": "probe isolated in unit test",
        }
        self.profile = forge.host_profile("claude")

    def tearDown(self):
        forge.command_probe = self.original_command_probe

    @contextmanager
    def game(self):
        with workspace_tempdir() as temp:
            root = temp / "MyGame"
            root.mkdir()
            forge.install_overlay(str(root), apply=True)
            yield root

    def test_a_new_project_ships_the_first_party_unreal_route(self):
        """The Unreal layer is not left for the user to choose: the template declares it."""
        with self.game() as root:
            self.assertTrue((root / ".forge" / "mcp.json").is_file())
            declared = forge.resolve_project_servers(root)
            self.assertEqual([item["id"] for item in declared], ["unreal-native-mcp"])
            self.assertEqual(declared[0]["transport"]["type"], "http")
            self.assertTrue(declared[0]["transport"]["url"].endswith("/mcp"))

    def test_declared_server_reaches_the_session_surface(self):
        with self.game() as root:
            forge.mcp_amend(root, self.profile, "add", "blender-gateway", apply=True, command="uvx", args=["blender-mcp"])
            surface = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
            self.assertIn("blender-mcp", surface["mcpServers"])
            self.assertEqual(surface["mcpServers"]["blender-mcp"]["command"], "uvx")

    def test_a_declared_route_whose_probe_fails_is_unavailable_not_unverified(self):
        """Knowing a route is dead must degrade it to its fallback, not leave it dispatchable."""
        with self.game() as root:
            route = next(
                item for item in forge.mcp_status(root, self.profile)["routes"]
                if item["provider"] == "unreal-native-mcp"
            )
            self.assertTrue(route["declared_in_project"])
            self.assertFalse(route["live"])
            self.assertEqual(route["status"], "UNAVAILABLE_OPTIONAL")
            contract = next(
                item for item in forge.mcp_capability_contracts(root, self.profile)
                if item["capability"] == "ue.live.typed"
            )
            self.assertEqual(contract["health"], "UNAVAILABLE")
            self.assertEqual(contract["fallbacks"], ["ue.editor-closed-or-human"])

    def test_an_editor_hosted_server_renders_as_a_url_forge_never_starts(self):
        with self.game() as root:
            surface = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
            entry = surface["mcpServers"]["unreal-mcp"]
            self.assertEqual(entry["type"], "http")
            self.assertEqual(entry["url"], "http://127.0.0.1:8000/mcp")
            self.assertNotIn("command", entry)

    def test_a_catalog_entry_inherits_its_routing_fields(self):
        with self.game() as root:
            resolved = forge.resolve_project_servers(root)[0]
            self.assertEqual(resolved["source"], "catalog")
            self.assertEqual(resolved["lane"], "lane.ue-editor")
            self.assertEqual(resolved["isolation_mode"], "project-exclusive")
            self.assertIn("ue.live.typed", resolved["capabilities"])

    def test_a_catalog_entry_may_not_restate_catalog_fields(self):
        with self.game() as root:
            path = root / ".forge" / "mcp.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["servers"] = [{
                "id": "unreal-native-mcp", "enabled": True,
                "transport": {"command": "uvx"}, "lane": "somewhere-else",
            }]
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(forge.ForgeExit) as caught:
                forge.resolve_project_servers(root)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["MCP_FIELD_RESTATED"])

    def test_a_project_local_server_must_declare_its_own_routing(self):
        with self.game() as root:
            path = root / ".forge" / "mcp.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["servers"] = [{"id": "some-new-tool", "enabled": True, "transport": {"command": "node"}}]
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(forge.ForgeExit) as caught:
                forge.resolve_project_servers(root)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["MCP_INCOMPLETE_DECLARATION"])

    def test_a_fully_declared_project_local_server_routes(self):
        """Any other app: adoptable without shipping a catalog change."""
        with self.game() as root:
            path = root / ".forge" / "mcp.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["servers"] = [{
                "id": "some-new-tool", "enabled": True, "transport": {"command": "node", "args": ["srv.js"]},
                "server": "some-new-tool", "capabilities": ["audio.mix"], "lane": "lane.audio-authoring",
                "isolation_mode": "git-worktree", "fallbacks": ["human-audio-pass"],
            }]
            path.write_text(json.dumps(document), encoding="utf-8")
            resolved = forge.resolve_project_servers(root)[0]
            self.assertEqual(resolved["source"], "project")
            self.assertEqual(resolved["lane"], "lane.audio-authoring")
            rendered = forge.render_project_mcp(root, self.profile, root)
            self.assertIn("some-new-tool", json.loads(rendered[1].decode("utf-8"))["mcpServers"])

    def test_rendering_preserves_servers_forge_does_not_own(self):
        with self.game() as root:
            surface = root / ".mcp.json"
            document = json.loads(surface.read_text(encoding="utf-8"))
            document["mcpServers"]["hand-added"] = {"command": "node"}
            document["unrelatedKey"] = {"kept": True}
            surface.write_text(json.dumps(document), encoding="utf-8")
            forge.mcp_amend(root, self.profile, "add", "blender-gateway", apply=True, command="uvx")
            after = json.loads(surface.read_text(encoding="utf-8"))
            self.assertIn("hand-added", after["mcpServers"])
            self.assertEqual(after["unrelatedKey"], {"kept": True})

    def test_disabling_withdraws_only_that_server(self):
        with self.game() as root:
            forge.mcp_amend(root, self.profile, "add", "blender-gateway", apply=True, command="uvx")
            forge.mcp_amend(root, self.profile, "disable", "blender-gateway", apply=True)
            servers = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
            self.assertIn("unreal-mcp", servers)
            self.assertNotIn("blender-mcp", servers)

    def test_dry_run_amend_writes_nothing(self):
        with self.game() as root:
            before = (root / ".forge" / "mcp.json").read_text(encoding="utf-8")
            surface_before = (root / ".mcp.json").read_text(encoding="utf-8")
            result = forge.mcp_amend(root, self.profile, "add", "blender-gateway", apply=False, command="uvx")
            self.assertEqual(result["mode"], "dry-run")
            self.assertEqual((root / ".forge" / "mcp.json").read_text(encoding="utf-8"), before)
            self.assertEqual((root / ".mcp.json").read_text(encoding="utf-8"), surface_before)

    def test_an_unroutable_amendment_never_lands_on_disk(self):
        with self.game() as root:
            declaration = root / ".forge" / "mcp.json"
            before = declaration.read_text(encoding="utf-8")
            surface_before = (root / ".mcp.json").read_text(encoding="utf-8")
            with self.assertRaises(forge.ForgeExit) as caught:
                forge.mcp_amend(root, self.profile, "add", "some-new-tool", apply=True, command="node")
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["MCP_INCOMPLETE_DECLARATION"])
            self.assertEqual(declaration.read_text(encoding="utf-8"), before)
            self.assertEqual((root / ".mcp.json").read_text(encoding="utf-8"), surface_before)

    def test_status_separates_the_declared_scope_from_where_the_probe_found_it(self):
        with self.game() as root:
            forge.mcp_amend(root, self.profile, "add", "blender-gateway", apply=True, command="uvx", scope="both")
            route = next(
                item for item in forge.mcp_status(root, self.profile)["routes"]
                if item["provider"] == "blender-gateway"
            )
            self.assertEqual(route["scope"], "both")
            self.assertEqual(route["found_in_scope"], "project")

    def test_status_reports_session_visibility_from_the_project(self):
        with self.game() as root:
            status = forge.mcp_status(root, self.profile)
            route = next(item for item in status["routes"] if item["provider"] == "unreal-native-mcp")
            self.assertTrue(route["declared_in_project"])
            self.assertTrue(route["rendered_to_host"])
            self.assertTrue(route["session_visible"])
            self.assertFalse(route["subagent_visible"])

    def test_the_project_surface_is_tracked_like_every_other_rendered_surface(self):
        """A hand-edited surface is a LOCAL_VARIANT like any rendered file, and
        status reports the lost server by probing rather than diffing."""
        with self.game() as root:
            surface_path = str((root / ".mcp.json").resolve())
            checks = {c["path"]: c for c in forge.verify_overlay(str(root), "claude")["checks"]}
            tracked = next(c for path, c in checks.items() if Path(path).name == ".mcp.json")
            self.assertEqual(tracked["status"], "MATCH")
            self.assertEqual(tracked["kind"], "host-rendered")

            (root / ".mcp.json").write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
            checks = {c["path"]: c for c in forge.verify_overlay(str(root), "claude")["checks"]}
            tracked = next(c for path, c in checks.items() if Path(path).name == ".mcp.json")
            self.assertEqual(tracked["status"], "LOCAL_VARIANT")
            route = next(
                item for item in forge.mcp_status(root, self.profile)["routes"]
                if item["provider"] == "unreal-native-mcp"
            )
            self.assertFalse(route["session_visible"])
            self.assertTrue(surface_path)

    def test_a_host_without_a_project_surface_renders_nothing(self):
        with self.game() as root:
            self.assertIsNone(forge.render_project_mcp(root, forge.host_profile("codex"), root))


class FailureContractTests(unittest.TestCase):
    """Every declared failure carries a typed reason and an exit code."""

    def test_reason_vocabulary_is_frozen(self):
        with self.assertRaises(TypeError):
            forge.ERROR_REASON["NEW"] = "new"

    def test_reason_values_are_snake_case_and_unique(self):
        values = list(forge.ERROR_REASON.values())
        self.assertEqual(len(values), len(set(values)))
        for value in values:
            self.assertRegex(value, r"^[a-z][a-z0-9_]*$")

    def test_an_undeclared_reason_is_refused(self):
        with self.assertRaises(ValueError):
            forge.ForgeExit("x", reason="not_a_declared_reason")

    def test_failure_payload_shape(self):
        error = forge.fail("boom", reason=forge.ERROR_REASON["USAGE"], code=forge.EXIT_USAGE, detail="extra")
        self.assertEqual(
            error.payload(),
            {"ok": False, "reason": "usage", "message": "boom", "detail": "extra"},
        )
        self.assertEqual(error.code, forge.EXIT_USAGE)

    def test_cli_emits_a_typed_reason_and_its_exit_code(self):
        with workspace_tempdir() as temp:
            completed = subprocess.run(
                [sys.executable, str(FORGE_PATH), "host", "status", "--project", str(temp / "missing")],
                capture_output=True, text=True,
            )
        self.assertEqual(completed.returncode, forge.EXIT_USAGE)
        payload = json.loads(completed.stderr)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["reason"], forge.ERROR_REASON["PROJECT_NOT_FOUND"])
        self.assertEqual(payload["command"], "host")

    def test_every_declared_reason_is_reachable_from_a_call_site(self):
        """A reason may be raised from any module, so every module is scanned."""
        source = "\n".join(path.read_text(encoding="utf-8") for path in MODULE_PATHS)
        declared = set(forge.ERROR_REASON)
        used = {
            key for key in declared
            if f'ERROR_REASON["{key}"]' in source or f'ERROR_REASONS["{key}"]' in source
        }
        self.assertEqual(sorted(declared - used), [])

    def test_only_a_reason_vocabulary_may_raise_a_bare_value_error(self):
        """Two modules declare a reason enum; each guards its own, and nothing else does."""
        for path in MODULE_PATHS:
            sites = re.findall(r"raise ValueError\(", path.read_text(encoding="utf-8"))
            expected = 1 if path in REASON_OWNERS else 0
            self.assertEqual(len(sites), expected, f"unexpected ValueError count in {path.name}")

    def test_logic_never_calls_sys_exit(self):
        """Checked structurally: a textual scan would match the prose explaining
        the rule and pass or fail for the wrong reason."""
        tree = ast.parse(FORGE_PATH.read_text(encoding="utf-8"))
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "exit"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "sys"
        ]
        self.assertEqual(calls, [])


class ResultContractTests(unittest.TestCase):
    """`ok` means a verdict everywhere, or it means nothing anywhere."""

    def setUp(self):
        self.original_command_probe = forge.command_probe
        forge.command_probe = lambda command, timeout=8: {
            "ok": False, "exit_code": 1, "output": "", "error": "probe isolated in unit test",
        }

    def tearDown(self):
        forge.command_probe = self.original_command_probe

    @contextmanager
    def game(self):
        with workspace_tempdir() as temp:
            root = temp / "Game"
            root.mkdir()
            forge.install_overlay(str(root), apply=True)
            yield root

    def _run(self, *argv):
        return subprocess.run(
            [sys.executable, str(FORGE_PATH), *argv], capture_output=True, text=True
        )

    def test_every_verdict_command_is_a_real_command_path(self):
        self.assertTrue(forge.VERDICT_COMMANDS)
        source = FORGE_PATH.read_text(encoding="utf-8")
        for command in sorted(forge.VERDICT_COMMANDS):
            head = command.split()[0]
            self.assertIn(f'"{head}"', source, command)

    def _payloads(self, root):
        """Every result the CLI can emit, produced in-process.

        Not subprocesses: a spawned CLI re-runs live host probes, which is slow
        and varies with whatever happens to be installed."""
        profile = forge.host_profile("claude")
        return {
            "verify": (forge.verify_overlay(str(root), None), True),
            "bootstrap-check": (forge.bootstrap_verdict(root, profile), True),
            "host status": (forge.host_status(str(root), None), True),
            "host list": (forge.host_list(), False),
            "next": (forge.forge_next(str(root)), False),
            "lifecycle": (forge.lifecycle_state(str(root), "status"), False),
            "mcp-status": (forge.mcp_status(root, profile), False),
            "install": (forge.install_overlay(str(root), apply=False), False),
        }

    def test_verdict_commands_emit_ok_and_reporting_commands_do_not(self):
        with self.game() as root:
            for name, (payload, expects_verdict) in self._payloads(root).items():
                self.assertEqual("ok" in payload, expects_verdict, f"{name} verdict presence")

    def test_every_payload_identifies_itself(self):
        with self.game() as root:
            for name, (payload, _) in self._payloads(root).items():
                self.assertTrue(payload.get("schema"), name)

    def test_the_declared_set_matches_what_the_payloads_actually_carry(self):
        with self.game() as root:
            for name, (payload, _) in self._payloads(root).items():
                self.assertEqual(
                    name in forge.VERDICT_COMMANDS, "ok" in payload,
                    f"{name}: VERDICT_COMMANDS and the payload disagree",
                )

    def test_a_failing_verdict_exits_contract_not_failure(self):
        """Ran-and-said-no must stay distinguishable from could-not-run."""
        with self.game() as root:
            completed = self._run("bootstrap-check", "--project", str(root))
            self.assertEqual(completed.returncode, forge.EXIT_CONTRACT)
            self.assertFalse(json.loads(completed.stdout)["ok"])

    def test_a_verdict_command_returning_no_ok_is_refused(self):
        source = FORGE_PATH.read_text(encoding="utf-8")
        self.assertIn('command_path in VERDICT_COMMANDS and not carries_verdict', source)
        self.assertIn('command_path not in VERDICT_COMMANDS and carries_verdict', source)
        self.assertNotIn('result.get("ok", True) else EXIT_CONTRACT\n    except', source)


class ActionSurfaceTests(unittest.TestCase):
    """A routed action is a Forge verb, ids included. What Forge does not route
    stays available as the GSD command it is."""

    def test_no_routed_action_id_carries_a_gsd_prefix(self):
        """The command is translated at dispatch, but the id is displayed too."""
        source = (SCRIPTS_DIR / "forge_lifecycle.py").read_text(encoding="utf-8")
        ids = re.findall(r"forge_action\(\s*\"([^\"]+)\"", source)
        self.assertTrue(ids, "no forge_action ids found; the guard would assert over nothing")
        self.assertEqual([item for item in ids if item.startswith("gsd-")], [])

    def test_every_routed_action_id_is_unique_per_situation(self):
        source = (SCRIPTS_DIR / "forge_lifecycle.py").read_text(encoding="utf-8")
        for block in re.findall(r"actions\s*=\s*\[(.*?)\n\s*\]", source, re.DOTALL):
            ids = re.findall(r"forge_action\(\s*\"([^\"]+)\"", block)
            self.assertEqual(len(ids), len(set(ids)), f"duplicate action id in block: {ids}")

    def test_no_situation_offers_the_same_command_twice(self):
        """Two ids that translate to one verb are a choice the user does not have.
        Distinct ids are not enough: the registry fronts GSD verbs with Forge ones,
        so an alternative naming the fronted verb collapses onto the recommended one."""
        profile = forge.host_profile("claude")
        tree = ast.parse((SCRIPTS_DIR / "forge_lifecycle.py").read_text(encoding="utf-8"))
        blocks = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.List):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "actions" for t in node.targets):
                continue
            rendered = {}
            for call in node.value.elts:
                if not (isinstance(call, ast.Call) and getattr(call.func, "id", "") == "forge_action"):
                    continue
                action_id = call.args[0].value
                spelling = call.args[2]
                if isinstance(spelling, ast.Constant):
                    command = spelling.value
                elif isinstance(spelling, ast.JoinedStr):
                    command = "".join(p.value for p in spelling.values if isinstance(p, ast.Constant))
                else:
                    continue
                verb = forge.normalize_gsd_command(command.split()[0], profile)
                rendered.setdefault(verb, []).append(action_id)
            blocks += 1
            for verb, owners in sorted(rendered.items()):
                self.assertEqual(len(owners), 1, f"{owners} all render as {verb}")
        self.assertGreater(blocks, 3, "no action blocks parsed; the guard would assert over nothing")


class UserScopeMcpTests(unittest.TestCase):
    """Publishing to user scope: planned by default, consented when applied, and
    never destructive to what it finds."""

    def setUp(self):
        self.original_command_probe = forge.command_probe
        forge.command_probe = lambda command, timeout=8: {
            "ok": False, "exit_code": 1, "output": "", "error": "probe isolated in unit test",
        }

    def tearDown(self):
        forge.command_probe = self.original_command_probe

    @contextmanager
    def game(self, host="claude"):
        """Yield a project plus a profile whose user surface points at a sandbox
        file, so no test writes the developer's real config."""
        with workspace_tempdir() as temp:
            root = temp / "MyGame"
            root.mkdir()
            forge.install_overlay(str(root), apply=True)
            profile = json.loads(json.dumps(forge.host_profile(host)))
            surface = profile.get("mcp", {}).get("user_surface")
            if surface:
                surface["path"] = str(temp / "userconfig.json")
            yield root, profile, temp / "userconfig.json"

    def test_project_scope_stays_out_of_user_scope(self):
        with self.game() as (root, profile, user_file):
            forge.mcp_amend(root, profile, "add", "blender-gateway", apply=True, command="uvx", scope="project")
            plan = forge.sync_user_mcp(root, profile, apply=False)
            self.assertEqual(plan["wanted"], [])
            self.assertEqual(plan["planned"], [])
            self.assertFalse(user_file.exists())

    def test_user_scope_only_stays_out_of_the_project_surface(self):
        with self.game() as (root, profile, _):
            forge.mcp_amend(root, profile, "add", "blender-gateway", apply=True, command="uvx", scope="user")
            rendered = forge.render_project_mcp(root, profile, root)
            self.assertNotIn("blender-mcp", json.loads(rendered[1].decode("utf-8"))["mcpServers"])

    def test_both_reaches_each_surface(self):
        with self.game() as (root, profile, user_file):
            forge.mcp_amend(root, profile, "add", "blender-gateway", apply=True, command="uvx", scope="both")
            project = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
            self.assertIn("blender-mcp", project["mcpServers"])
            forge.sync_user_mcp(root, profile, apply=True)
            self.assertIn("blender-mcp", json.loads(user_file.read_text(encoding="utf-8"))["mcpServers"])

    def test_sync_is_a_plan_until_asked(self):
        with self.game() as (root, profile, user_file):
            forge.mcp_amend(root, profile, "add", "blender-gateway", apply=True, command="uvx", scope="user")
            plan = forge.sync_user_mcp(root, profile, apply=False)
            self.assertEqual(plan["mode"], "dry-run")
            self.assertFalse(plan["applied"])
            self.assertTrue(plan["consent_required"])
            self.assertFalse(user_file.exists())

    def test_applying_preserves_every_other_key_and_server(self):
        with self.game() as (root, profile, user_file):
            user_file.write_text(json.dumps({
                "numStartups": 42,
                "projects": {"/elsewhere": {"history": ["a", "b"]}},
                "mcpServers": {"someone-elses": {"command": "node"}},
            }), encoding="utf-8")
            forge.mcp_amend(root, profile, "add", "blender-gateway", apply=True, command="uvx", scope="user")
            forge.sync_user_mcp(root, profile, apply=True)
            after = json.loads(user_file.read_text(encoding="utf-8"))
            self.assertEqual(after["numStartups"], 42)
            self.assertEqual(after["projects"], {"/elsewhere": {"history": ["a", "b"]}})
            self.assertIn("someone-elses", after["mcpServers"])
            self.assertIn("blender-mcp", after["mcpServers"])

    def test_applying_backs_up_and_records_consent(self):
        with self.game() as (root, profile, user_file):
            user_file.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
            forge.mcp_amend(root, profile, "add", "blender-gateway", apply=True, command="uvx", scope="user")
            result = forge.sync_user_mcp(root, profile, apply=True)
            self.assertTrue(Path(result["backup"]).is_file())
            ledger = json.loads((root / ".forge" / "capabilities" / "consent-ledger.json").read_text(encoding="utf-8"))
            self.assertTrue(any(e["scope"] == "mcp.user-scope-write" for e in ledger["entries"]))

    def test_withdrawing_reclaims_only_an_unmodified_entry(self):
        with self.game() as (root, profile, user_file):
            forge.mcp_amend(root, profile, "add", "blender-gateway", apply=True, command="uvx", scope="user")
            forge.sync_user_mcp(root, profile, apply=True)
            forge.mcp_amend(root, profile, "disable", "blender-gateway", apply=True)
            forge.sync_user_mcp(root, profile, apply=True)
            self.assertNotIn("blender-mcp", json.loads(user_file.read_text(encoding="utf-8"))["mcpServers"])

    def test_a_hand_edited_entry_is_reported_not_reclaimed(self):
        with self.game() as (root, profile, user_file):
            forge.mcp_amend(root, profile, "add", "blender-gateway", apply=True, command="uvx", scope="user")
            forge.sync_user_mcp(root, profile, apply=True)
            document = json.loads(user_file.read_text(encoding="utf-8"))
            document["mcpServers"]["blender-mcp"] = {"command": "my-own-wrapper"}
            user_file.write_text(json.dumps(document), encoding="utf-8")
            forge.mcp_amend(root, profile, "disable", "blender-gateway", apply=True)
            plan = forge.sync_user_mcp(root, profile, apply=False)
            retained = [c for c in plan["planned"] if c["action"] == "retain-modified"]
            self.assertEqual([c["server"] for c in retained], ["blender-mcp"])
            forge.sync_user_mcp(root, profile, apply=True)
            after = json.loads(user_file.read_text(encoding="utf-8"))
            self.assertEqual(after["mcpServers"]["blender-mcp"], {"command": "my-own-wrapper"})

    def test_an_unparseable_config_is_never_rewritten(self):
        with self.game() as (root, profile, user_file):
            user_file.write_text("{ this is not json", encoding="utf-8")
            forge.mcp_amend(root, profile, "add", "blender-gateway", apply=True, command="uvx", scope="user")
            result = forge.sync_user_mcp(root, profile, apply=True)
            self.assertEqual(result["mode"], "blocked")
            self.assertFalse(result["applied"])
            self.assertEqual(user_file.read_text(encoding="utf-8"), "{ this is not json")

    def test_a_host_forge_may_not_write_reports_instead(self):
        with self.game(host="codex") as (root, profile, _):
            forge.mcp_amend(root, profile, "add", "blender-gateway", apply=True, command="uvx", scope="user")
            result = forge.sync_user_mcp(root, profile, apply=True)
            self.assertEqual(result["mode"], "report-only")
            self.assertFalse(result["applied"])
            self.assertEqual([c["action"] for c in result["planned"]], ["declare-by-hand"])


class McpGateTests(unittest.TestCase):
    """Each validator gate must fail on a planted violation."""

    def _validate(self, mutate):
        """Run the repo validator against a mutated copy of the repository."""
        with workspace_tempdir() as root:
            copy = root / "repo"
            shutil.copytree(
                ROOT,
                copy,
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".tmp"),
            )
            mutate(copy)
            completed = subprocess.run(
                [sys.executable, str(copy / "scripts" / "validate_repo.py")],
                capture_output=True,
                text=True,
                cwd=str(copy),
            )
            return completed.returncode, completed.stdout + completed.stderr

    @staticmethod
    def _rewrite(path: Path, mutate):
        document = json.loads(path.read_text(encoding="utf-8"))
        mutate(document)
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    def test_baseline_repository_passes(self):
        code, output = self._validate(lambda root: None)
        self.assertEqual(code, 0, output)

    def test_provider_without_a_dependency_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "dependencies" / "route-registry.json",
                lambda doc: doc["providers"][0].__setitem__("id", "not-a-dependency"),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("not a declared dependency", output)

    def test_undeclared_lane_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "dependencies" / "route-registry.json",
                lambda doc: doc["providers"][0].__setitem__("lane", "ue.imaginary"),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("undeclared lane", output)

    def test_unknown_acceptance_suite_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "dependencies" / "route-registry.json",
                lambda doc: doc["providers"][0].__setitem__("acceptance_suites", ["FORGE-NOPE-99"]),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("unknown acceptance suite", output)

    def test_two_providers_serving_one_capability_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "dependencies" / "route-registry.json",
                lambda doc: doc["providers"][1].__setitem__("capabilities", doc["providers"][0]["capabilities"]),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("ambiguous", output)

    def test_agent_capability_with_no_provider_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "assets" / "project-template" / ".forge" / "agents" / "unreal-operator.json",
                lambda doc: doc.__setitem__("mcp_capabilities", ["ue.phantom"]),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("no MCP provider serves", output)

    def test_typed_agent_without_a_fallback_route_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "assets" / "project-template" / ".forge" / "agents" / "unreal-operator.json",
                lambda doc: doc.__setitem__("instructions", "Operate the editor."),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("names no fallback route", output)

    def test_host_providing_mcp_client_without_an_mcp_block_fails(self):
        def mutate(root):
            def drop(doc):
                for host in doc["hosts"]:
                    host.pop("mcp", None)

            self._rewrite(root / "plugins" / "forge-ue-studio" / "hosts" / "registry.json", drop)

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("declares no mcp block", output)

    def test_namespace_template_without_the_server_token_fails(self):
        def mutate(root):
            def blunt(doc):
                doc["hosts"][0]["mcp"]["tool_namespace_template"] = "mcp__fixed__*"

            self._rewrite(root / "plugins" / "forge-ue-studio" / "hosts" / "registry.json", blunt)

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("interpolate", output)

    def test_a_dependency_with_no_routing_state_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "dependencies" / "catalog.json",
                lambda doc: doc["dependencies"][0].pop("routing", None),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("unknown routing state", output)

    def test_an_unrouted_dependency_without_a_note_fails(self):
        def mutate(root):
            def strip(doc):
                for dep in doc["dependencies"]:
                    if dep.get("routing") == "declared":
                        dep.pop("routing_note", None)
                        return

            self._rewrite(root / "plugins" / "forge-ue-studio" / "dependencies" / "catalog.json", strip)

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("how it is actually exercised", output)

    def test_a_false_routed_claim_fails(self):
        def mutate(root):
            def lie(doc):
                for dep in doc["dependencies"]:
                    if dep.get("routing") == "declared":
                        dep["routing"] = "routed"
                        return

            self._rewrite(root / "plugins" / "forge-ue-studio" / "dependencies" / "catalog.json", lie)

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("claims routed but no provider serves", output)

    def test_activation_naming_an_undeclared_capability_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "assets" / "project-template" / ".forge" / "context" / "activation-policy.json",
                lambda doc: doc["profiles"]["design"].append("capability.that.does.not.exist"),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("which no dependency declares", output)

    def test_an_unprefixed_lane_fails(self):
        def mutate(root):
            def rename(doc):
                doc["lanes"]["ue.editor"] = doc["lanes"].pop("lane.ue-editor")
                doc["providers"][0]["lane"] = "ue.editor"

            self._rewrite(root / "plugins" / "forge-ue-studio" / "dependencies" / "route-registry.json", rename)

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("must carry the lane. prefix", output)

    def test_a_skill_that_does_not_load_its_workflow_fails(self):
        def mutate(root):
            skill = root / "plugins" / "forge-ue-studio" / "skills" / "forge-undo" / "SKILL.md"
            text = skill.read_text(encoding="utf-8")
            skill.write_text(text.replace("@<forge-plugin-root>/workflows/forge-undo.md\n", ""), encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("does not load its own workflow", output)

    def test_a_workflow_no_skill_loads_fails(self):
        def mutate(root):
            orphan = root / "plugins" / "forge-ue-studio" / "workflows" / "forge-orphan.md"
            orphan.write_text("# Orphan\n\n1. Do nothing.\n", encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("is loaded by no skill", output)

    def test_a_skill_loading_an_undeclared_gsd_workflow_fails(self):
        def mutate(root):
            skill = root / "plugins" / "forge-ue-studio" / "skills" / "forge-undo" / "SKILL.md"
            text = skill.read_text(encoding="utf-8")
            skill.write_text(
                text.replace("@<gsd-core>/workflows/undo.md", "@<gsd-core>/workflows/undo.md\n@<gsd-core>/workflows/ship.md"),
                encoding="utf-8",
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("the verb registry does not map to it", output)

    def test_a_description_that_says_when_to_use_it_fails(self):
        def mutate(root):
            skill = root / "plugins" / "forge-ue-studio" / "skills" / "forge-undo" / "SKILL.md"
            text = skill.read_text(encoding="utf-8")
            skill.write_text(
                text.replace(
                    "description: Roll back a phase or plan when execution went wrong",
                    "description: Roll back a phase or plan. Use when execution went wrong",
                ),
                encoding="utf-8",
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("description states when to use it", output)

    def test_a_skill_missing_a_required_section_fails(self):
        def mutate(root):
            skill = root / "plugins" / "forge-ue-studio" / "skills" / "forge-undo" / "SKILL.md"
            text = skill.read_text(encoding="utf-8")
            skill.write_text(text.replace("<invocation>", "<invoked>"), encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("is missing its <invocation> block", output)

    def test_a_shipped_schema_the_installer_cannot_validate_fails(self):
        def mutate(root):
            installer = root / "install.ps1"
            text = installer.read_text(encoding="utf-8-sig")
            installer.write_text(text.replace("'project-mcp', ", "", 1), encoding="utf-8-sig")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("cannot validate shipped schema", output)

    def test_a_cli_verb_with_no_installer_mode_fails(self):
        def mutate(root):
            source = root / "plugins" / "forge-ue-studio" / "scripts" / "forge.py"
            text = source.read_text(encoding="utf-8")
            text = text.replace(
                'validate = sub.add_parser("validate")',
                'orphan = sub.add_parser("orphan-verb")\n    validate = sub.add_parser("validate")',
                1,
            )
            source.write_text(text, encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("has no install.ps1 -Mode", output)

    def test_an_agent_no_skill_dispatches_to_fails(self):
        def mutate(root):
            agents = root / "plugins" / "forge-ue-studio" / "assets" / "project-template" / ".forge" / "agents"
            (agents / "never-dispatched.json").write_text(
                json.dumps({
                    "schema": "forge.agent-definition/v1", "name": "never-dispatched",
                    "role": "engineering", "description": "x", "instructions": "y",
                }), encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("no skill names it as a dispatch target", output)

    def test_a_comment_in_shipped_code_fails(self):
        def mutate(root):
            source = root / "plugins" / "forge-ue-studio" / "scripts" / "forge_core.py"
            text = source.read_text(encoding="utf-8")
            source.write_text(text.replace("def utc_now()", "# why\ndef utc_now()", 1), encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("carries a comment", output)

    def test_a_shebang_and_tool_pragma_are_not_comments(self):
        def mutate(root):
            source = root / "scripts" / "validate_repo.py"
            text = source.read_text(encoding="utf-8")
            source.write_text(text.replace("import json", "import json  # noqa: F401", 1), encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 0, output)

    def test_a_state_file_nothing_reads_fails(self):
        def mutate(root):
            state = root / "plugins" / "forge-ue-studio" / "assets" / "project-template" / ".forge" / "state"
            (state / "unread-ledger.json").write_text(json.dumps({"entries": []}), encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("has no reader", output)

    def test_a_verdict_command_that_is_not_a_command_fails(self):
        def mutate(root):
            source = root / "plugins" / "forge-ue-studio" / "scripts" / "forge.py"
            text = source.read_text(encoding="utf-8")
            mutated = text.replace('        "verify",\n', '        "not-a-command",\n        "verify",\n', 1)
            self.assertNotEqual(mutated, text, "VERDICT_COMMANDS anchor not found")
            source.write_text(mutated, encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("not a declared CLI command", output)

    def test_dropping_the_result_contract_assertion_fails(self):
        def mutate(root):
            source = root / "plugins" / "forge-ue-studio" / "scripts" / "forge.py"
            text = source.read_text(encoding="utf-8")
            text = text.replace("command_path not in VERDICT_COMMANDS and carries_verdict", "False", 1)
            source.write_text(text, encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("does not assert the result contract", output)

    def test_an_inline_reason_string_fails(self):
        def mutate(root):
            source = root / "plugins" / "forge-ue-studio" / "scripts" / "forge_hosts.py"
            text = source.read_text(encoding="utf-8")
            text = text.replace(
                'reason=ERROR_REASON["HOST_UNKNOWN"]', 'reason="host_unknown"', 1
            )
            source.write_text(text, encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("inline reason string", output)

    def test_a_declared_but_never_raised_reason_fails(self):
        def mutate(root):
            source = root / "plugins" / "forge-ue-studio" / "scripts" / "forge_core.py"
            text = source.read_text(encoding="utf-8")
            text = text.replace(
                '        "USAGE": "usage",', '        "NEVER_RAISED": "never_raised",\n        "USAGE": "usage",', 1
            )
            source.write_text(text, encoding="utf-8")

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("declared but never raised", output)

    def test_fallback_diverging_from_the_catalog_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "dependencies" / "route-registry.json",
                lambda doc: doc["providers"][0].__setitem__("fallbacks", ["something-else"]),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("catalog fallback", output)


GIT_LFS_PRESENT = subprocess.run(
    ["git", "lfs", "version"], capture_output=True
).returncode == 0


class RecordingHandler(BaseHTTPRequestHandler):
    """Base for the local servers the probes actually talk to."""

    def log_message(self, *args):
        pass

    def read_request(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, ValueError):
            return {}

    def respond(self, code, payload, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LfsLockHandler(RecordingHandler):
    """The Git LFS locking API, enough of it that `git lfs lock` is a real lock."""

    locks = {}

    def do_POST(self):
        request = self.read_request()
        if self.path.endswith("/locks/verify"):
            self.respond(200, {"ours": list(self.locks.values()), "theirs": []})
        elif self.path.endswith("/unlock"):
            lock_id = self.path.rstrip("/").split("/")[-2]
            removed = self.locks.pop(lock_id, None)
            self.respond(200, {"lock": removed} if removed else {"message": "no such lock"})
        elif self.path.endswith("/locks"):
            path = request.get("path")
            held = next((lock for lock in self.locks.values() if lock["path"] == path), None)
            if held:
                self.respond(409, {"lock": held, "message": "already locked by another writer"})
                return
            lock = {
                "id": uuid.uuid4().hex[:8],
                "path": path,
                "locked_at": "2026-01-01T00:00:00Z",
                "owner": {"name": "forge-test"},
            }
            self.locks[lock["id"]] = lock
            self.respond(201, {"lock": lock})
        else:
            self.respond(404, {"message": "no route"})

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        matched = list(self.locks.values())
        if "path" in query:
            matched = [lock for lock in matched if lock["path"] in query["path"]]
        if "id" in query:
            matched = [lock for lock in matched if lock["id"] in query["id"]]
        self.respond(200, {"locks": matched})


class McpHandler(RecordingHandler):
    """An endpoint that answers an MCP initialize the way a live server does."""

    behaviour = "json"

    def do_POST(self):
        request = self.read_request()
        if self.behaviour == "http-error":
            self.respond(503, {"error": "editor busy"})
            return
        if self.behaviour == "not-mcp":
            self.respond(200, b"<html>a web server, not an MCP server</html>", content_type="text/html")
            return
        result = {
            "jsonrpc": "2.0",
            "id": request.get("id", 1),
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "unreal-mcp", "version": "5.8.0"},
            },
        }
        if self.behaviour == "sse":
            body = f"event: message\ndata: {json.dumps(result)}\n\n".encode("utf-8")
            self.respond(200, body, content_type="text/event-stream")
            return
        self.respond(200, result)


@contextmanager
def local_server(handler_class):
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class ExecutorTests(unittest.TestCase):
    """Isolation is a property of the runtime, not of an agent following instructions."""

    @contextmanager
    def game(self):
        with workspace_tempdir() as temp:
            root = temp / "MyGame"
            root.mkdir()
            forge.install_overlay(str(root), apply=True)
            for command in (
                ["git", "init", "-b", "main"],
                ["git", "config", "user.email", "forge@test.invalid"],
                ["git", "config", "user.name", "Forge Test"],
                ["git", "add", "-A"],
                ["git", "commit", "-m", "base"],
            ):
                subprocess.run(command, cwd=str(root), capture_output=True, check=True)
            yield root

    def packet(self, work_order, lane, mode="project-exclusive", write_scope=None, **isolation):
        return {
            "work_order": work_order,
            "leases": [lane],
            "write_scope": write_scope if write_scope is not None else ["project-files"],
            "isolation": {"mode": mode, "base_revision": "HEAD", **isolation},
        }

    def active_lanes(self, root):
        return [
            lease["lane"]
            for lease in forge.executor.status(root)["active"]
        ]

    def authorise(self, root, *work_orders):
        """Record the routing decision the CLI now requires before it will acquire."""
        for work_order in work_orders:
            forge.record_route_decision(
                root,
                {"schema": "forge.route-decision/v1", "canonical_work_order": work_order,
                 "leases": [], "isolation_mode": None, "tool_access_degraded": False},
                "test",
            )

    def test_two_workers_in_one_exclusive_group_cannot_both_hold(self):
        """The group is declared in leases.json; the runtime, not the workflow, enforces it."""
        with self.game() as root:
            forge.executor.acquire(root, self.packet("WO-1", "ue-live-native-mcp"), owner="worker-a", apply=True)
            with self.assertRaises(forge.executor.ExecutorError) as caught:
                forge.executor.acquire(root, self.packet("WO-2", "human-editor"), owner="worker-b", apply=True)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["LEASE_CONFLICT"])
            self.assertEqual(caught.exception.extra["conflicts"][0]["work_order"], "WO-1")
            self.assertEqual(self.active_lanes(root), ["ue-live-native-mcp"])

    def test_lanes_outside_the_group_still_run_concurrently(self):
        with self.game() as root:
            forge.executor.acquire(root, self.packet("WO-1", "ue-live-native-mcp"), owner="worker-a", apply=True)
            forge.executor.acquire(
                root,
                self.packet("WO-2", "lane.dcc-authoring", write_scope=["dcc-workspace"]),
                owner="worker-b",
                apply=True,
            )
            self.assertEqual(sorted(self.active_lanes(root)), ["lane.dcc-authoring", "ue-live-native-mcp"])

    def test_a_second_holder_of_the_same_lane_is_refused(self):
        with self.game() as root:
            forge.executor.acquire(root, self.packet("WO-1", "ue-live-python"), owner="worker-a", apply=True)
            with self.assertRaises(forge.executor.ExecutorError) as caught:
                forge.executor.acquire(root, self.packet("WO-2", "ue-live-python"), owner="worker-b", apply=True)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["LEASE_CONFLICT"])

    def test_an_expired_lease_is_recovered_rather_than_inherited(self):
        with self.game() as root:
            forge.executor.acquire(
                root, self.packet("WO-1", "ue-live-native-mcp"), owner="worker-a", apply=True, ttl_minutes=-1
            )
            result = forge.executor.acquire(
                root, self.packet("WO-2", "ue-live-native-mcp"), owner="worker-b", apply=True
            )
            self.assertEqual(len(result["recovered_stale"]), 1)
            self.assertEqual(self.active_lanes(root), ["ue-live-native-mcp"])
            self.assertEqual(forge.executor.status(root)["active"][0]["work_order"], "WO-2")

    def test_a_worktree_is_created_from_the_named_revision(self):
        with self.game() as root:
            result = forge.executor.acquire(
                root,
                self.packet("WO-1", "project-files", mode="git-worktree", branch="forge/WO-1"),
                owner="worker-a",
                apply=True,
            )
            self.assertTrue((root / result["workspace"]).is_dir())
            self.assertEqual(result["base_revision"], result["leases"][0]["isolation"]["base_revision"])

    def test_failed_isolation_leaves_no_lease_behind(self):
        """Rollback is the point: a half-entered transaction is worse than a refusal."""
        with self.game() as root:
            packet = self.packet("WO-1", "project-files", mode="git-worktree")
            packet["isolation"]["base_revision"] = "no-such-revision"
            with self.assertRaises(forge.executor.ExecutorError):
                forge.executor.acquire(root, packet, owner="worker-a", apply=True)
            self.assertEqual(self.active_lanes(root), [])

    def test_a_lock_that_cannot_be_taken_never_becomes_a_held_lease(self):
        """No LFS remote here, so the lock fails. The lease must fail with it."""
        with self.game() as root:
            packet = self.packet(
                "WO-1", "generated-assets", mode="lfs-lock", lock_targets=["Content/Maps/Main.umap"]
            )
            with self.assertRaises(forge.executor.ExecutorError) as caught:
                forge.executor.acquire(root, packet, owner="worker-a", apply=True)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["ISOLATION_FAILED"])
            self.assertEqual(self.active_lanes(root), [])

    def test_release_frees_the_lane_for_the_next_worker(self):
        with self.game() as root:
            forge.executor.acquire(root, self.packet("WO-1", "ue-live-native-mcp"), owner="worker-a", apply=True)
            forge.executor.release(root, "WO-1", outcome="passed", apply=True)
            self.assertEqual(self.active_lanes(root), [])
            forge.executor.acquire(root, self.packet("WO-2", "human-editor"), owner="worker-b", apply=True)
            self.assertEqual(self.active_lanes(root), ["human-editor"])

    def test_a_failed_outcome_discards_the_workspace_a_passed_one_keeps_it(self):
        with self.game() as root:
            kept = forge.executor.acquire(
                root, self.packet("WO-1", "project-files", mode="git-worktree"), owner="worker-a", apply=True
            )
            forge.executor.release(root, "WO-1", outcome="passed", apply=True)
            self.assertTrue((root / kept["workspace"]).is_dir())

            discarded = forge.executor.acquire(
                root,
                self.packet("WO-2", "project-files", mode="git-worktree", workspace=".forge/workspaces/WO-2"),
                owner="worker-b",
                apply=True,
            )
            forge.executor.release(root, "WO-2", outcome="failed", apply=True)
            self.assertFalse((root / discarded["workspace"]).exists())

    def test_releasing_something_never_held_is_refused(self):
        with self.game() as root:
            with self.assertRaises(forge.executor.ExecutorError) as caught:
                forge.executor.release(root, "WO-never", outcome="passed", apply=True)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["LEASE_UNKNOWN"])

    def test_a_preview_and_a_result_carry_the_same_fields(self):
        """A consumer reading a dry run must not hit a missing key on the real thing."""
        with self.game() as root:
            forge.executor.acquire(root, self.packet("WO-1", "ue-live-native-mcp"), owner="worker-a", apply=True)
            preview = forge.executor.release(root, "WO-1", outcome="passed", apply=False)
            applied = forge.executor.release(root, "WO-1", outcome="passed", apply=True)
            self.assertEqual(sorted(preview), sorted(applied))

    def test_a_dry_run_reports_the_plan_and_holds_nothing(self):
        with self.game() as root:
            result = forge.executor.acquire(
                root, self.packet("WO-1", "ue-live-native-mcp"), owner="worker-a", apply=False
            )
            self.assertEqual(result["mode"], "dry-run")
            self.assertTrue(any(step["step"] == "acquire-lease" for step in result["plan"]))
            self.assertEqual(self.active_lanes(root), [])

    def test_a_dry_run_still_reports_a_conflict_before_anything_is_taken(self):
        with self.game() as root:
            forge.executor.acquire(root, self.packet("WO-1", "ue-live-native-mcp"), owner="worker-a", apply=True)
            with self.assertRaises(forge.executor.ExecutorError) as caught:
                forge.executor.acquire(root, self.packet("WO-2", "human-editor"), owner="worker-b", apply=False)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["LEASE_CONFLICT"])

    def test_a_packet_that_mutates_without_naming_a_lease_is_refused(self):
        with self.game() as root:
            packet = self.packet("WO-1", "ue-live-native-mcp")
            packet["leases"] = []
            with self.assertRaises(forge.executor.ExecutorError) as caught:
                forge.executor.acquire(root, packet, owner="worker-a", apply=True)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["PACKET_INVALID"])

    def test_two_processes_racing_the_same_lane_produce_exactly_one_holder(self):
        """The ledger is guarded by a real mutex, so the race has one winner, not two."""
        with self.game() as root:
            self.authorise(root, "WO-A", "WO-B")
            packets = []
            for name in ("WO-A", "WO-B"):
                path = root / f"{name}.json"
                path.write_text(json.dumps(self.packet(name, "ue-live-native-mcp")), encoding="utf-8")
                packets.append(path)
            running = [
                subprocess.Popen(
                    [sys.executable, str(FORGE_PATH), "exec", "acquire", "--project", str(root),
                     "--packet", str(path), "--owner", path.stem, "--apply"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for path in packets
            ]
            results = []
            for process in running:
                _, errors = process.communicate()
                results.append((process.returncode, errors.decode("utf-8", "replace")))
            codes = sorted(code for code, _ in results)
            self.assertEqual(codes, [0, forge.EXIT_CONTRACT])
            loser = next(errors for code, errors in results if code == forge.EXIT_CONTRACT)
            self.assertEqual(json.loads(loser)["reason"], forge.ERROR_REASON["LEASE_CONFLICT"])
            self.assertEqual(self.active_lanes(root), ["ue-live-native-mcp"])


@unittest.skipUnless(GIT_LFS_PRESENT, "git-lfs is not installed on this machine")
class LfsLockTests(unittest.TestCase):
    """Binary ownership is refused by git, not by convention, so git has to be in the test."""

    def setUp(self):
        LfsLockHandler.locks = {}

    @contextmanager
    def game(self):
        with local_server(LfsLockHandler) as url:
            with workspace_tempdir() as temp:
                root = temp / "MyGame"
                root.mkdir()
                forge.install_overlay(str(root), apply=True)
                (root / "Content").mkdir()
                (root / "Content" / "Main.umap").write_bytes(b"a binary package")
                for command in (
                    ["git", "init", "-q", "-b", "main"],
                    ["git", "config", "user.email", "forge@test.invalid"],
                    ["git", "config", "user.name", "Forge Test"],
                    ["git", "config", "lfs.url", url],
                    ["git", "add", "-A"],
                    ["git", "commit", "-qm", "base"],
                ):
                    subprocess.run(command, cwd=str(root), capture_output=True, check=True)
                yield root

    def packet(self, work_order, targets):
        return {
            "work_order": work_order,
            "leases": ["generated-assets"],
            "write_scope": list(targets),
            "isolation": {"mode": "lfs-lock", "base_revision": "HEAD", "lock_targets": list(targets)},
        }

    def held_paths(self):
        return sorted(lock["path"] for lock in LfsLockHandler.locks.values())

    def test_acquiring_takes_a_real_lock_on_the_server(self):
        with self.game() as root:
            result = forge.executor.acquire(
                root, self.packet("WO-MAP", ["Content/Main.umap"]), owner="worker-a", apply=True
            )
            self.assertEqual(result["locked"], ["Content/Main.umap"])
            self.assertEqual(self.held_paths(), ["Content/Main.umap"])
            self.assertEqual(forge.executor.status(root)["active"][0]["status"], "ACTIVE")

    def test_a_lock_another_writer_holds_refuses_the_lease(self):
        """The point of a lock: refusal comes from git, across machines Forge cannot see."""
        with self.game() as root:
            LfsLockHandler.locks["other"] = {
                "id": "other",
                "path": "Content/Main.umap",
                "locked_at": "2026-01-01T00:00:00Z",
                "owner": {"name": "someone-else"},
            }
            with self.assertRaises(forge.executor.ExecutorError) as caught:
                forge.executor.acquire(
                    root, self.packet("WO-MAP", ["Content/Main.umap"]), owner="worker-a", apply=True
                )
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["ISOLATION_FAILED"])
            self.assertEqual(forge.executor.status(root)["active"], [])
            self.assertEqual(self.held_paths(), ["Content/Main.umap"])

    def test_a_partial_lock_set_is_rolled_back_completely(self):
        """The second path is already locked, so the first must not stay locked either."""
        with self.game() as root:
            (root / "Content" / "Second.umap").write_bytes(b"another package")
            LfsLockHandler.locks["other"] = {
                "id": "other",
                "path": "Content/Second.umap",
                "locked_at": "2026-01-01T00:00:00Z",
                "owner": {"name": "someone-else"},
            }
            with self.assertRaises(forge.executor.ExecutorError):
                forge.executor.acquire(
                    root,
                    self.packet("WO-MAPS", ["Content/Main.umap", "Content/Second.umap"]),
                    owner="worker-a",
                    apply=True,
                )
            self.assertEqual(self.held_paths(), ["Content/Second.umap"])
            self.assertEqual(forge.executor.status(root)["active"], [])

    def test_a_rollback_that_cannot_undo_a_lock_says_so(self):
        """Silence here would mean a lock held on the server that Forge no longer tracks."""
        with self.game() as root:
            (root / "Content" / "Second.umap").write_bytes(b"another package")
            subprocess.run(["git", "add", "-A"], cwd=str(root), capture_output=True, check=True)
            subprocess.run(["git", "commit", "-qm", "second"], cwd=str(root), capture_output=True, check=True)
            LfsLockHandler.locks["other"] = {
                "id": "other",
                "path": "Content/Second.umap",
                "locked_at": "2026-01-01T00:00:00Z",
                "owner": {"name": "someone-else"},
            }
            original = forge.executor.git

            def failing_unlock(target_root, *args, **kwargs):
                if args[:2] == ("lfs", "unlock"):
                    return subprocess.CompletedProcess(args, 1, "", "lfs server unreachable")
                return original(target_root, *args, **kwargs)

            forge.executor.git = failing_unlock
            try:
                with self.assertRaises(forge.executor.ExecutorError) as caught:
                    forge.executor.acquire(
                        root,
                        self.packet("WO-MAPS", ["Content/Main.umap", "Content/Second.umap"]),
                        owner="worker-a",
                        apply=True,
                    )
            finally:
                forge.executor.git = original
            leaked = caught.exception.extra["rollback_incomplete"]
            self.assertEqual(len(leaked), 1)
            self.assertIn("Content/Main.umap", leaked[0])
            self.assertIn("rollback_note", caught.exception.extra)
            self.assertEqual(forge.executor.status(root)["active"], [])

    def test_releasing_gives_the_lock_back(self):
        with self.game() as root:
            forge.executor.acquire(
                root, self.packet("WO-MAP", ["Content/Main.umap"]), owner="worker-a", apply=True
            )
            result = forge.executor.release(root, "WO-MAP", outcome="passed", apply=True)
            self.assertEqual(result["unlocked"], ["Content/Main.umap"])
            self.assertEqual(result["unlock_failures"], [])
            self.assertEqual(self.held_paths(), [])

    def test_a_lock_that_will_not_release_is_reported_not_swallowed(self):
        """The lane frees, the path does not. Saying so is the whole job."""
        with self.game() as root:
            forge.executor.acquire(
                root, self.packet("WO-MAP", ["Content/Main.umap"]), owner="worker-a", apply=True
            )
            LfsLockHandler.locks.clear()
            subprocess.run(
                ["git", "config", "lfs.url", "http://127.0.0.1:1"], cwd=str(root), capture_output=True, check=True
            )
            result = forge.executor.release(root, "WO-MAP", outcome="failed", apply=True)
            self.assertEqual(result["unlocked"], [])
            self.assertEqual([item["target"] for item in result["unlock_failures"]], ["Content/Main.umap"])
            self.assertIn("still held", result["note"])
            self.assertEqual(forge.executor.status(root)["active"], [])

    def test_the_lock_is_released_after_a_lease_is_freed_and_can_be_retaken(self):
        with self.game() as root:
            forge.executor.acquire(
                root, self.packet("WO-MAP", ["Content/Main.umap"]), owner="worker-a", apply=True
            )
            forge.executor.release(root, "WO-MAP", outcome="passed", apply=True)
            forge.executor.acquire(
                root, self.packet("WO-MAP-2", ["Content/Main.umap"]), owner="worker-b", apply=True
            )
            self.assertEqual(self.held_paths(), ["Content/Main.umap"])


class McpHandshakeTests(unittest.TestCase):
    """A route is verified by an answer from a running server, never by a config file."""

    def setUp(self):
        McpHandler.behaviour = "json"
        self.profile = forge.host_profile("claude")

    @contextmanager
    def game(self, url):
        with workspace_tempdir() as temp:
            root = temp / "MyGame"
            root.mkdir()
            forge.install_overlay(str(root), apply=True)
            path = root / ".forge" / "mcp.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            for entry in document["servers"]:
                if entry["id"] == "unreal-native-mcp":
                    entry["transport"] = {"type": "http", "url": f"{url}/mcp"}
            path.write_text(json.dumps(document, indent=2), encoding="utf-8")
            rendered = forge.render_project_mcp(root, self.profile, root)
            (root / ".mcp.json").write_bytes(rendered[1])
            yield root

    def route(self, root):
        return next(
            item for item in forge.mcp_status(root, self.profile)["routes"]
            if item["provider"] == "unreal-native-mcp"
        )

    def contract(self, root):
        return next(
            item for item in forge.mcp_capability_contracts(root, self.profile)
            if item["capability"] == "ue.live.typed"
        )

    def test_a_server_that_answers_initialize_is_verified(self):
        with local_server(McpHandler) as url:
            with self.game(url) as root:
                route = self.route(root)
                self.assertTrue(route["live"])
                self.assertEqual(route["status"], "AVAILABLE_VERIFIED")
                self.assertEqual(self.contract(root)["status"], "AVAILABLE_VERIFIED")
                self.assertEqual(self.contract(root)["health"], "HEALTHY")

    def test_an_event_stream_answer_is_verified_too(self):
        """The first-party server speaks HTTP and SSE, so the SSE framing must count."""
        McpHandler.behaviour = "sse"
        with local_server(McpHandler) as url:
            with self.game(url) as root:
                self.assertEqual(self.route(root)["status"], "AVAILABLE_VERIFIED")

    def test_a_server_that_errors_is_unavailable_not_verified(self):
        McpHandler.behaviour = "http-error"
        with local_server(McpHandler) as url:
            with self.game(url) as root:
                route = self.route(root)
                self.assertFalse(route["live"])
                self.assertEqual(route["status"], "UNAVAILABLE_OPTIONAL")
                self.assertEqual(self.contract(root)["health"], "UNAVAILABLE")

    def test_something_listening_that_is_not_mcp_is_not_a_route(self):
        """A port answering is not a server speaking. Only the handshake decides."""
        McpHandler.behaviour = "not-mcp"
        with local_server(McpHandler) as url:
            with self.game(url) as root:
                route = self.route(root)
                self.assertFalse(route["live"])
                self.assertEqual(route["status"], "UNAVAILABLE_OPTIONAL")

    def test_nothing_listening_leaves_the_declared_route_unavailable(self):
        with self.game("http://127.0.0.1:1") as root:
            route = self.route(root)
            self.assertFalse(route["live"])
            self.assertTrue(route["declared_in_project"])
            self.assertEqual(route["status"], "UNAVAILABLE_OPTIONAL")

    def test_a_live_server_the_host_cannot_see_is_reported_as_undeclared(self):
        with local_server(McpHandler) as url:
            with self.game(url) as root:
                (root / ".mcp.json").write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
                probe = forge.probe_mcp_server(
                    root, self.profile, "unreal-mcp", forge.mcp_providers()[0]
                )
                self.assertTrue(probe["live"])
                self.assertFalse(probe["found"])
                self.assertIn("no configuration the host reads declares it", probe["note"])


class EditorClosedRouteTests(unittest.TestCase):
    """The editor-closed API is a peer route, not the live route's fallback."""

    def setUp(self):
        self.profile = forge.host_profile("claude")
        self.row = next(row for row in forge.process_providers() if row["id"] == "unreal-python")

    @contextmanager
    def game(self, engine_present):
        with workspace_tempdir() as temp:
            root = temp / "MyGame"
            root.mkdir()
            forge.install_overlay(str(root), apply=True)
            original = os.environ.get("PATH", "")
            if engine_present:
                shim = temp / "engine"
                shim.mkdir()
                (shim / "UnrealEditor-Cmd.cmd").write_text("@echo off\r\necho stub\r\n", encoding="utf-8")
                os.environ["PATH"] = f"{shim}{os.pathsep}{original}"
            try:
                yield root
            finally:
                os.environ["PATH"] = original

    def contracts(self, root):
        return {c["capability"]: c for c in forge.mcp_capability_contracts(root, self.profile)}

    def test_it_is_a_peer_route_with_its_own_lane_and_lease(self):
        self.assertEqual(self.row["kind"], "process")
        self.assertEqual(self.row["lane"], "lane.ue-editor-closed")
        self.assertEqual(self.row["lease"], "ue-editor-closed-api")
        live = next(row for row in forge.mcp_providers() if row["id"] == "unreal-native-mcp")
        self.assertNotEqual(self.row["lane"], live["lane"], "peer routes must not share a lane")

    def test_its_capabilities_are_servable_at_all(self):
        """They were catalog-declared and route-less, so no contract could ever bind them."""
        index = forge.mcp_capability_index()
        for capability in ("ue.python.commandlet", "ue.batch"):
            self.assertIn(capability, index)
            self.assertEqual(index[capability]["id"], "unreal-python")

    def test_both_editor_lanes_sit_in_one_exclusive_group(self):
        leases = json.loads(
            (ROOT / "plugins" / "forge-ue-studio" / "assets" / "project-template" / ".forge" / "state" / "leases.json")
            .read_text(encoding="utf-8")
        )
        group = leases["exclusive_groups"]["unreal-project-super-lock"]
        live = next(row for row in forge.mcp_providers() if row["id"] == "unreal-native-mcp")
        self.assertIn(self.row["lease"], group)
        self.assertIn(live["lease"], group)

    def test_without_the_engine_command_it_is_unavailable(self):
        with self.game(engine_present=False) as root:
            probe = forge.probe_process_route(root, self.row)
            self.assertFalse(probe["found"])
            self.assertEqual(probe["status"], "UNAVAILABLE_OPTIONAL")
            self.assertIn("not on PATH", probe["reason"])

    def test_a_clear_lane_makes_it_available(self):
        with self.game(engine_present=True) as root:
            probe = forge.probe_process_route(root, self.row)
            self.assertTrue(probe["lane_clear"])
            self.assertEqual(probe["status"], "AVAILABLE_UNVERIFIED")
            self.assertEqual(self.contracts(root)["ue.python.commandlet"]["status"], "AVAILABLE_UNVERIFIED")

    def test_a_live_editor_closes_the_lane(self):
        """The inverse handshake: a commandlet must not run against a project the editor holds."""
        with local_server(McpHandler) as url:
            with self.game(engine_present=True) as root:
                path = root / ".forge" / "mcp.json"
                document = json.loads(path.read_text(encoding="utf-8"))
                for entry in document["servers"]:
                    if entry["id"] == "unreal-native-mcp":
                        entry["transport"] = {"type": "http", "url": f"{url}/mcp"}
                path.write_text(json.dumps(document, indent=2), encoding="utf-8")
                rendered = forge.render_project_mcp(root, self.profile, root)
                (root / ".mcp.json").write_bytes(rendered[1])

                probe = forge.probe_process_route(root, self.row)
                self.assertFalse(probe["lane_clear"])
                self.assertEqual(probe["status"], "UNAVAILABLE_OPTIONAL")

                contracts = self.contracts(root)
                self.assertEqual(contracts["ue.live.typed"]["status"], "AVAILABLE_VERIFIED")
                self.assertEqual(contracts["ue.python.commandlet"]["status"], "UNAVAILABLE_OPTIONAL")

    def test_the_two_editor_routes_are_never_available_together(self):
        with self.game(engine_present=True) as root:
            contracts = self.contracts(root)
            live = contracts["ue.live.typed"]["status"].startswith("AVAILABLE")
            closed = contracts["ue.python.commandlet"]["status"].startswith("AVAILABLE")
            self.assertFalse(live and closed, "one project cannot offer both editor lanes at once")


class RoutedAcquisitionTests(unittest.TestCase):
    """Routing resolves what the work needs; acquiring may not hold less than that."""

    def setUp(self):
        self.profile = forge.host_profile("claude")

    @contextmanager
    def game(self, engine_present=True):
        with workspace_tempdir() as temp:
            root = temp / "MyGame"
            root.mkdir()
            forge.install_overlay(str(root), apply=True)
            for command in (
                ["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "forge@test.invalid"],
                ["git", "config", "user.name", "Forge Test"],
                ["git", "add", "-A"],
                ["git", "commit", "-qm", "base"],
            ):
                subprocess.run(command, cwd=str(root), capture_output=True, check=True)
            (root / "request.json").write_text(
                json.dumps({
                    "work_order": "FI-UNREAL", "task_class": "engine-operation", "complexity": "medium",
                    "bounded": True, "required_capabilities": ["ue.python.commandlet"],
                    "required_lanes": ["lane.ue-editor-closed"], "mutation_risk": "project-write",
                }),
                encoding="utf-8",
            )
            original = os.environ.get("PATH", "")
            if engine_present:
                shim = temp / "engine"
                shim.mkdir()
                (shim / "UnrealEditor-Cmd.cmd").write_text("@echo off\r\necho stub\r\n", encoding="utf-8")
                os.environ["PATH"] = f"{shim}{os.pathsep}{original}"
            try:
                yield root
            finally:
                os.environ["PATH"] = original

    def decision(self, root):
        return forge.route_work(str(root), str(root / "request.json"))

    def record(self, root, **overrides):
        """Put a decision in the ledger, the way `route --apply` does."""
        decision = {**self.decision(root), **overrides}
        forge.record_route_decision(root, decision, "test")
        return decision

    def packet(self, root, name, **overrides):
        body = {
            "work_order": "FI-UNREAL",
            "leases": ["ue-editor-closed-api"],
            "write_scope": ["Content"],
            "isolation": {"mode": "project-exclusive", "base_revision": "HEAD"},
        }
        body.update(overrides)
        path = root / name
        path.write_text(json.dumps(body), encoding="utf-8")
        return path

    def test_routing_names_the_lane_lease_and_isolation_the_work_needs(self):
        with self.game() as root:
            decision = self.decision(root)
            self.assertEqual(decision["lanes"], ["lane.ue-editor-closed"])
            self.assertEqual(decision["leases"], ["ue-editor-closed-api"])
            self.assertEqual(decision["isolation_mode"], "project-exclusive")
            self.assertFalse(decision["tool_access_degraded"])
            self.assertEqual(decision["lane_warnings"], [])

    def test_routing_reads_the_live_contract_not_a_stale_snapshot(self):
        """The probe decides, so an absent engine degrades the route to its fallback."""
        with self.game(engine_present=False) as root:
            decision = self.decision(root)
            self.assertTrue(decision["tool_access_degraded"])
            self.assertEqual(decision["leases"], [])
            self.assertEqual(
                decision["degraded_capabilities"][0]["take_fallback"], ["ue.native-mcp-or-cpp-uat"]
            )
            self.assertIn("no bound route serves", decision["lane_warnings"][0])

    def test_a_capability_no_route_serves_resolves_to_the_resident(self):
        with self.game() as root:
            contracts = {c["capability"]: c for c in forge.mcp_capability_contracts(root, self.profile)}
            resolved = forge.resolve_tool_access(contracts, {"ue.build"})[0]
            self.assertFalse(resolved["routed"])
            self.assertTrue(resolved["bound"])
            self.assertEqual(resolved["provider"], forge.RESIDENT_PROVIDER)

    def test_a_packet_missing_the_lease_routing_requires_is_refused(self):
        with self.game() as root:
            decision = self.decision(root)
            packet = json.loads(self.packet(root, "p.json", leases=[]).read_text(encoding="utf-8"))
            conflicts = forge.route_conflicts(packet, decision)
            self.assertTrue(any("does not declare" in item for item in conflicts))

    def test_a_packet_weaker_than_routing_requires_is_refused(self):
        with self.game() as root:
            decision = self.decision(root)
            packet = json.loads(
                self.packet(root, "p.json", isolation={"mode": "git-worktree", "base_revision": "HEAD"})
                .read_text(encoding="utf-8")
            )
            conflicts = forge.route_conflicts(packet, decision)
            self.assertTrue(any("weaker" in item for item in conflicts))

    def test_a_degraded_route_refuses_acquisition_rather_than_taking_the_lane(self):
        with self.game(engine_present=False) as root:
            decision = self.decision(root)
            packet = json.loads(self.packet(root, "p.json").read_text(encoding="utf-8"))
            conflicts = forge.route_conflicts(packet, decision)
            self.assertTrue(any("degraded" in item for item in conflicts))

    def test_exec_acquire_refuses_the_mismatch_through_the_cli(self):
        with self.game() as root:
            route_path = root / "route.json"
            route_path.write_text(json.dumps(self.decision(root)), encoding="utf-8")
            packet_path = self.packet(root, "under.json", leases=[])
            with self.assertRaises(forge.ForgeExit) as caught:
                forge.execute_acquire(str(root), str(packet_path), None, apply=True, route_value=str(route_path))
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["ROUTE_PACKET_MISMATCH"])
            self.assertEqual(forge.executor.status(root)["active"], [])

    def test_a_packet_that_matches_routing_acquires(self):
        with self.game() as root:
            route_path = root / "route.json"
            route_path.write_text(json.dumps(self.decision(root)), encoding="utf-8")
            packet_path = self.packet(root, "ok.json")
            result = forge.execute_acquire(
                str(root), str(packet_path), None, apply=True, route_value=str(route_path)
            )
            self.assertEqual(result["leases"][0]["lane"], "ue-editor-closed-api")
            self.assertEqual(result["route"], str(route_path))

    def test_a_lease_in_no_exclusive_group_is_reported_not_silent(self):
        """A typo'd lane still leases, but it protects nothing, so it must be visible."""
        with self.game() as root:
            self.record(root, leases=["ue-editor-closed-api-typo"])
            packet_path = self.packet(root, "typo.json", leases=["ue-editor-closed-api-typo"])
            preview = forge.execute_acquire(str(root), str(packet_path), None, apply=False)
            self.assertEqual(preview["ungrouped_lanes"], ["ue-editor-closed-api-typo"])
            self.assertIn("no exclusive group", preview["ungrouped_note"])

    def test_a_known_lane_names_the_group_it_joined(self):
        with self.game() as root:
            self.record(root)
            result = forge.execute_acquire(str(root), str(self.packet(root, "ok.json")), None, apply=True)
            self.assertEqual(result["leases"][0]["exclusive_group"], "unreal-project-super-lock")
            self.assertEqual(result["ungrouped_lanes"], [])
            status = forge.executor.status(root)
            self.assertEqual(status["lane_groups"]["ue-editor-closed-api"], "unreal-project-super-lock")

    def test_a_packet_no_decision_covers_is_refused_and_changes_nothing(self):
        """The seam the review named: an unrouted packet used to be taken on trust."""
        with self.game() as root:
            ledger = forge.executor.lease_state_path(root)
            before = ledger.read_bytes()
            with self.assertRaises(forge.ForgeExit) as caught:
                forge.execute_acquire(str(root), str(self.packet(root, "ok.json")), None, apply=True)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["ROUTE_DECISION_MISSING"])
            self.assertEqual(forge.executor.status(root)["active"], [])
            self.assertEqual(ledger.read_bytes(), before)

    def test_the_recorded_decision_authorises_acquisition_with_no_flag(self):
        with self.game() as root:
            self.record(root)
            result = forge.execute_acquire(str(root), str(self.packet(root, "ok.json")), None, apply=True)
            self.assertEqual(result["leases"][0]["lane"], "ue-editor-closed-api")
            self.assertEqual(result["route"], str(forge.route_decisions_path(root)))
            self.assertTrue(result["route_recorded_at"])

    def test_a_recorded_decision_still_refuses_a_packet_holding_less(self):
        """Reading the decision instead of being handed it does not relax the check."""
        with self.game() as root:
            self.record(root)
            with self.assertRaises(forge.ForgeExit) as caught:
                forge.execute_acquire(str(root), str(self.packet(root, "under.json", leases=[])), None, apply=True)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["ROUTE_PACKET_MISMATCH"])
            self.assertEqual(forge.executor.status(root)["active"], [])

    def test_a_decision_the_environment_has_outlived_is_refused(self):
        """The two Unreal routes swap as the editor opens, so an old decision names a lane that may protect nothing."""
        with self.game() as root:
            self.record(root)
            document = forge.read_route_decisions(root)
            document["decisions"][0]["recorded_at"] = "2000-01-01T00:00:00+00:00"
            forge.executor.write_state_atomically(forge.route_decisions_path(root), document)
            with self.assertRaises(forge.ForgeExit) as caught:
                forge.execute_acquire(str(root), str(self.packet(root, "ok.json")), None, apply=True)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["ROUTE_DECISION_STALE"])
            self.assertEqual(forge.executor.status(root)["active"], [])

    def test_route_records_only_on_apply(self):
        with self.game() as root:
            argv = ["route", "--project", str(root), "--request", str(root / "request.json")]
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                forge.main(argv)
            self.assertEqual(forge.read_route_decisions(root)["decisions"], [])
            self.assertFalse(json.loads(stream.getvalue())["recorded"])
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                forge.main([*argv, "--apply"])
            recorded = forge.read_route_decisions(root)["decisions"]
            self.assertEqual([item["canonical_work_order"] for item in recorded], ["FI-UNREAL"])
            self.assertTrue(json.loads(stream.getvalue())["recorded"])

    def test_re_routing_replaces_the_decision_rather_than_appending(self):
        with self.game() as root:
            self.record(root)
            self.record(root)
            self.assertEqual(len(forge.read_route_decisions(root)["decisions"]), 1)

    def test_a_packet_naming_an_alias_finds_the_canonical_decision(self):
        """Aliases are display compatibility, so they must not split the decision from the packet."""
        with self.game() as root:
            registry_path = root / ".forge" / "state" / "packet-registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["aliases"] = list(registry.get("aliases", [])) + [
                {"alias": "FI-UNREAL-LEGACY", "canonical": "FI-UNREAL"}
            ]
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            self.record(root)
            packet_path = self.packet(root, "alias.json", work_order="FI-UNREAL-LEGACY")
            result = forge.execute_acquire(str(root), str(packet_path), None, apply=True)
            self.assertEqual(result["leases"][0]["lane"], "ue-editor-closed-api")

    def test_an_override_decision_still_wins_over_the_ledger(self):
        with self.game() as root:
            self.record(root)
            route_path = root / "route.json"
            route_path.write_text(json.dumps(self.decision(root)), encoding="utf-8")
            result = forge.execute_acquire(
                str(root), str(self.packet(root, "ok.json")), None, apply=True, route_value=str(route_path)
            )
            self.assertEqual(result["route"], str(route_path))
            self.assertIsNone(result["route_recorded_at"])

    def test_a_project_local_route_must_spell_its_lane_as_a_lane(self):
        with self.game() as root:
            path = root / ".forge" / "mcp.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["servers"] = [{
                "id": "some-tool", "enabled": True, "transport": {"command": "node"},
                "server": "some-tool", "capabilities": ["audio.mix"], "lane": "audio-authoring",
                "isolation_mode": "git-worktree", "fallbacks": ["human-audio-pass"],
            }]
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(forge.ForgeExit) as caught:
                forge.resolve_project_servers(root)
            self.assertEqual(caught.exception.reason, forge.ERROR_REASON["MCP_INCOMPLETE_DECLARATION"])
            document["servers"][0]["lane"] = "lane.audio-authoring"
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertEqual(forge.resolve_project_servers(root)[0]["lane"], "lane.audio-authoring")


class ProfileStabilityTests(unittest.TestCase):
    """The detected profile describes the machine, so how the path was typed cannot change it."""

    @contextmanager
    def game(self):
        with workspace_tempdir() as temp:
            root = temp / "MyGame"
            root.mkdir()
            forge.install_overlay(str(root), apply=True)
            yield root

    def test_re_profiling_the_same_machine_proposes_nothing(self):
        with self.game() as root:
            for spelling in (str(root), str(root) + "/", "."):
                original = Path.cwd()
                os.chdir(root)
                try:
                    result = forge.write_profile(spelling, apply=True)
                finally:
                    os.chdir(original)
                self.assertEqual(result["action"], "unchanged", f"{spelling!r} proposed a change")
            proposals = list((root / ".forge" / "capabilities").glob("*.forge-proposed"))
            self.assertEqual(proposals, [], "re-profiling wrote a proposal a human must resolve")

    def test_the_invocation_record_is_kept_but_never_compared(self):
        """`requested` stays in the file as provenance; it just cannot cause a proposal."""
        with self.game() as root:
            detected = json.loads((root / ".forge" / "capabilities" / "detected.json").read_text(encoding="utf-8"))
            self.assertIn("requested", detected["project"])
            widened = json.loads(json.dumps(detected))
            widened["project"]["requested"] = "somewhere/else"
            widened["snapshot"]["project"]["requested"] = "somewhere/else"
            self.assertEqual(forge.stable_profile(detected), forge.stable_profile(widened))

    def test_a_real_capability_change_still_proposes(self):
        """Stripping the invocation must not blind the comparison to the machine."""
        with self.game() as root:
            detected = json.loads((root / ".forge" / "capabilities" / "detected.json").read_text(encoding="utf-8"))
            changed = json.loads(json.dumps(detected))
            changed["providers"] = []
            self.assertNotEqual(forge.stable_profile(detected), forge.stable_profile(changed))


class CommandSurfaceTests(unittest.TestCase):
    """Every verb the parser declares is dispatched at least once, through main, so a
    payload that violates the result contract cannot reach a user unexercised."""

    @classmethod
    def leaf_commands(cls):
        found = set()

        def walk(parser, prefix=""):
            for action in parser._actions:
                if action.__class__.__name__ != "_SubParsersAction":
                    continue
                for name, sub in action.choices.items():
                    path = f"{prefix} {name}".strip()
                    nested = [a for a in sub._actions if a.__class__.__name__ == "_SubParsersAction"]
                    if nested:
                        walk(sub, path)
                    else:
                        found.add(path)

        walk(forge.build_parser())
        return found

    @contextmanager
    def game(self):
        with workspace_tempdir() as temp:
            root = temp / "MyGame"
            root.mkdir()
            forge.install_overlay(str(root), apply=True)
            for command in (
                ["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "forge@test.invalid"],
                ["git", "config", "user.name", "Forge Test"],
                ["git", "add", "-A"],
                ["git", "commit", "-qm", "base"],
            ):
                subprocess.run(command, cwd=str(root), capture_output=True, check=True)
            (root / "request.json").write_text(
                json.dumps({
                    "work_order": "FI-HOST", "task_class": "research", "complexity": "low",
                    "bounded": True, "required_capabilities": [], "required_lanes": [],
                    "mutation_risk": "read-only",
                }),
                encoding="utf-8",
            )
            (root / "packet.json").write_text(
                json.dumps({
                    "work_order": "WO-SURFACE", "leases": ["ue-live-native-mcp"],
                    "write_scope": ["project-files"],
                    "isolation": {"mode": "project-exclusive", "base_revision": "HEAD"},
                }),
                encoding="utf-8",
            )
            forge.record_route_decision(
                root,
                {"schema": "forge.route-decision/v1", "canonical_work_order": "WO-SURFACE",
                 "leases": [], "isolation_mode": None, "tool_access_degraded": False},
                "surface-test",
            )
            yield root

    def invocations(self, root):
        project = ["--project", str(root)]
        return {
            "survey": ["survey", *project],
            "install": ["install", *project],
            "verify": ["verify", *project],
            "profile": ["profile", *project],
            "next": ["next", *project],
            "bootstrap-check": ["bootstrap-check", *project],
            "gsd-sync": ["gsd-sync", *project],
            "mcp-status": ["mcp-status", *project],
            "route-status": ["route-status", *project],
            "lifecycle": ["lifecycle", *project],
            "route": ["route", *project, "--request", str(root / "request.json")],
            "validate": ["validate", "--kind", "lane-lease", "--input", str(root / ".forge" / "state" / "leases.json")],
            "host list": ["host", "list"],
            "host status": ["host", "status", *project],
            "host set": ["host", "set", *project, "--host", "claude"],
            "mcp add": ["mcp", "add", *project, "--id", "blender-gateway", "--command", "uvx"],
            "mcp remove": ["mcp", "remove", *project, "--id", "unreal-native-mcp"],
            "mcp enable": ["mcp", "enable", *project, "--id", "unreal-native-mcp"],
            "mcp disable": ["mcp", "disable", *project, "--id", "unreal-native-mcp"],
            "mcp sync-user": ["mcp", "sync-user", *project],
            "exec acquire": ["exec", "acquire", *project, "--packet", str(root / "packet.json")],
            "exec status": ["exec", "status", *project],
            "exec release": ["exec", "release", *project, "--work-order", "WO-SURFACE", "--outcome", "passed"],
        }

    def run_command(self, argv):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = forge.main(argv)
        return code, stream.getvalue()

    def test_every_declared_command_is_exercised(self):
        """A new verb with no invocation here is a verb nothing ever ran."""
        self.assertEqual(sorted(self.leaf_commands() - set(self.invocations(Path(".")))), [])

    def test_every_command_answers_with_an_identified_payload(self):
        with self.game() as root:
            for name, argv in sorted(self.invocations(root).items()):
                if name == "exec release":
                    forge.executor.acquire(
                        root, json.loads((root / "packet.json").read_text(encoding="utf-8")),
                        owner="surface-test", apply=True,
                    )
                with self.subTest(command=name):
                    code, out = self.run_command(argv)
                    self.assertIn(code, {forge.EXIT_OK, forge.EXIT_CONTRACT}, f"{name} exited {code}: {out}")
                    payload = json.loads(out)
                    self.assertIn("schema", payload, f"{name} returned a payload with no schema identity")

    def test_a_read_only_invocation_stays_a_preview(self):
        """None of the above may write without --apply, or the surface sweep is destructive."""
        with self.game() as root:
            before = {p: p.read_bytes() for p in sorted((root / ".forge").rglob("*")) if p.is_file()}
            for name, argv in sorted(self.invocations(root).items()):
                if name.startswith("exec"):
                    continue
                self.run_command(argv)
            after = {p: p.read_bytes() for p in sorted((root / ".forge").rglob("*")) if p.is_file()}
            self.assertEqual(sorted(before), sorted(after), "a preview created or removed a file")
            self.assertEqual([p.name for p in before if before[p] != after[p]], [])


class ModuleBoundaryTests(unittest.TestCase):
    """The split holds: every reference resolves, the layering stays acyclic, and
    the command line still names the whole public surface."""

    def loaded(self):
        return {path.stem: sys.modules[path.stem] for path in MODULE_PATHS if path.stem in sys.modules}

    def public_names(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        return {name for name in names if not name.startswith("_")}

    def imported_modules(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("forge"):
                found.add(node.module)
            elif isinstance(node, ast.Import):
                found |= {alias.name for alias in node.names if alias.name.startswith("forge")}
        return found

    def test_every_name_a_module_references_is_defined_or_imported(self):
        """Catches a reference the split left behind before a rare path raises NameError."""
        modules = self.loaded()
        self.assertIn("forge_core", modules, "modules did not load; the rest would assert over nothing")
        for name, module in sorted(modules.items()):
            path = SCRIPTS_DIR / f"{name}.py"
            table = symtable.symtable(path.read_text(encoding="utf-8"), str(path), "exec")
            missing = set()
            pending = [table]
            while pending:
                scope = pending.pop()
                for symbol in scope.get_symbols():
                    if symbol.is_global() and not symbol.is_assigned():
                        symbol_name = symbol.get_name()
                        if not hasattr(module, symbol_name) and not hasattr(builtins, symbol_name):
                            missing.add(symbol_name)
                pending.extend(scope.get_children())
            self.assertEqual(sorted(missing), [], f"{name}.py references names it never defines or imports")

    def test_the_module_layering_is_acyclic(self):
        graph = {path.stem: self.imported_modules(path) for path in MODULE_PATHS}
        for start in sorted(graph):
            seen, pending = set(), [start]
            while pending:
                current = pending.pop()
                for nxt in graph.get(current, set()):
                    self.assertNotEqual(nxt, start, f"import cycle reaches {start} again through {current}")
                    if nxt not in seen:
                        seen.add(nxt)
                        pending.append(nxt)

    def test_the_command_line_names_every_public_verb(self):
        """`forge.X` has to keep resolving, so the split cannot quietly drop a name."""
        for path in MODULE_PATHS:
            if path.stem in {"forge", "forge_executor"}:
                continue
            for name in sorted(self.public_names(path)):
                self.assertTrue(hasattr(forge, name), f"forge.py does not re-export {name} from {path.name}")

    def test_no_module_imports_the_command_line(self):
        """forge.py is the entry point; nothing underneath may depend on it."""
        for path in MODULE_PATHS:
            if path.stem == "forge":
                continue
            self.assertNotIn("forge", {m for m in self.imported_modules(path) if m == "forge"},
                             f"{path.name} imports the CLI it is supposed to sit below")

    def test_the_executor_stays_independent_of_the_rest(self):
        """It is the transactional core; a dependency on the CLI layers would undo that."""
        self.assertEqual(self.imported_modules(EXECUTOR_PATH), set())


if __name__ == "__main__":
    unittest.main()
