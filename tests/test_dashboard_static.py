from __future__ import annotations

import unittest
from html.parser import HTMLParser
from pathlib import Path


STATIC_DIR = Path(__file__).parents[1] / "src" / "execution_monitor" / "static"


class IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "id" and value:
                self.ids.append(value)


class DashboardStaticTests(unittest.TestCase):
    def test_dashboard_ids_are_unique_and_required_regions_exist(self) -> None:
        parser = IdCollector()
        parser.feed((STATIC_DIR / "index.html").read_text(encoding="utf-8"))

        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        for required in {
            "mode-value",
            "connection-value",
            "status-title",
            "phase-value",
            "order-stage-grid",
            "safety-grid",
            "reconciliation-grid",
            "latest-event",
            "latest-event-time",
        }:
            self.assertIn(required, parser.ids)

        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        for phase in {
            "checking_order",
            "sending_order",
            "waiting_for_fill",
            "order_partly_filled",
            "order_fully_filled",
            "reconciled",
        }:
            self.assertIn(f'data-phase="{phase}"', html)

    def test_browser_code_uses_read_only_status_endpoint(self) -> None:
        javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn('fetch("/api/status"', javascript)
        self.assertIn("payload.execution_phase", javascript)
        self.assertIn("payload.latest_event_at", javascript)
        self.assertNotIn('method: "POST"', javascript)
        self.assertNotIn('method: "PUT"', javascript)
        self.assertNotIn('method: "DELETE"', javascript)


if __name__ == "__main__":
    unittest.main()
