from __future__ import annotations

import unittest

from chatmock.responses_websocket_sessions import (
    ResponsesWebsocketSessionCapacityError,
    ResponsesWebsocketSessionConflictError,
    acquire_retained_upstream_websocket,
    release_retained_upstream_websocket,
    reset_retained_upstream_websocket_sessions,
)


class FakeRetainedUpstreamWebsocket:
    def __init__(self) -> None:
        self.closed = False
        self.close_calls = 0

    def close(self) -> None:
        self.closed = True
        self.close_calls += 1
        return None


class RetainedUpstreamWebsocketRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_retained_upstream_websocket_sessions()

    def tearDown(self) -> None:
        reset_retained_upstream_websocket_sessions()

    def test_registry_reuses_released_websocket_for_same_session(self) -> None:
        created: list[FakeRetainedUpstreamWebsocket] = []

        def factory() -> FakeRetainedUpstreamWebsocket:
            websocket = FakeRetainedUpstreamWebsocket()
            created.append(websocket)
            return websocket

        first = acquire_retained_upstream_websocket("session-fixed", factory, max_sessions=2)
        release_retained_upstream_websocket(first, retain=True)
        second = acquire_retained_upstream_websocket("session-fixed", factory, max_sessions=2)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertIs(first.upstream_ws, second.upstream_ws)
        self.assertEqual(len(created), 1)

        release_retained_upstream_websocket(second, retain=True)

    def test_registry_rejects_same_session_contention(self) -> None:
        lease = acquire_retained_upstream_websocket(
            "session-fixed",
            FakeRetainedUpstreamWebsocket,
            max_sessions=2,
        )

        with self.assertRaisesRegex(
            ResponsesWebsocketSessionConflictError,
            "already in progress",
        ):
            acquire_retained_upstream_websocket(
                "session-fixed",
                FakeRetainedUpstreamWebsocket,
                max_sessions=2,
            )

        release_retained_upstream_websocket(lease, retain=True)

    def test_registry_rejects_new_session_when_all_capacity_is_in_use(self) -> None:
        first = acquire_retained_upstream_websocket("session-1", FakeRetainedUpstreamWebsocket, max_sessions=2)
        second = acquire_retained_upstream_websocket("session-2", FakeRetainedUpstreamWebsocket, max_sessions=2)

        with self.assertRaisesRegex(
            ResponsesWebsocketSessionCapacityError,
            "Too many retained upstream websocket sessions are active right now.",
        ):
            acquire_retained_upstream_websocket("session-3", FakeRetainedUpstreamWebsocket, max_sessions=2)

        release_retained_upstream_websocket(first, retain=False)
        release_retained_upstream_websocket(second, retain=False)

    def test_registry_evicts_oldest_idle_session_when_capacity_is_reached(self) -> None:
        first = acquire_retained_upstream_websocket("session-1", FakeRetainedUpstreamWebsocket, max_sessions=2)
        release_retained_upstream_websocket(first, retain=True)
        second = acquire_retained_upstream_websocket("session-2", FakeRetainedUpstreamWebsocket, max_sessions=2)
        release_retained_upstream_websocket(second, retain=True)

        third = acquire_retained_upstream_websocket("session-3", FakeRetainedUpstreamWebsocket, max_sessions=2)

        self.assertTrue(third.created)
        self.assertEqual(first.upstream_ws.close_calls, 1)
        self.assertEqual(second.upstream_ws.close_calls, 0)

        release_retained_upstream_websocket(third, retain=True)

    def test_registry_discards_closed_retained_websocket_before_reuse(self) -> None:
        created: list[FakeRetainedUpstreamWebsocket] = []

        def factory() -> FakeRetainedUpstreamWebsocket:
            websocket = FakeRetainedUpstreamWebsocket()
            created.append(websocket)
            return websocket

        first = acquire_retained_upstream_websocket("session-fixed", factory, max_sessions=2)
        release_retained_upstream_websocket(first, retain=True)
        first.upstream_ws.closed = True

        second = acquire_retained_upstream_websocket("session-fixed", factory, max_sessions=2)

        self.assertTrue(second.created)
        self.assertIsNot(first.upstream_ws, second.upstream_ws)
        self.assertEqual(first.upstream_ws.close_calls, 1)
        self.assertEqual(len(created), 2)

        release_retained_upstream_websocket(second, retain=True)


if __name__ == "__main__":
    unittest.main()