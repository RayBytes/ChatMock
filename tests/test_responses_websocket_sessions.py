from __future__ import annotations

import unittest

from chatmock.responses_websocket_sessions import (
    ResponsesWebsocketSessionCapacityError,
    ResponsesWebsocketSessionConflictError,
    ResponsesWebsocketSessionNotFoundError,
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

    def test_registry_promotes_first_turn_to_response_marker_and_reuses_it(self) -> None:
        created: list[FakeRetainedUpstreamWebsocket] = []

        def factory() -> FakeRetainedUpstreamWebsocket:
            websocket = FakeRetainedUpstreamWebsocket()
            created.append(websocket)
            return websocket

        first = acquire_retained_upstream_websocket(None, factory, max_sessions=2)
        release_retained_upstream_websocket(
            first,
            retain=True,
            response_id="resp_fixed_1",
        )
        second = acquire_retained_upstream_websocket("resp_fixed_1", factory, max_sessions=2)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertIs(first.upstream_ws, second.upstream_ws)
        self.assertEqual(len(created), 1)

        release_retained_upstream_websocket(
            second,
            retain=True,
            response_id="resp_fixed_2",
        )

    def test_registry_rotates_retained_ownership_to_latest_response_marker(self) -> None:
        first = acquire_retained_upstream_websocket(None, FakeRetainedUpstreamWebsocket, max_sessions=2)
        release_retained_upstream_websocket(
            first,
            retain=True,
            response_id="resp_fixed_1",
        )

        second = acquire_retained_upstream_websocket(
            "resp_fixed_1",
            FakeRetainedUpstreamWebsocket,
            max_sessions=2,
        )
        release_retained_upstream_websocket(
            second,
            retain=True,
            response_id="resp_fixed_2",
        )

        third = acquire_retained_upstream_websocket(
            "resp_fixed_2",
            FakeRetainedUpstreamWebsocket,
            max_sessions=2,
        )

        self.assertFalse(third.created)
        self.assertIs(third.upstream_ws, first.upstream_ws)

        release_retained_upstream_websocket(
            third,
            retain=True,
            response_id="resp_fixed_3",
        )

    def test_registry_rejects_same_marker_contention(self) -> None:
        seed = acquire_retained_upstream_websocket(None, FakeRetainedUpstreamWebsocket, max_sessions=2)
        release_retained_upstream_websocket(
            seed,
            retain=True,
            response_id="resp_fixed_1",
        )

        lease = acquire_retained_upstream_websocket(
            "resp_fixed_1",
            FakeRetainedUpstreamWebsocket,
            max_sessions=2,
        )

        with self.assertRaisesRegex(
            ResponsesWebsocketSessionConflictError,
            "already in progress",
        ):
            acquire_retained_upstream_websocket(
                "resp_fixed_1",
                FakeRetainedUpstreamWebsocket,
                max_sessions=2,
            )

        release_retained_upstream_websocket(
            lease,
            retain=True,
            response_id="resp_fixed_2",
        )

    def test_registry_rejects_new_conversation_when_all_capacity_is_in_use(self) -> None:
        first = acquire_retained_upstream_websocket(None, FakeRetainedUpstreamWebsocket, max_sessions=2)
        second = acquire_retained_upstream_websocket(None, FakeRetainedUpstreamWebsocket, max_sessions=2)

        with self.assertRaisesRegex(
            ResponsesWebsocketSessionCapacityError,
            "Too many retained upstream websocket sessions are active right now.",
        ):
            acquire_retained_upstream_websocket(None, FakeRetainedUpstreamWebsocket, max_sessions=2)

        release_retained_upstream_websocket(first, retain=False)
        release_retained_upstream_websocket(second, retain=False)

    def test_registry_evicts_oldest_idle_marker_when_capacity_is_reached(self) -> None:
        first = acquire_retained_upstream_websocket(None, FakeRetainedUpstreamWebsocket, max_sessions=2)
        release_retained_upstream_websocket(first, retain=True, response_id="resp_1")
        second = acquire_retained_upstream_websocket(None, FakeRetainedUpstreamWebsocket, max_sessions=2)
        release_retained_upstream_websocket(second, retain=True, response_id="resp_2")

        third = acquire_retained_upstream_websocket(None, FakeRetainedUpstreamWebsocket, max_sessions=2)

        self.assertTrue(third.created)
        self.assertEqual(first.upstream_ws.close_calls, 1)
        self.assertEqual(second.upstream_ws.close_calls, 0)

        release_retained_upstream_websocket(third, retain=True, response_id="resp_3")

    def test_registry_treats_closed_retained_websocket_as_missing_marker(self) -> None:
        created: list[FakeRetainedUpstreamWebsocket] = []

        def factory() -> FakeRetainedUpstreamWebsocket:
            websocket = FakeRetainedUpstreamWebsocket()
            created.append(websocket)
            return websocket

        first = acquire_retained_upstream_websocket(None, factory, max_sessions=2)
        release_retained_upstream_websocket(
            first,
            retain=True,
            response_id="resp_fixed_1",
        )
        first.upstream_ws.closed = True

        with self.assertRaisesRegex(
            ResponsesWebsocketSessionNotFoundError,
            "No retained upstream websocket exists",
        ):
            acquire_retained_upstream_websocket("resp_fixed_1", factory, max_sessions=2)

        self.assertEqual(first.upstream_ws.close_calls, 1)
        self.assertEqual(len(created), 1)


if __name__ == "__main__":
    unittest.main()