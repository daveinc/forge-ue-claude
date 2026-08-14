from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FORGE_PATH = ROOT / "plugins" / "forge-ue-studio" / "scripts" / "forge.py"
TEMP_ROOT = ROOT / "tests" / ".tmp"
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
        shutil.rmtree(path)


class ForgeInstallerTests(unittest.TestCase):
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

    def test_survey_separates_detection_from_verification(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            result = forge.survey(str(project))
            self.assertEqual(result["schema"], "forge.environment-snapshot/v1")
            self.assertEqual(result["providers"]["resident_default"], "codex")
            self.assertIn("gsd_detected", result["providers"])
            self.assertIn("gsd_inventory", result["providers"])
            self.assertIn("runtime_script", result["providers"]["gsd_inventory"])
            self.assertIn("skill_roots", result["providers"]["gsd_inventory"])
            self.assertIn("local_worker_candidates", result["providers"])
            self.assertTrue(result["unreal"]["vibeue_declared"])
            statuses = {item["capability"]: item["status"] for item in result["capabilities"]}
            self.assertEqual(statuses["ue.live.python"], "AVAILABLE_UNVERIFIED")
            self.assertEqual(statuses["dcc.unreal.animation"], "AVAILABLE_UNVERIFIED")
            self.assertEqual(statuses["worker.codex.resident"], "AVAILABLE_UNVERIFIED")
            self.assertIn(statuses["workflow.gsd"], {"AVAILABLE_UNVERIFIED", "UNAVAILABLE_BLOCKING"})
            gsd = next(item for item in result["capabilities"] if item["capability"] == "workflow.gsd")
            self.assertEqual(gsd["qualification"]["state"], "UNQUALIFIED")

    def test_route_policy_keeps_codex_resident_and_local_workers_optional(self):
        policy_path = ROOT / "plugins" / "forge-ue-studio" / "dependencies" / "route-policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertEqual(policy["resident_default"]["provider"], "codex")
        self.assertTrue(policy["resident_default"]["fallback_for_optional_workers"])
        self.assertIn("context-heavy-extraction", policy["offload_policy"]["consider_for"])
        self.assertIn("final-synthesis", policy["offload_policy"]["keep_on_codex_by_default"])
        self.assertTrue(policy["offload_policy"]["require_task_and_complexity_eval"])

    def test_dry_run_does_not_write(self):
        with workspace_tempdir() as temp:
            project = self.make_project(temp)
            result = forge.install_overlay(str(project), apply=False)
            self.assertEqual(result["mode"], "dry-run")
            self.assertFalse((project / ".forge").exists())
            self.assertTrue(any(item["action"] == "create" for item in result["actions"]))

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
        self.assertEqual(preview["scope"], "global-codex")
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
            self.assertEqual(forge.route_work(str(project), str(request_path))["selected"], "codex")

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
