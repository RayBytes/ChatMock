"""Cover _extract_usage error path in OpenAI text completions (non-stream)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

import chatmock.routes_openai as routes


class _Up:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False) -> Iterator[bytes]:
        # usage has non-numeric values to trigger the except branch in _extract_usage
        yield (
            b'data: {"type": "response.completed", "response": {"usage": {"input_tokens": "NaN"}}}'
        )

    def close(self) -> None:
        return None


def test_completions_nonstream_usage_value_error(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(), None), raising=True
    )
    body = {"model": "gpt-5", "prompt": "hi"}
    r = client.post("/v1/completions", data=json.dumps(body), content_type="application/json")
    data = r.get_json()
    # Should succeed and omit usage due to parse error
    assert r.status_code == 200 and "usage" not in data
