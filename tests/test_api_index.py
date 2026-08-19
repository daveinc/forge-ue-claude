from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "scripts" / "api_index.py"
RESOLVER_PATH = ROOT / "plugins" / "forge-ue-studio" / "scripts" / "forge_api_index.py"
INDEX_DIR = ROOT / "plugins" / "forge-ue-studio" / "dependencies" / "api-index"
INDEX_PATH = INDEX_DIR / "python-api@5.8.json"
SYMBOLS_PATH = INDEX_DIR / "python-api@5.8.symbols.json"
PROCEDURES_PATH = ROOT / "plugins" / "forge-ue-studio" / "doctrine" / "procedures.json"
SHIPPED_BUDGET = 700_000

SPEC = importlib.util.spec_from_file_location("api_index", MODULE_PATH)
assert SPEC and SPEC.loader
api_index = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api_index)
resolver = sys.modules["forge_api_index"]


class ApiIndexShipsSmallTest(unittest.TestCase):
    def test_index_and_manifest_ship_beside_each_other(self):
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        self.assertEqual(index["schema"], "forge.api-index/v1")
        self.assertEqual(index["engine_version"], "5.8")
        self.assertEqual(index["coverage"]["symbol_manifest"], SYMBOLS_PATH.name)
        manifest = json.loads(SYMBOLS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], "forge.api-symbols/v1")
        self.assertEqual(len(manifest["symbols"]), index["coverage"]["symbols_in_source"])

    def test_committed_bytes_stay_under_the_budget_the_dump_would_blow(self):
        shipped = INDEX_PATH.stat().st_size + SYMBOLS_PATH.stat().st_size
        self.assertLess(shipped, SHIPPED_BUDGET)
        self.assertLess(shipped, json.loads(INDEX_PATH.read_text(encoding="utf-8"))["provenance"]["source_bytes"] // 20)

    def test_provenance_names_the_engine_and_pins_the_source(self):
        provenance = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["provenance"]
        self.assertEqual(len(provenance["source_sha256"]), 64)
        self.assertEqual(provenance["source_meta"]["symbols"], 11794)
        self.assertIn("5.8", provenance["source_meta"]["engine_note"])


class ApiIndexResolutionTest(unittest.TestCase):
    def test_the_resolver_ships_inside_the_plugin_where_a_packet_compiler_reaches_it(self):
        self.assertEqual(Path(resolver.__file__).resolve(), RESOLVER_PATH.resolve())
        generator = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("def api_classes_for", generator)
        self.assertIn("def build", generator)

    def test_resolution_is_assorted_per_task_class(self):
        lod = resolver.api_classes_for("lod-generation", ["ue.batch"])
        self.assertIn("StaticMeshEditorSubsystem", lod)
        self.assertNotIn("IKRetargeterController", lod)
        retarget = resolver.api_classes_for("ik-retarget", ["ue.batch"])
        self.assertIn("IKRetargetBatchOperation", retarget)
        self.assertNotIn("StaticMeshEditorSubsystem", retarget)

    def test_resolution_is_assorted_per_capability_within_one_task_class(self):
        commandlet = resolver.api_classes_for("ik-retarget", ["ue.python.commandlet"])
        batch = resolver.api_classes_for("ik-retarget", ["ue.batch"])
        self.assertIn("IKRetargeterController", commandlet)
        self.assertNotIn("IKRetargeterController", batch)
        self.assertNotIn("IKRetargetBatchOperation", commandlet)

    def test_call_names_intersect_the_provider_with_the_declared_capabilities(self):
        reached = resolver.api_call_names("unreal-python", "world-blockout", ["ue.python.commandlet"])
        self.assertIn("LevelEditorSubsystem.new_level", reached)
        self.assertIn("EditorActorSubsystem.spawn_actor_from_class", reached)
        self.assertEqual(resolver.api_call_names("unreal-python", "world-blockout", ["ue.live.typed"]), [])
        self.assertEqual(resolver.api_call_names("unreal-native-mcp", "world-blockout", ["ue.pie"]), [])
        self.assertEqual(resolver.api_call_names("no-such-provider", "world-blockout", ["ue.batch"]), [])

    def test_a_capability_that_reaches_nothing_is_empty_but_an_unknown_task_class_is_typed(self):
        self.assertEqual(resolver.api_classes_for("world-blockout", ["ue.viewport"]), {})
        with self.assertRaises(resolver.ApiIndexError) as caught:
            resolver.api_classes_for("landscape-sculpt", ["ue.python.commandlet"])
        self.assertEqual(caught.exception.reason, "api_index_unknown_task_class")

    def test_a_missing_index_folder_is_a_typed_failure(self):
        with self.assertRaises(resolver.ApiIndexError) as caught:
            resolver.load_index(None, ROOT / "plugins" / "forge-ue-studio" / "dependencies" / "no-index-here")
        self.assertEqual(caught.exception.reason, "api_index_missing")


class ApiIndexHonestyTest(unittest.TestCase):
    def test_lookup_separates_indexed_unindexed_and_absent(self):
        self.assertEqual(resolver.api_lookup("LevelEditorSubsystem")["status"], "indexed")
        unindexed = resolver.api_lookup("Landscape")
        self.assertEqual(unindexed["status"], "present_not_indexed")
        self.assertNotIn("reason", unindexed)
        absent = resolver.api_lookup("NotAnUnrealClassAnywhere")
        self.assertEqual(absent["status"], "absent")
        self.assertEqual(absent["reason"], "api_symbol_absent")
        self.assertEqual(absent["engine_version"], "5.8")

    def test_deprecation_is_recorded_per_method(self):
        classes = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["classes"]
        library = classes["EditorLevelLibrary"]["methods"]
        self.assertEqual(library["destroy_actor"].get("deprecated"), True)
        self.assertIsNone(library["spawn_actor_from_class"].get("deprecated"))
        deprecated = [name for name, body in library.items() if body.get("deprecated")]
        self.assertEqual(len(deprecated), 32)

    def test_the_module_entry_carries_the_editor_closed_entry_points(self):
        module = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["classes"]["unreal"]["methods"]
        self.assertIn("get_editor_subsystem", module)
        self.assertIn("load_asset", module)
        self.assertIn("is_editor", module)


class ProcedureSymbolGuardTest(unittest.TestCase):
    def test_shipped_procedures_name_no_symbol_the_index_lacks(self):
        document = json.loads(PROCEDURES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(api_index.procedure_symbol_failures(document), [])

    def test_guard_flags_a_method_this_engine_does_not_carry(self):
        document = {
            "procedures": {
                "world-blockout": {
                    "steps": [
                        {
                            "does": "Call LevelEditorSubsystem.make_me_a_level and hope.",
                            "produces": "Nothing.",
                            "capability": "ue.python.commandlet",
                        }
                    ]
                }
            }
        }
        failures = api_index.procedure_symbol_failures(document)
        self.assertEqual(len(failures), 1)
        self.assertIn("make_me_a_level", failures[0])

    def test_guard_flags_a_class_the_index_does_not_carry(self):
        document = {
            "procedures": {
                "world-blockout": {
                    "steps": [
                        {
                            "does": "Call LandscapeEditorObject.import_heightmap in a commandlet.",
                            "produces": "Nothing.",
                            "capability": "ue.python.commandlet",
                        }
                    ]
                }
            }
        }
        failures = api_index.procedure_symbol_failures(document)
        self.assertEqual(len(failures), 1)
        self.assertIn("does not carry", failures[0])

    def test_guard_flags_a_real_call_the_task_class_does_not_assort(self):
        document = {
            "procedures": {
                "world-blockout": {
                    "steps": [
                        {
                            "does": "Call StaticMeshEditorSubsystem.get_lod_count while blocking out.",
                            "produces": "Nothing.",
                            "capability": "ue.python.commandlet",
                        }
                    ]
                }
            }
        }
        failures = api_index.procedure_symbol_failures(document)
        self.assertEqual(len(failures), 1)
        self.assertIn("does not assort", failures[0])

    def test_guard_ignores_calls_on_a_capability_this_index_does_not_serve(self):
        document = {
            "procedures": {
                "world-blockout": {
                    "steps": [
                        {
                            "does": "Confirm with AssetTools.exists that the path is free.",
                            "produces": "Nothing.",
                            "capability": "ue.live.typed",
                        }
                    ]
                }
            }
        }
        self.assertEqual(api_index.procedure_symbol_failures(document), [])


class GeneratorTest(unittest.TestCase):
    def test_generator_refuses_a_source_directory_with_no_dump(self):
        with self.assertRaises(resolver.ApiIndexError) as caught:
            api_index.build(ROOT / "scripts", "5.8", ROOT / "scripts")
        self.assertEqual(caught.exception.reason, "api_index_missing")

    def test_every_seeded_symbol_is_carried_by_the_generated_index(self):
        classes = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["classes"]
        seeded = {name for table in api_index.SEEDS.values() for names in table.values() for name in names}
        self.assertEqual(sorted(seeded - set(classes)), [])
        self.assertEqual(sorted(set(classes) - seeded), [])


if __name__ == "__main__":
    unittest.main()
