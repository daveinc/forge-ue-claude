from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "forge-ue-studio"
INDEX_DIR = PLUGIN / "dependencies" / "api-index"
API_ID = "python-api"
INDEX_SCHEMA = "forge.api-index/v1"
SYMBOLS_SCHEMA = "forge.api-symbols/v1"

sys.path.insert(0, str(PLUGIN / "scripts"))

from forge_api_index import ApiIndexError, ERROR_REASON, load_index

LINE_ENDING = chr(10)
MODULE_SYMBOL = "unreal"
SOURCE_CUT = "**C++ Source:**"
PROPERTY_CUT = "**Editor Properties:**"
CLASS_SUMMARY_LIMIT = 320
METHOD_DOC_LIMIT = 420
PROPERTY_LIMIT = 140
PLUGIN_LINE = re.compile(r"\*\*Plugin\*\*:\s*([^\r\n*]+)")
MODULE_LINE = re.compile(r"\*\*Module\*\*:\s*([^\r\n*]+)")
PROPERTY_LINE = re.compile(r"^-\s+``([^`]+)``\s*\((.+)\):\s*(.*)$")
DOTTED_CALL = re.compile(r"(?<![\w.])(" + MODULE_SYMBOL + r"|[A-Z][A-Za-z0-9_]+)\.([a-z_][A-Za-z0-9_]*)")
PROSE_FIELDS = ("does", "produces")

SEEDS: dict[str, dict[str, list[str]]] = {
    "ik-retarget": {
        "ue.python.commandlet": [
            MODULE_SYMBOL,
            "IKRetargeterController",
            "IKRigController",
            "IKRetargeter",
            "IKRigDefinition",
            "IKRigDefinitionFactory",
            "IKRetargetFactory",
            "AssetTools",
            "AssetToolsHelpers",
            "Skeleton",
            "SkeletalMesh",
            "AnimSequence",
            "AnimBlueprint",
            "EditorAssetLibrary",
        ],
        "ue.batch": [
            MODULE_SYMBOL,
            "IKRetargetBatchOperation",
            "IKRetargetBatchOperationInputs",
            "EditorAssetLibrary",
        ],
    },
    "world-blockout": {
        "ue.python.commandlet": [
            MODULE_SYMBOL,
            "LevelEditorSubsystem",
            "EditorActorSubsystem",
            "EditorLevelLibrary",
            "EditorLoadingAndSavingUtils",
            "EditorAssetLibrary",
            "AssetTools",
            "AssetToolsHelpers",
            "BlueprintFactory",
        ],
        "ue.live.python": [
            MODULE_SYMBOL,
            "LevelEditorSubsystem",
            "EditorActorSubsystem",
            "EditorAssetLibrary",
        ],
    },
    "batch-import": {
        "ue.python.commandlet": [
            MODULE_SYMBOL,
            "AssetImportTask",
            "AssetTools",
            "AssetToolsHelpers",
            "EditorAssetLibrary",
            "FbxImportUI",
            "AssetRegistryHelpers",
        ],
        "ue.batch": [
            MODULE_SYMBOL,
            "AssetImportTask",
            "AssetTools",
            "AssetToolsHelpers",
            "EditorAssetLibrary",
        ],
    },
    "lod-generation": {
        "ue.python.commandlet": [
            MODULE_SYMBOL,
            "StaticMeshEditorSubsystem",
            "StaticMesh",
            "MeshReductionSettings",
            "MeshNaniteSettings",
            "EditorAssetLibrary",
        ],
        "ue.batch": [
            MODULE_SYMBOL,
            "StaticMeshEditorSubsystem",
            "StaticMesh",
            "EditorAssetLibrary",
        ],
    },
}


def collapse(text: str) -> str:
    return " ".join(str(text or "").replace("\r", " ").split())


def clip(text: str, limit: int) -> str:
    body = collapse(text)
    return body if len(body) <= limit else body[:limit].rstrip() + " [...]"


def class_summary(doc: str) -> str:
    return clip(str(doc or "").split(SOURCE_CUT)[0], CLASS_SUMMARY_LIMIT)


def source_module(doc: str) -> dict[str, str]:
    found: dict[str, str] = {}
    plugin = PLUGIN_LINE.search(str(doc or ""))
    module = MODULE_LINE.search(str(doc or ""))
    if plugin:
        found["plugin"] = collapse(plugin.group(1))
    if module:
        found["module"] = collapse(module.group(1))
    return found


def editor_properties(doc: str) -> dict[str, str]:
    text = str(doc or "")
    if PROPERTY_CUT not in text:
        return {}
    found: dict[str, str] = {}
    for line in text.split(PROPERTY_CUT, 1)[1].replace("\r", "").splitlines():
        match = PROPERTY_LINE.match(line.strip())
        if match:
            name, kind, note = match.groups()
            found[collapse(name)] = clip(f"({collapse(kind)}) {collapse(note)}", PROPERTY_LIMIT)
    return found


def method_entry(doc: str) -> dict[str, Any]:
    lines = str(doc or "").replace("\r", "").splitlines()
    signature = collapse(lines[0]) if lines else ""
    body = clip("\n".join(lines[1:]), METHOD_DOC_LIMIT)
    entry: dict[str, Any] = {"signature": signature}
    if body:
        entry["doc"] = body
    if "deprecat" in str(doc or "").lower():
        entry["deprecated"] = True
    return entry


def class_entry(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    doc = raw.get("doc") or ""
    entry: dict[str, Any] = {
        "kind": str(raw.get("kind") or "class"),
        "summary": class_summary(doc),
    }
    bases = [str(item) for item in raw.get("bases") or []]
    if bases:
        entry["bases"] = bases
    entry.update(source_module(doc))
    methods = {
        str(method): method_entry(text)
        for method, text in sorted((raw.get("methods") or {}).items())
    }
    if methods:
        entry["methods"] = methods
    properties = editor_properties(doc)
    if properties:
        entry["editor_properties"] = properties
    if not methods and not properties:
        entry["note"] = f"{name} carries neither a scripted method nor an editor property in this dump."
    return entry


def module_entry(dump: dict[str, Any]) -> dict[str, Any]:
    functions = {
        str(name): method_entry(body.get("doc") or "")
        for name, body in sorted(dump.items())
        if str(body.get("kind")) == "function"
    }
    return {
        "kind": "module",
        "summary": "The unreal module itself: the entry points every editor-closed or live Python script starts from.",
        "methods": functions,
    }


def write_json(path: Path, body: str) -> None:
    with path.open("w", encoding="utf-8", newline=LINE_ENDING) as handle:
        handle.write(body + LINE_ENDING)


def build(source_dir: Path, engine_version: str, out_dir: Path) -> tuple[Path, Path]:
    dump_path = source_dir / "unreal_api.json"
    meta_path = source_dir / "_meta.json"
    if not dump_path.is_file():
        raise ApiIndexError(f"No API dump at {dump_path}", ERROR_REASON["API_INDEX_MISSING"])
    raw_bytes = dump_path.read_bytes()
    dump = json.loads(raw_bytes.decode("utf-8-sig"))
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig")) if meta_path.is_file() else {}

    wanted: set[str] = {name for table in SEEDS.values() for names in table.values() for name in names}
    missing = sorted(name for name in wanted if name != MODULE_SYMBOL and name not in dump)
    if missing:
        raise ApiIndexError(
            f"Seeded symbols absent from {dump_path.name}: {', '.join(missing)}",
            ERROR_REASON["API_SYMBOL_ABSENT"],
        )

    classes: dict[str, Any] = {}
    for name in sorted(wanted):
        classes[name] = module_entry(dump) if name == MODULE_SYMBOL else class_entry(name, dump[name])

    detailed_methods = sum(len(body.get("methods") or {}) for body in classes.values())
    symbols = sorted(dump)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / f"{API_ID}@{engine_version}.json"
    symbols_path = out_dir / f"{API_ID}@{engine_version}.symbols.json"

    index = {
        "schema": INDEX_SCHEMA,
        "api": API_ID,
        "engine_version": engine_version,
        "generated_by": "scripts/api_index.py",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provenance": {
            "source_file": dump_path.name,
            "source_bytes": len(raw_bytes),
            "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "source_meta": meta,
            "note": (
                "Introspected from one live UE " + engine_version + " unreal module on one machine, with that "
                "machine's plugin set enabled. A symbol absent here is absent from that build, not from Unreal; "
                "a project on another engine version or with different plugins enabled will disagree, and "
                "describe/dir() in a live interpreter is the authority when it does."
            ),
        },
        "coverage": {
            "symbols_in_source": len(symbols),
            "classes_detailed": len(classes),
            "methods_detailed": detailed_methods,
            "symbol_manifest": symbols_path.name,
            "note": (
                "Two tiers. This file carries full method detail only for the symbols a shipped procedure "
                "reaches; the manifest carries every symbol name so a lookup that found nothing can say whether "
                "the name is unknown to this engine build or merely not indexed for any task class yet."
            ),
        },
        "capabilities": sorted({name for table in SEEDS.values() for name in table}),
        "task_classes": {
            task_class: {name: sorted(set(members)) for name, members in sorted(table.items())}
            for task_class, table in sorted(SEEDS.items())
        },
        "classes": classes,
    }
    write_json(index_path, json.dumps(index, indent=1, ensure_ascii=False))
    write_json(
        symbols_path,
        json.dumps(
            {
                "schema": SYMBOLS_SCHEMA,
                "api": API_ID,
                "engine_version": engine_version,
                "generated_by": "scripts/api_index.py",
                "source_sha256": index["provenance"]["source_sha256"],
                "note": "Every symbol name the dump carries, and nothing else. Membership only, so a lookup miss is separable from an unindexed hit.",
                "symbols": symbols,
            },
            ensure_ascii=False,
        ),
    )
    return index_path, symbols_path


def procedure_symbol_failures(
    document: dict[str, Any],
    engine_version: str | None = None,
    folder: Path | None = None,
) -> list[str]:
    index = load_index(engine_version, folder)
    classes = index.get("classes", {})
    table = index.get("task_classes", {})
    indexed_capabilities = {str(item) for item in index.get("capabilities", [])}
    failures: list[str] = []
    for task_class, procedure in sorted((document.get("procedures") or {}).items()):
        assortment = table.get(str(task_class), {})
        for position, step in enumerate(procedure.get("steps") or [], start=1):
            capability = str(step.get("capability"))
            if capability not in indexed_capabilities:
                continue
            reachable = {str(name) for name in assortment.get(capability, [])}
            for field in PROSE_FIELDS:
                for owner, method in DOTTED_CALL.findall(str(step.get(field) or "")):
                    body = classes.get(owner)
                    if body is None:
                        failures.append(
                            f"Procedure {task_class!r} step {position} names {owner}.{method} on capability "
                            f"{capability!r}, which the Unreal Python API index does not carry"
                        )
                    elif method not in (body.get("methods") or {}):
                        failures.append(
                            f"Procedure {task_class!r} step {position} names {owner}.{method}, and {owner} carries "
                            f"no such method in the UE {index.get('engine_version')} API index"
                        )
                    elif owner not in reachable:
                        failures.append(
                            f"Procedure {task_class!r} step {position} names {owner}.{method} on capability "
                            f"{capability!r}, which that task class does not assort {owner} under"
                        )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="api_index.py")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--engine-version", default="5.8")
    parser.add_argument("--out", type=Path, default=INDEX_DIR)
    args = parser.parse_args(argv)
    try:
        index_path, symbols_path = build(args.source, args.engine_version, args.out)
    except ApiIndexError as exc:
        print(json.dumps({"ok": False, "reason": exc.reason, "error": str(exc)}))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "index": str(index_path.relative_to(ROOT)),
                "index_bytes": index_path.stat().st_size,
                "symbols": str(symbols_path.relative_to(ROOT)),
                "symbols_bytes": symbols_path.stat().st_size,
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
