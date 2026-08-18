#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import time
from typing import Any

from mcp_client import McpError, McpSession, text_of

HELP = "The acceptance stages that need a live editor: Blueprint authoring, PIE, and whether the shipped tool catalogue still matches the engine."
BLUEPRINT_TOOLSET = "editor_toolset.toolsets.blueprint.BlueprintTools"
ASSET_TOOLSET = "editor_toolset.toolsets.asset.AssetTools"
APP_TOOLSET = "EditorToolset.EditorAppToolset"
ACTOR_CLASS = "/Script/CoreUObject.Class'/Script/Engine.Actor'"
FOLDER = "/Game/ForgeAcceptance"
CAPTURE_POSE = {
    "location": {"x": 0.0, "y": 0.0, "z": 300.0},
    "rotation": {"pitch": -30.0, "yaw": 0.0, "roll": 0.0},
    "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
}


def stage(name: str, status: str, detail: str) -> dict[str, str]:
    return {"stage": name, "status": status, "detail": detail}


def advertised_toolsets(session: McpSession) -> set[str]:
    listing = text_of(session.call_tool("list_toolsets"))
    found = set()
    for line in listing.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and ":" in stripped:
            found.add(stripped[2:].split(":", 1)[0].strip())
    return found


def blueprint_stage(session: McpSession) -> dict[str, str]:
    asset_name = f"BP_ForgeProbe_{int(time.time())}"
    try:
        created = session.toolset_result(
            BLUEPRINT_TOOLSET,
            "create",
            {"folder_path": FOLDER, "asset_name": asset_name, "asset_type": {"refPath": ACTOR_CLASS}},
        )
        if not isinstance(created, dict) or "refPath" not in created:
            return stage("blueprint-create-compile", "FAIL", f"create returned {json.dumps(created)[:200]}")
        path = f"{FOLDER}/{asset_name}"
        if session.toolset_result(ASSET_TOOLSET, "exists", {"path": path}) is not True:
            return stage("blueprint-create-compile", "FAIL", f"{path} does not exist after create reported success")
        session.toolset_result(BLUEPRINT_TOOLSET, "compile_blueprint", {"blueprint": created, "warnings_as_errors": False})
        saved = session.toolset_result(ASSET_TOOLSET, "save_assets", {"asset_paths": [path]})
        if saved is not True:
            return stage("blueprint-create-compile", "FAIL", f"save_assets returned {json.dumps(saved)[:160]}")
        return stage("blueprint-create-compile", "PASS", f"created, compiled and saved {created['refPath']}")
    except McpError as exc:
        return stage("blueprint-create-compile", "FAIL", str(exc)[:300])


def pie_stage(session: McpSession) -> dict[str, str]:
    started = False
    try:
        if session.toolset_result(APP_TOOLSET, "IsPIERunning") is True:
            return stage("pie-and-viewport-evidence", "FAIL", "PIE was already running before the stage began")
        session.toolset_result(APP_TOOLSET, "StartPIE", {"options": {"bSimulate": False}})
        started = True
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if session.toolset_result(APP_TOOLSET, "IsPIERunning") is True:
                break
            time.sleep(2)
        else:
            return stage("pie-and-viewport-evidence", "FAIL", "PIE did not report running within 60s")

        actors = session.toolset_result(APP_TOOLSET, "GetVisibleActors")
        if not isinstance(actors, list) or not actors:
            return stage("pie-and-viewport-evidence", "FAIL", f"no actor state readable from the running world: {str(actors)[:160]}")

        captured = session.call_toolset(
            APP_TOOLSET, "CaptureViewport", {"captureTransform": CAPTURE_POSE, "annotations": []}
        )
        image = _image_bytes(captured)
        if not image:
            return stage("pie-and-viewport-evidence", "FAIL", f"viewport capture returned no image: {text_of(captured)[:160]}")
        return stage(
            "pie-and-viewport-evidence", "PASS",
            f"PIE ran, {len(actors)} actors readable, viewport captured ({image} bytes of PNG)",
        )
    except McpError as exc:
        return stage("pie-and-viewport-evidence", "FAIL", str(exc)[:300])
    finally:
        if started:
            try:
                session.toolset_result(APP_TOOLSET, "StopPIE")
            except McpError:
                pass


def schema_defaults_stage(session: McpSession) -> dict[str, str]:
    try:
        session.call_toolset(APP_TOOLSET, "CaptureViewport", {"captureTransform": CAPTURE_POSE})
    except McpError as exc:
        if "annotations" in str(exc):
            return stage(
                "schema-defaults-absent", "PASS",
                "omitting an optional parameter failed naming it: " + str(exc)[:200],
            )
        return stage(
            "schema-defaults-absent", "NOT_PROVEN",
            "omitting an optional parameter failed without naming it: " + str(exc)[:200],
        )
    return stage(
        "schema-defaults-absent", "FAIL",
        "CaptureViewport succeeded with annotations omitted, so the server does apply schema defaults",
    )


CATALOGUE = (
    pathlib.Path(__file__).resolve().parents[2]
    / "plugins" / "forge-ue-studio" / "dependencies" / "tool-catalog" / "unreal-mcp@5.8.json"
)


def catalogue_stage(session: McpSession, advertised: set[str]) -> dict[str, str]:
    try:
        catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    except OSError as exc:
        return stage("catalogue-matches-engine", "FAIL", f"no catalogue to check: {exc}")
    toolsets = catalogue["toolsets"]
    gone = sorted(set(toolsets) - advertised)
    if gone:
        return stage(
            "catalogue-matches-engine", "FAIL",
            f"catalogued toolsets no longer advertised: {', '.join(gone)}",
        )
    undescribed = []
    for name, body in toolsets.items():
        try:
            described = text_of(session.call_tool("describe_toolset", {"toolset_name": name}))
        except McpError as exc:
            return stage("catalogue-matches-engine", "FAIL", f"describe_toolset({name}) failed: {str(exc)[:200]}")
        undescribed += [f"{name}.{tool}" for tool in body["tools"] if tool not in described]
    if undescribed:
        return stage(
            "catalogue-matches-engine", "FAIL",
            f"catalogued tools no longer described: {', '.join(undescribed)}",
        )
    total = sum(len(body["tools"]) for body in toolsets.values())
    return stage(
        "catalogue-matches-engine", "PASS",
        f"{len(toolsets)} catalogued toolsets and {total} tools are still advertised by the engine",
    )


def _image_bytes(result: dict[str, Any]) -> int:
    for part in result.get("content", []):
        if part.get("type") == "image" and part.get("data"):
            return len(part["data"])
    try:
        payload = json.loads(text_of(result))
    except (json.JSONDecodeError, TypeError):
        return 0
    image = (payload.get("returnValue") or {}).get("image") if isinstance(payload, dict) else None
    return len(image.get("data", "")) if isinstance(image, dict) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=HELP)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    stages: list[dict[str, str]] = []
    try:
        session = McpSession(args.url, timeout=180)
        session.open()
        advertised = advertised_toolsets(session)
        missing = [name for name in (BLUEPRINT_TOOLSET, ASSET_TOOLSET, APP_TOOLSET) if name not in advertised]
        if missing:
            detail = f"the server does not advertise {', '.join(missing)}; AllToolsets may be disabled"
            stages = [stage("blueprint-create-compile", "NOT_PROVEN", detail),
                      stage("pie-and-viewport-evidence", "NOT_PROVEN", detail),
                      stage("catalogue-matches-engine", "NOT_PROVEN", detail)]
        else:
            stages.append(blueprint_stage(session))
            stages.append(pie_stage(session))
            stages.append(schema_defaults_stage(session))
            stages.append(catalogue_stage(session, advertised))
    except McpError as exc:
        detail = str(exc)[:300]
        stages = [stage("blueprint-create-compile", "FAIL", detail), stage("pie-and-viewport-evidence", "FAIL", detail)]

    rendered = json.dumps({"schema": "forge.live-editor-stages/v1", "url": args.url, "stages": stages}, indent=2)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    return 1 if any(item["status"] == "FAIL" for item in stages) else 0


if __name__ == "__main__":
    raise SystemExit(main())
