from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from execution_monitor.demo import DemoLoop
from execution_monitor.models import Mode, OrderStage, OverallStatus
from execution_monitor.monitor import ExecutionMonitor
from execution_monitor.simulator import SimulatedVenue


class DemoLoopTests(unittest.TestCase):
    def test_one_visible_cycle_warns_blocks_and_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = ExecutionMonitor(
                Path(temp_dir) / "demo.db",
                SimulatedVenue(),
                mode=Mode.SIMULATION,
            )
            try:
                demo = DemoLoop(monitor, delay=0.001)

                self.assertTrue(demo.run_cycle())
                self.assertEqual(
                    demo.status_trace,
                    [
                        OverallStatus.SAFE.value,
                        OverallStatus.SAFE.value,
                        OverallStatus.SAFE.value,
                        OverallStatus.SAFE.value,
                        OverallStatus.WARNING.value,
                        OverallStatus.SAFE.value,
                        OverallStatus.SAFE.value,
                        OverallStatus.SAFE.value,
                        OverallStatus.BLOCKED.value,
                        OverallStatus.SAFE.value,
                    ],
                )
                self.assertEqual(
                    demo.phase_trace,
                    [
                        OrderStage.NO_ACTIVE_ORDER.value,
                        OrderStage.CHECKING_ORDER.value,
                        OrderStage.SENDING_ORDER.value,
                        OrderStage.WAITING_FOR_FILL.value,
                        OrderStage.WAITING_FOR_FILL.value,
                        OrderStage.ORDER_PARTLY_FILLED.value,
                        OrderStage.ORDER_FULLY_FILLED.value,
                        "reconciled",
                        OrderStage.ORDER_FULLY_FILLED.value,
                        "reconciled",
                    ],
                )
                self.assertTrue(monitor.snapshot()["records_match"])
                self.assertEqual(
                    monitor.snapshot()["overall_status"],
                    OverallStatus.SAFE.value,
                )
            finally:
                monitor.close()

    def test_automatic_demo_history_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = ExecutionMonitor(
                Path(temp_dir) / "bounded.db",
                SimulatedVenue(state_path=Path(temp_dir) / "bounded-venue.json"),
                mode=Mode.SIMULATION,
            )
            try:
                demo = DemoLoop(monitor, delay=0.001, max_cycles=1)

                self.assertTrue(demo.run_cycle())
                self.assertTrue(demo.run_cycle())

                self.assertEqual(len(monitor.store.list_orders()), 1)
                self.assertIn(
                    "automatic demonstration reset",
                    " ".join(event["message"].lower() for event in monitor.events(limit=100)),
                )
            finally:
                monitor.close()


if __name__ == "__main__":
    unittest.main()
