from __future__ import annotations

import ast
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FORGE_PATH = ROOT / "plugins" / "forge-ue-studio" / "scripts" / "forge.py"
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
            # Detection must never imply the resident seat.
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
            # Canon is host-neutral; surfaces are rendered for the assigned host.
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

            # Canonical state that must survive any swap.
            (project / ".planning").mkdir()
            (project / ".planning" / "STATE.md").write_text("phase 3\n", encoding="utf-8")
            packets = (project / ".forge" / "state" / "packet-registry.json").read_bytes()
            directives = (project / ".forge" / "directives.md").read_bytes()

            result = forge.host_set(str(project), "codex", apply=True)
            self.assertTrue(result["swapped"])
            self.assertEqual(result["previous_host"], "claude")

            # Incoming host surfaces exist in the right format.
            self.assertTrue((project / "AGENTS.md").is_file())
            self.assertTrue((project / ".codex" / "agents" / "studio-director.toml").is_file())
            toml_text = (project / ".codex" / "agents" / "studio-director.toml").read_text(encoding="utf-8")
            self.assertIn("developer_instructions = ", toml_text)
            self.assertIn("$forge-plan-convergence", toml_text)

            # Outgoing host surfaces are fully retired.
            self.assertFalse((project / "CLAUDE.md").exists())
            self.assertFalse((project / ".claude").exists())

            # Canon is untouched.
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

            # Evidence from another host must not grant a route under the active host.
            result = forge.route_work(str(project), str(request_path))
            self.assertEqual(result["selected"], "resident")
            self.assertEqual(result["resident_host"], "claude")
            candidate = next(item for item in result["candidates"] if item["provider"] == "ollama:m")
            self.assertFalse(candidate["eligible"])
            self.assertIn("re-probe", candidate["reason"])

            # The same evidence recorded under the active host is accepted.
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
                # Derived from canon so adding an agent definition cannot leave
                # this assertion behind asserting a stale count.
                self.assertEqual(len(agents), len(forge.agent_definitions(forge.template_root())))
                self.assertTrue(forge.verify_overlay(str(project), host_id)["ok"])
                # No unresolved canon tokens may survive rendering.
                for path in [project / surface["instruction_file"], *agents]:
                    self.assertNotIn("{{", path.read_text(encoding="utf-8"), str(path))

    def test_canon_never_carries_a_host_specific_spelling(self):
        banned = validate_repo.neutrality_banned_tokens(HOSTS)
        self.assertIn("codex", banned)
        self.assertIn("claude", banned)
        # The generic placeholder host contributes no tokens; its identifiers are
        # ordinary words that would produce false positives.
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
        # The guard is only worth having if it actually fails on a leak.
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
        # Path segments and the OpenAI-compatible protocol name are not leaks.
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
        # These checks are Forge's own domain. GSD owns phase state and has no
        # equivalent, so nothing downstream catches them if this gate does not.
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

            # A rendered instruction file that lost the phase contract must block,
            # because it is what constrains the next session.
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

            # A report that is closable but omits canonical jobs must not pass.
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
            # Advisory only: the routed action is still GSD's, unchanged.
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
        # A GSD command must never reach the user; it becomes the Forge verb
        # fronting it, spelled for the active host.
        self.assertEqual(forge.normalize_gsd_command("gsd-execute-phase", claude), "/forge-execute-phase")
        self.assertEqual(forge.normalize_gsd_command("gsd-execute-phase", codex), "$forge-execute-phase")
        self.assertEqual(forge.normalize_gsd_command("/gsd:progress --next", claude), "/forge-progress --next")
        self.assertEqual(forge.normalize_gsd_command("$gsd-onboard", claude), "/forge-onboard")
        # Forge verbs pass through, re-spelled only.
        self.assertEqual(forge.normalize_gsd_command("forge-next", codex), "$forge-next")
        # Unmapped GSD verbs fail loudly rather than leaking silently.
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
            self.assertEqual(commands, ["/forge-execute-phase 2", "/forge-verify-work", "/forge-onboard"])
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
            # Deliberate exclusions never appear as actions the user cannot run,
            # and are never emitted as UNMAPPED leaks.
            self.assertEqual([a["command"] for a in result["actions"]], ["/forge-execute-phase"])
            self.assertEqual(len(result["suppressed_actions"]), 2)
            for item in result["suppressed_actions"]:
                self.assertTrue(item["reason"])
            self.assertNotIn("UNMAPPED", json.dumps(result))

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
            # A fallback Forge verb, never an empty list.
            self.assertTrue(result["actions"])
            self.assertIsNotNone(result["recommended"])
            self.assertEqual(result["actions"][0]["command"], "/forge-progress")

    def test_planning_helpers_are_fronted_not_orphaned(self):
        # These reach real GSD capability a game project needs. Leaving them
        # unclassified would strand parts of GSD's own chain:
        #   plan-milestone-gaps closes the loop from forge-milestone --audit
        #   analyze-dependencies feeds Forge's lane leases
        #   the discussion variants are modes forge-discuss-phase must offer
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

    def test_every_command_smart_entry_can_emit_is_classified(self):
        # Anything smart-entry can recommend must be fronted or explicitly
        # dropped; an unclassified command would leak as UNMAPPED at runtime.
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

            # GSD has not created .planning yet, so the sync defers rather than failing.
            self.assertEqual(forge.sync_gsd_runtime(project, forge.host_profile("claude"), True)["action"], "deferred")

            config = project / ".planning" / "config.json"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(json.dumps({"runtime": "claude", "other": "preserved"}), encoding="utf-8")

            # Swapping the host must re-point GSD's own command spelling.
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

            # The generic host has no GSD identifier; skip rather than write junk.
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
        self.registry = forge.mcp_registry()
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
        text = (ROOT / "plugins" / "forge-ue-studio" / "dependencies" / "mcp-registry.json").read_text(encoding="utf-8")
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
        """The scope distinction is the whole point: present for the session,
        absent for anything it spawns."""
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

    def test_a_new_project_starts_with_an_amendable_declaration(self):
        with self.game() as root:
            self.assertTrue((root / ".forge" / "mcp.json").is_file())
            self.assertEqual(forge.resolve_project_servers(root), [])

    def test_declared_server_reaches_the_session_surface(self):
        with self.game() as root:
            forge.mcp_amend(root, self.profile, "add", "unreal-native-mcp", apply=True, command="uvx", args=["unreal-mcp"])
            surface = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
            self.assertIn("unreal-mcp", surface["mcpServers"])
            self.assertEqual(surface["mcpServers"]["unreal-mcp"]["command"], "uvx")

    def test_a_catalog_entry_inherits_its_routing_fields(self):
        with self.game() as root:
            forge.mcp_amend(root, self.profile, "add", "unreal-native-mcp", apply=True, command="uvx")
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
            forge.mcp_amend(root, self.profile, "add", "unreal-native-mcp", apply=True, command="uvx")
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
            forge.mcp_amend(root, self.profile, "add", "unreal-native-mcp", apply=True, command="uvx")
            forge.mcp_amend(root, self.profile, "add", "blender-gateway", apply=True, command="uvx")
            forge.mcp_amend(root, self.profile, "disable", "blender-gateway", apply=True)
            servers = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
            self.assertIn("unreal-mcp", servers)
            self.assertNotIn("blender-mcp", servers)

    def test_dry_run_amend_writes_nothing(self):
        with self.game() as root:
            before = (root / ".forge" / "mcp.json").read_text(encoding="utf-8")
            result = forge.mcp_amend(root, self.profile, "add", "unreal-native-mcp", apply=False, command="uvx")
            self.assertEqual(result["mode"], "dry-run")
            self.assertEqual((root / ".forge" / "mcp.json").read_text(encoding="utf-8"), before)
            self.assertFalse((root / ".mcp.json").exists())

    def test_status_reports_session_visibility_from_the_project(self):
        with self.game() as root:
            forge.mcp_amend(root, self.profile, "add", "unreal-native-mcp", apply=True, command="uvx")
            status = forge.mcp_status(root, self.profile)
            route = next(item for item in status["routes"] if item["provider"] == "unreal-native-mcp")
            self.assertTrue(route["declared_in_project"])
            self.assertTrue(route["rendered_to_host"])
            self.assertTrue(route["session_visible"])
            self.assertFalse(route["subagent_visible"])

    def test_the_project_surface_is_tracked_like_every_other_rendered_surface(self):
        """Hand-editing the surface is reported as a variant, as for any rendered
        file. The consequence that matters — the session no longer seeing a
        declared server — is reported by status, which probes rather than diffs."""
        with self.game() as root:
            forge.mcp_amend(root, self.profile, "add", "unreal-native-mcp", apply=True, command="uvx")
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
            forge.mcp_amend(root, self.profile, "add", "unreal-native-mcp", apply=True, command="uvx")
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
        """A reason nothing raises is vocabulary nobody can act on."""
        source = FORGE_PATH.read_text(encoding="utf-8")
        declared = set(forge.ERROR_REASON)
        # UNKNOWN is the fallback for an untyped bug reaching main().
        used = {key for key in declared if f'ERROR_REASON["{key}"]' in source}
        self.assertEqual(sorted(declared - used), [])

    def test_no_declared_failure_still_raises_a_bare_value_error(self):
        """ValueError reaching main() means a bug, so the CLI must not raise one
        as a normal outcome. The single permitted site guards the enum itself."""
        source = FORGE_PATH.read_text(encoding="utf-8")
        sites = re.findall(r"raise ValueError\(", source)
        self.assertEqual(len(sites), 1, "only the ERROR_REASON self-check may raise ValueError")

    def test_logic_never_calls_sys_exit(self):
        """Exit code resolution belongs to main(), so an importer of this module
        gets an exception rather than a process that disappears.

        Checked structurally: a textual scan would match the prose explaining
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
        """A declared verdict verb that no invocation can produce is a rule
        guarding nothing."""
        self.assertTrue(forge.VERDICT_COMMANDS)
        source = FORGE_PATH.read_text(encoding="utf-8")
        for command in sorted(forge.VERDICT_COMMANDS):
            head = command.split()[0]
            self.assertIn(f'"{head}"', source, command)

    def _payloads(self, root):
        """Every result the CLI can emit, produced in-process.

        Deliberately not seven subprocesses: a spawned CLI re-runs live host
        probes, which turns a contract assertion into a multi-minute wait and
        makes the suite flaky on whatever happens to be installed."""
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
        """Neither list is authoritative alone; a drift between them is the bug."""
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
        # The default that made a missing verdict look like success is gone.
        self.assertNotIn('result.get("ok", True) else EXIT_CONTRACT\n    except', source)


class ActionSurfaceTests(unittest.TestCase):
    """Forge owns the whole user-facing vocabulary, ids included."""

    def test_no_routed_action_id_carries_a_gsd_prefix(self):
        """The command is translated at dispatch, but an id is displayed too.
        A `gsd-` id is the same leak by a quieter route."""
        source = (ROOT / "plugins" / "forge-ue-studio" / "scripts" / "forge.py").read_text(encoding="utf-8")
        ids = re.findall(r"forge_action\(\s*\"([^\"]+)\"", source)
        self.assertTrue(ids, "no forge_action ids found; the guard would assert over nothing")
        self.assertEqual([item for item in ids if item.startswith("gsd-")], [])

    def test_every_routed_action_id_is_unique_per_situation(self):
        source = (ROOT / "plugins" / "forge-ue-studio" / "scripts" / "forge.py").read_text(encoding="utf-8")
        for block in re.findall(r"actions\s*=\s*\[(.*?)\n\s*\]", source, re.DOTALL):
            ids = re.findall(r"forge_action\(\s*\"([^\"]+)\"", block)
            self.assertEqual(len(ids), len(set(ids)), f"duplicate action id in block: {ids}")


class UserScopeMcpTests(unittest.TestCase):
    """Publishing to user scope is a machine-wide external write: planned by
    default, consented when applied, and never destructive to what it finds."""

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
        file, so no test can ever write the developer's real config."""
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
            forge.mcp_amend(root, profile, "add", "unreal-native-mcp", apply=True, command="uvx", scope="project")
            plan = forge.sync_user_mcp(root, profile, apply=False)
            self.assertEqual(plan["wanted"], [])
            self.assertEqual(plan["planned"], [])
            self.assertFalse(user_file.exists())

    def test_user_scope_only_stays_out_of_the_project_surface(self):
        with self.game() as (root, profile, _):
            forge.mcp_amend(root, profile, "add", "unreal-native-mcp", apply=True, command="uvx", scope="user")
            self.assertIsNone(forge.render_project_mcp(root, profile, root))

    def test_both_reaches_each_surface(self):
        with self.game() as (root, profile, user_file):
            forge.mcp_amend(root, profile, "add", "unreal-native-mcp", apply=True, command="uvx", scope="both")
            project = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
            self.assertIn("unreal-mcp", project["mcpServers"])
            forge.sync_user_mcp(root, profile, apply=True)
            self.assertIn("unreal-mcp", json.loads(user_file.read_text(encoding="utf-8"))["mcpServers"])

    def test_sync_is_a_plan_until_asked(self):
        with self.game() as (root, profile, user_file):
            forge.mcp_amend(root, profile, "add", "unreal-native-mcp", apply=True, command="uvx", scope="user")
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
            forge.mcp_amend(root, profile, "add", "unreal-native-mcp", apply=True, command="uvx", scope="user")
            forge.sync_user_mcp(root, profile, apply=True)
            after = json.loads(user_file.read_text(encoding="utf-8"))
            self.assertEqual(after["numStartups"], 42)
            self.assertEqual(after["projects"], {"/elsewhere": {"history": ["a", "b"]}})
            self.assertIn("someone-elses", after["mcpServers"])
            self.assertIn("unreal-mcp", after["mcpServers"])

    def test_applying_backs_up_and_records_consent(self):
        with self.game() as (root, profile, user_file):
            user_file.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
            forge.mcp_amend(root, profile, "add", "unreal-native-mcp", apply=True, command="uvx", scope="user")
            result = forge.sync_user_mcp(root, profile, apply=True)
            self.assertTrue(Path(result["backup"]).is_file())
            ledger = json.loads((root / ".forge" / "capabilities" / "consent-ledger.json").read_text(encoding="utf-8"))
            self.assertTrue(any(e["scope"] == "mcp.user-scope-write" for e in ledger["entries"]))

    def test_withdrawing_reclaims_only_an_unmodified_entry(self):
        with self.game() as (root, profile, user_file):
            forge.mcp_amend(root, profile, "add", "unreal-native-mcp", apply=True, command="uvx", scope="user")
            forge.sync_user_mcp(root, profile, apply=True)
            forge.mcp_amend(root, profile, "disable", "unreal-native-mcp", apply=True)
            forge.sync_user_mcp(root, profile, apply=True)
            self.assertNotIn("unreal-mcp", json.loads(user_file.read_text(encoding="utf-8"))["mcpServers"])

    def test_a_hand_edited_entry_is_reported_not_reclaimed(self):
        with self.game() as (root, profile, user_file):
            forge.mcp_amend(root, profile, "add", "unreal-native-mcp", apply=True, command="uvx", scope="user")
            forge.sync_user_mcp(root, profile, apply=True)
            document = json.loads(user_file.read_text(encoding="utf-8"))
            document["mcpServers"]["unreal-mcp"] = {"command": "my-own-wrapper"}
            user_file.write_text(json.dumps(document), encoding="utf-8")
            forge.mcp_amend(root, profile, "disable", "unreal-native-mcp", apply=True)
            plan = forge.sync_user_mcp(root, profile, apply=False)
            retained = [c for c in plan["planned"] if c["action"] == "retain-modified"]
            self.assertEqual([c["server"] for c in retained], ["unreal-mcp"])
            forge.sync_user_mcp(root, profile, apply=True)
            after = json.loads(user_file.read_text(encoding="utf-8"))
            self.assertEqual(after["mcpServers"]["unreal-mcp"], {"command": "my-own-wrapper"})

    def test_an_unparseable_config_is_never_rewritten(self):
        with self.game() as (root, profile, user_file):
            user_file.write_text("{ this is not json", encoding="utf-8")
            forge.mcp_amend(root, profile, "add", "unreal-native-mcp", apply=True, command="uvx", scope="user")
            result = forge.sync_user_mcp(root, profile, apply=True)
            self.assertEqual(result["mode"], "blocked")
            self.assertFalse(result["applied"])
            self.assertEqual(user_file.read_text(encoding="utf-8"), "{ this is not json")

    def test_a_host_forge_may_not_write_reports_instead(self):
        with self.game(host="codex") as (root, profile, _):
            forge.mcp_amend(root, profile, "add", "unreal-native-mcp", apply=True, command="uvx", scope="user")
            result = forge.sync_user_mcp(root, profile, apply=True)
            self.assertEqual(result["mode"], "report-only")
            self.assertFalse(result["applied"])
            self.assertEqual([c["action"] for c in result["planned"]], ["declare-by-hand"])


class McpGateTests(unittest.TestCase):
    """The validator gates must actually fire. A guard that cannot fail is not a guard."""

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
                root / "plugins" / "forge-ue-studio" / "dependencies" / "mcp-registry.json",
                lambda doc: doc["providers"][0].__setitem__("id", "not-a-dependency"),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("not a declared dependency", output)

    def test_undeclared_lane_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "dependencies" / "mcp-registry.json",
                lambda doc: doc["providers"][0].__setitem__("lane", "ue.imaginary"),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("undeclared lane", output)

    def test_unknown_acceptance_suite_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "dependencies" / "mcp-registry.json",
                lambda doc: doc["providers"][0].__setitem__("acceptance_suites", ["FORGE-NOPE-99"]),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("unknown acceptance suite", output)

    def test_two_providers_serving_one_capability_fails(self):
        def mutate(root):
            self._rewrite(
                root / "plugins" / "forge-ue-studio" / "dependencies" / "mcp-registry.json",
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

            self._rewrite(root / "plugins" / "forge-ue-studio" / "dependencies" / "mcp-registry.json", rename)

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("must carry the lane. prefix", output)

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
            text = text.replace('        "verify",           #', '        "not-a-command",\n        "verify",           #', 1)
            source.write_text(text, encoding="utf-8")

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
            source = root / "plugins" / "forge-ue-studio" / "scripts" / "forge.py"
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
            source = root / "plugins" / "forge-ue-studio" / "scripts" / "forge.py"
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
                root / "plugins" / "forge-ue-studio" / "dependencies" / "mcp-registry.json",
                lambda doc: doc["providers"][0].__setitem__("fallbacks", ["something-else"]),
            )

        code, output = self._validate(mutate)
        self.assertEqual(code, 1)
        self.assertIn("catalog fallback", output)


if __name__ == "__main__":
    unittest.main()
