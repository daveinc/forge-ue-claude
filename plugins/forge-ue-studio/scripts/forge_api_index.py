from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forge_core import ERROR_REASON, plugin_root
from forge_mcp import route_providers


API_ID = "python-api"


class ApiIndexError(Exception):

    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def index_path_for(engine_version: str | None, folder: Path | None = None) -> Path | None:
    folder = folder or plugin_root() / "dependencies" / "api-index"
    if not folder.is_dir():
        return None
    if engine_version:
        exact = folder / f"{API_ID}@{engine_version}.json"
        if exact.is_file():
            return exact
    candidates = sorted(
        (path for path in folder.glob(f"{API_ID}@*.json") if not path.name.endswith(".symbols.json")),
        reverse=True,
    )
    return candidates[0] if candidates else None


def load_index(engine_version: str | None = None, folder: Path | None = None) -> dict[str, Any]:
    path = index_path_for(engine_version, folder)
    if path is None:
        raise ApiIndexError(
            f"No shipped Unreal Python API index for engine {engine_version or 'any'}; "
            "regenerate it with scripts/api_index.py before a procedure can name a call",
            ERROR_REASON["API_INDEX_MISSING"],
        )
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_symbols(engine_version: str | None = None, folder: Path | None = None) -> set[str]:
    path = index_path_for(engine_version, folder)
    if path is None:
        raise ApiIndexError("No shipped Unreal Python API index", ERROR_REASON["API_INDEX_MISSING"])
    manifest = path.with_name(str(load_index(engine_version, folder)["coverage"]["symbol_manifest"]))
    if not manifest.is_file():
        raise ApiIndexError(
            f"The index names symbol manifest {manifest.name}, which does not ship beside it",
            ERROR_REASON["API_INDEX_MISSING"],
        )
    return set(json.loads(manifest.read_text(encoding="utf-8-sig")).get("symbols", []))


def api_classes_for(
    task_class: str,
    capabilities: list[str],
    engine_version: str | None = None,
    folder: Path | None = None,
) -> dict[str, dict[str, Any]]:
    index = load_index(engine_version, folder)
    table = index.get("task_classes", {})
    if str(task_class) not in table:
        raise ApiIndexError(
            f"Task class {task_class!r} has no Unreal Python API assortment; known: "
            f"{', '.join(sorted(table)) or 'none'}",
            ERROR_REASON["API_INDEX_UNKNOWN_TASK_CLASS"],
        )
    wanted = {str(item) for item in capabilities}
    reached: set[str] = set()
    for capability, names in table[str(task_class)].items():
        if capability in wanted:
            reached.update(str(name) for name in names)
    return {name: index["classes"][name] for name in sorted(reached) if name in index.get("classes", {})}


def api_call_names(
    provider_id: str | None,
    task_class: str,
    capabilities: list[str],
    engine_version: str | None = None,
    folder: Path | None = None,
) -> list[str]:
    provider = next(
        (row for row in route_providers() if str(row.get("id")) == str(provider_id)),
        None,
    )
    if not provider:
        return []
    served = {str(item) for item in provider.get("capabilities", [])} & {str(item) for item in capabilities}
    if not served:
        return []
    assorted = api_classes_for(task_class, sorted(served), engine_version, folder)
    return sorted(
        f"{name}.{method}"
        for name, body in assorted.items()
        for method in (body.get("methods") or {})
    )


def api_lookup(
    symbol: str,
    engine_version: str | None = None,
    folder: Path | None = None,
) -> dict[str, Any]:
    index = load_index(engine_version, folder)
    engine = str(index.get("engine_version", ""))
    if str(symbol) in index.get("classes", {}):
        return {"symbol": str(symbol), "status": "indexed", "engine_version": engine}
    if str(symbol) in load_symbols(engine_version, folder):
        return {
            "symbol": str(symbol),
            "status": "present_not_indexed",
            "engine_version": engine,
            "note": f"{symbol} exists in the UE {engine} dump but no shipped procedure reaches it, so no method detail ships; "
            "seed it in scripts/api_index.py and regenerate rather than guessing its methods.",
        }
    return {
        "symbol": str(symbol),
        "status": "absent",
        "engine_version": engine,
        "reason": ERROR_REASON["API_SYMBOL_ABSENT"],
        "note": f"{symbol} is in no symbol of the UE {engine} introspection dump. It may exist on another engine "
        "version or behind a plugin that machine did not have enabled; confirm in a live interpreter before naming it.",
    }
