from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location("mcp_client", Path(__file__).parent / "unreal" / "mcp_client.py")
mcp_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mcp_client)


class TryDecodeTests(unittest.TestCase):

    def frame(self, payload: dict) -> str:
        return f"event: message\ndata: {json.dumps(payload)}\n\n"

    def test_a_partial_frame_decodes_to_nothing_rather_than_raising(self):
        self.assertIsNone(mcp_client._try_decode('{"jsonrpc":"2.0","result":{"a"'))

    def test_a_partial_sse_frame_decodes_to_nothing(self):
        self.assertIsNone(mcp_client._try_decode('event: message\ndata: {"jsonrpc":"2.0","result"'))

    def test_a_complete_frame_decodes(self):
        payload = {"jsonrpc": "2.0", "id": 1, "result": {"a": 1}}
        self.assertEqual(mcp_client._try_decode(self.frame(payload))["result"]["a"], 1)

    def test_a_bare_json_body_decodes(self):
        payload = {"jsonrpc": "2.0", "id": 1, "result": {"a": 1}}
        self.assertEqual(mcp_client._try_decode(json.dumps(payload))["result"]["a"], 1)

    def test_an_interior_closing_brace_does_not_truncate_the_payload(self):
        payload = {"jsonrpc": "2.0", "id": 1, "result": {"b": {"c": 2}, "d": 3}}
        decoded = mcp_client._try_decode(self.frame(payload))
        self.assertEqual(decoded["result"]["b"]["c"], 2)
        self.assertEqual(decoded["result"]["d"], 3)

    def test_a_frame_truncated_at_an_interior_closing_brace_decodes_to_nothing(self):
        payload = {"jsonrpc": "2.0", "id": 1, "result": {"b": {"c": 2}, "d": 3}}
        whole = self.frame(payload)
        truncated = whole[:whole.index('"d"')]
        self.assertIsNone(mcp_client._try_decode(truncated))

    def test_an_empty_body_decodes_to_nothing(self):
        self.assertIsNone(mcp_client._try_decode(""))


class ReadUntilParsedTests(unittest.TestCase):

    def test_read1_is_preferred_so_a_short_reply_on_an_open_stream_returns(self):
        source = (Path(mcp_client.__file__).parent / "mcp_client.py").read_text(encoding="utf-8")
        body = source[source.index("def _read_frame"):source.index("def _try_decode")]
        self.assertIn('getattr(response, "read1", response.read)', body)

    def test_a_reader_returning_one_chunk_at_a_time_still_yields_a_whole_frame(self):
        payload = {"jsonrpc": "2.0", "id": 1, "result": {"b": {"c": 2}, "d": 3}}
        whole = TryDecodeTests.frame(None, payload).encode("utf-8")

        class Dribbler:
            def __init__(self, data):
                self.data, self.at = data, 0

            def read1(self, size=-1):
                chunk = self.data[self.at:self.at + 8]
                self.at += len(chunk)
                return chunk

            def read(self, size=-1):
                return self.data[self.at:]

        frame = mcp_client._read_frame(Dribbler(whole), True, 1)
        self.assertEqual(mcp_client._try_decode(frame)["result"]["d"], 3)


if __name__ == "__main__":
    unittest.main()
