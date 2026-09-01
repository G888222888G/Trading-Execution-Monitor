from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from execution_monitor.models import Mode, OrderIntent
from execution_monitor.monitor import ExecutionMonitor
from execution_monitor.server import build_server
from execution_monitor.simulator import SimulatedVenue


class ReadOnlyServerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.monitor = ExecutionMonitor(
            Path(self.temp_dir.name) / "server.db",
            SimulatedVenue(),
            mode=Mode.SIMULATION,
        )
        self.monitor.submit(OrderIntent("server-1", "BTC-USD", "buy", 0.1), 100.0)
        self.server = build_server(self.monitor, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.monitor.close()
        self.temp_dir.cleanup()

    def get_text(self, path: str) -> str:
        with urllib.request.urlopen(self.base_url + path, timeout=2) as response:
            self.assertEqual(response.status, 200)
            return response.read().decode("utf-8")

    def test_status_api_exposes_only_readable_monitor_state(self) -> None:
        payload = json.loads(self.get_text("/api/status"))
        self.assertEqual(
            set(payload),
            {
                "mode",
                "overall_status",
                "status_reason",
                "order_stage",
                "execution_phase",
                "safety_checks",
                "reconciliation",
                "records_match",
                "latest_event",
                "latest_event_at",
            },
        )
        self.assertEqual(payload["mode"], Mode.SIMULATION.value)
        self.assertIn(payload["overall_status"], {"safe", "warning", "blocked"})
        self.assertIn("safety_checks", payload)
        self.assertIn("reconciliation", payload)
        self.assertIn("latest_event", payload)
        self.assertIn("latest_event_at", payload)
        self.assertIn("execution_phase", payload)

        def keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value).union(*(keys(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(item) for item in value))
            return set()

        self.assertTrue(
            {
                "run_id",
                "generated_at",
                "intent_id",
                "venue_order_id",
                "requested_quantity",
                "filled_quantity",
                "average_fill_price",
                "price",
                "quantity",
                "balance",
                "account_id",
                "wallet",
                "payload",
            }.isdisjoint(keys(payload))
        )
        encoded = json.dumps(payload)
        self.assertIsNone(re.search(r"demo-\d", encoded))
        self.assertIsNone(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", encoded))
        self.assertIsNone(re.search(r"[A-Z]:\\\\Users\\\\", encoded, re.IGNORECASE))

    def test_events_endpoint_is_not_public(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(self.base_url + "/api/events?limit=100", timeout=2)
        self.assertEqual(context.exception.code, 404)

    def test_dashboard_is_read_only(self) -> None:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                request = urllib.request.Request(
                    self.base_url + "/api/status",
                    method=method,
                    data=b"{}",
                )
                with self.assertRaises(urllib.error.HTTPError) as context:
                    urllib.request.urlopen(request, timeout=2)
                self.assertEqual(context.exception.code, 405)

    def test_dashboard_contains_no_action_controls(self) -> None:
        html = self.get_text("/").lower()
        self.assertIn("execution monitor", html)
        self.assertNotIn("<button", html)
        self.assertNotIn("<form", html)
        self.assertNotIn("place order", html)

    def test_refresh_does_not_change_underlying_order_state(self) -> None:
        first = json.loads(self.get_text("/api/status"))
        second = json.loads(self.get_text("/api/status"))
        self.assertEqual(first["order_stage"], second["order_stage"])
        self.assertEqual(first["records_match"], second["records_match"])

    def test_non_local_bind_requires_explicit_container_boundary(self) -> None:
        previous = os.environ.pop("EXECUTION_MONITOR_ALLOW_CONTAINER_BIND", None)
        try:
            with self.assertRaises(ValueError):
                build_server(self.monitor, host="0.0.0.0", port=0)
        finally:
            if previous is not None:
                os.environ["EXECUTION_MONITOR_ALLOW_CONTAINER_BIND"] = previous


if __name__ == "__main__":
    unittest.main()
