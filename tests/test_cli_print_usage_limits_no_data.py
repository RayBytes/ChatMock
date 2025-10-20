"""Cover _print_usage_limits_block when no data available."""

from __future__ import annotations

from chatmock import cli


def test_print_usage_limits_no_data(monkeypatch: object, capsys: object) -> None:
    """When no rate limit data exists, print appropriate message."""
    # Mock load_rate_limit_snapshot to return None
    monkeypatch.setattr(cli, "load_rate_limit_snapshot", lambda: None)

    # Call the function
    cli._print_usage_limits_block()

    # Capture stdout
    captured = capsys.readouterr()

    # Verify the output contains the "no data" message
    assert "No usage data available yet" in captured.out
    assert "Send a request through ChatMock first" in captured.out
    assert "📊 Usage Limits" in captured.out
