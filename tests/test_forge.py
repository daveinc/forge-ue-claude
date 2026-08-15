from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
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

    def complete_bootstrap(self, project: Path) -> None:
        report = {
            "schema": "forge.bootstrap-report/v1",
            "verdict": "PASS",
            "jobs": [],
            "delegation": {"mode": "test-fixture"},
            "verified": [],
            "assumed": [],
            "unavailable": [],
            "blocking": [],
            "human_actions": [],
            "evidence": [],
            "next_action": "$forge-next",
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
        self.assertEqual(preview["package"], "@opengsd/gsd-core@1.8.0")
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
            self.assertTrue(all(item["action"] == "unchanged" for item in second["actions"]))
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
            with self.assertRaisesRegex(ValueError, "Unregistered work_order"):
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
            with self.assertRaisesRegex(ValueError, "transitions are deprecated"):
                forge.lifecycle_state(str(project), "bootstrap-start", apply=False)

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

    def test_forge_next_routes_existing_docs_to_gsd_ingest(self):
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
            self.assertEqual(result["actions"][0]["command"], '/gsd-ingest-docs "Docs\\Design"')

    def test_forge_next_routes_existing_unreal_project_to_gsd_onboard(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            forge.install_overlay(str(project), apply=True)
            self.complete_bootstrap(project)
            gsd = {"ok": True, "error": "", "snapshot": {"situation": "no-project", "actions": []}}
            result = forge.forge_next(str(project), gsd)
            self.assertEqual(result["situation"], "existing-project-unplanned")
            self.assertEqual(result["actions"][0]["command"], "/gsd-onboard")

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
            self.assertEqual(result["actions"][0]["command"], "/gsd-progress --next")
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
            with self.assertRaisesRegex(ValueError, "not adopted"):
                forge.host_set(str(project), "codex", apply=False)
            forge.install_overlay(str(project), apply=True)
            with self.assertRaisesRegex(ValueError, "Unknown host"):
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
                self.assertEqual(len(agents), 9)
                self.assertTrue(forge.verify_overlay(str(project), host_id)["ok"])
                # No unresolved canon tokens may survive rendering.
                for path in [project / surface["instruction_file"], *agents]:
                    self.assertNotIn("{{", path.read_text(encoding="utf-8"), str(path))

    def test_canon_never_carries_a_host_specific_spelling(self):
        template = ROOT / "plugins" / "forge-ue-studio" / "assets" / "project-template"
        for path in template.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8-sig")
            for banned in ("$forge-", "$gsd-", "/forge-", "/gsd-"):
                # The instruction template carries tokens, never resolved spellings.
                self.assertNotIn(banned, text, f"{path.relative_to(ROOT)} hardcodes {banned}")

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


if __name__ == "__main__":
    unittest.main()
