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
        self.assertEqual(preview["package"], "@opengsd/gsd-core@1.9.1")
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
            with self.assertRaisesRegex(ValueError, "transitions are deprecated"):
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


if __name__ == "__main__":
    unittest.main()
