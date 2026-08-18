#!/usr/bin/env python3
"""A minimal streamable-HTTP MCP client, for talking to a live Unreal editor.

Forge itself only performs `initialize`, because that is all a capability probe
needs: a route either answers or it does not. Driving the editor needs a session,
so this lives with the acceptance tests rather than in the plugin.

The tool names are deliberately not hard-coded anywhere. Unreal's server runs in
discovery mode by default, where `tools/list` returns only `list_toolsets`,
`describe_toolset` and `call_tool`, and everything else is reached through
`call_tool`. What a toolset offers is read at runtime, never assumed.
"""

from __future__ import annotations

import argparse
import json
import sys
import http.client
import urllib.parse
from typing import Any


PROTOCOL_VERSION = "2025-06-18"


class McpError(Exception):
    pass


class McpSession:
    def __init__(self, url: str, timeout: float = 30.0):
        self.url = url
        self.timeout = timeout
        self.session_id: str | None = None
        self.server_info: dict[str, Any] = {}
        self._next_id = 0

    def _post(self, payload: dict[str, Any], expect_reply: bool = True) -> dict[str, Any] | None:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        parsed = urllib.parse.urlparse(self.url)
        opener = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = opener(parsed.hostname, parsed.port, timeout=self.timeout)
        try:
            connection.request("POST", parsed.path or "/", body=json.dumps(payload), headers=headers)
            response = connection.getresponse()
            assigned = response.getheader("Mcp-Session-Id")
            if assigned:
                self.session_id = assigned
            if response.status >= 400:
                detail = response.read(4096).decode("utf-8", "replace")
                raise McpError(f"{payload.get('method')} returned HTTP {response.status}: {detail[:400]}")
            raw = _read_frame(response, expect_reply, payload.get("id"))
        except OSError as exc:
            raise McpError(f"{payload.get('method')} could not reach {self.url}: {exc}") from None
        finally:
            connection.close()
        if not expect_reply:
            return None
        return _decode(raw, str(payload.get("method")))

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._next_id += 1
        reply = self._post({"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params or {}})
        if reply is None:
            raise McpError(f"{method} returned no reply")
        if "error" in reply:
            raise McpError(f"{method} failed: {json.dumps(reply['error'])[:400]}")
        return reply.get("result")

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._post({"jsonrpc": "2.0", "method": method, "params": params or {}}, expect_reply=False)

    def open(self) -> dict[str, Any]:
        result = self.call(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "forge-unreal-acceptance", "version": "1"},
            },
        )
        self.server_info = (result or {}).get("serverInfo", {})
        self.notify("notifications/initialized")
        return result or {}

    def tools(self) -> list[dict[str, Any]]:
        return list((self.call("tools/list") or {}).get("tools", []))

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.call("tools/call", {"name": name, "arguments": arguments or {}}) or {}

    def call_toolset(self, toolset: str, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.call_tool(
            "call_tool",
            {"toolset_name": toolset, "tool_name": tool, "arguments": arguments or {}},
        )

    def toolset_result(self, toolset: str, tool: str, arguments: dict[str, Any] | None = None) -> Any:
        text = text_of(self.call_toolset(toolset, tool, arguments))
        try:
            decoded = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text
        if isinstance(decoded, dict) and "returnValue" in decoded:
            return decoded["returnValue"]
        return decoded


def _read_frame(response: Any, expect_reply: bool, message_id: Any = None) -> str:
    if not expect_reply:
        return ""
    reader = getattr(response, "read1", response.read)
    buffered = b""
    while len(buffered) < 32_000_000:
        chunk = reader(8192)
        if not chunk:
            break
        buffered += chunk
        text = buffered.decode("utf-8", "replace")
        if _try_decode(text) is not None:
            return text
    return buffered.decode("utf-8", "replace")


def _try_decode(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None
    for line in stripped.splitlines():
        candidate = line.strip()
        if not candidate.startswith("data:"):
            continue
        body = candidate[5:].strip()
        if not body.startswith("{"):
            continue
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            continue
    return None


def _decode(raw: str, method: str) -> dict[str, Any]:
    if not raw.strip():
        raise McpError(f"{method} returned an empty body")
    decoded = _try_decode(raw)
    if decoded is None:
        raise McpError(f"{method} returned no complete JSON-RPC frame: {raw.strip()[:200]}")
    return decoded


def text_of(result: dict[str, Any]) -> str:
    parts = [item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"]
    return "\n".join(part for part in parts if part)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    parser.add_argument("--describe", action="store_true", help="Also describe every toolset the server advertises")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    session = McpSession(args.url)
    try:
        session.open()
        tools = session.tools()
        report: dict[str, Any] = {
            "schema": "forge.mcp-discovery/v1",
            "url": args.url,
            "server_info": session.server_info,
            "tools": [{"name": item.get("name"), "description": item.get("description")} for item in tools],
            "toolsets": [],
        }
        names = {str(item.get("name")) for item in tools}
        if "list_toolsets" in names:
            listed = session.call_tool("list_toolsets")
            report["list_toolsets"] = text_of(listed)
            if args.describe:
                for line in report["list_toolsets"].splitlines():
                    candidate = line.strip().strip("-*` ").split()[0] if line.strip() else ""
                    if not candidate or candidate.endswith(":"):
                        continue
                    try:
                        described = session.call_tool("describe_toolset", {"toolset": candidate})
                        report["toolsets"].append({"toolset": candidate, "detail": text_of(described)})
                    except McpError as exc:
                        report["toolsets"].append({"toolset": candidate, "error": str(exc)})
    except McpError as exc:
        print(json.dumps({"schema": "forge.mcp-discovery/v1", "ok": False, "error": str(exc)}, indent=2))
        return 1

    rendered = json.dumps({**report, "ok": True}, indent=2)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
