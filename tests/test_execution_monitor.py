from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from execution_monitor.models import Mode, OrderIntent, OrderStage, OverallStatus
from execution_monitor.monitor import ExecutionMonitor
from execution_monitor.simulator import SimulatedVenue


class ExecutionMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "monitor.db"
        self.venue = SimulatedVenue(initial_balance=10_000.0)
        self.monitor = ExecutionMonitor(
            self.db_path,
            self.venue,
            mode=Mode.SIMULATION,
            max_order_notional=1_000.0,
        )

    def tearDown(self) -> None:
        self.monitor.close()
        self.temp_dir.cleanup()

    @staticmethod
    def intent(intent_id: str = "intent-1", quantity: float = 0.50) -> OrderIntent:
        return OrderIntent(intent_id, "BTC-USD", "buy", quantity)

    def test_duplicate_intent_is_not_submitted_twice(self) -> None:
        first = self.monitor.submit(self.intent(), reference_price=100.0)
        second = self.monitor.submit(self.intent(), reference_price=100.0)

        self.assertEqual(first.venue_order_id, second.venue_order_id)
        self.assertEqual(self.venue.submit_count, 1)
        self.assertIn("duplicate", self.monitor.snapshot()["latest_event"].lower())

    def test_risk_limit_blocks_order_before_venue(self) -> None:
        record = self.monitor.submit(self.intent(quantity=20.0), reference_price=100.0)
        snapshot = self.monitor.snapshot()

        self.assertEqual(record.stage, OrderStage.ORDER_FAILED)
        self.assertEqual(self.venue.submit_count, 0)
        self.assertEqual(snapshot["overall_status"], OverallStatus.BLOCKED.value)
        self.assertIn("risk limit", snapshot["latest_event"].lower())

    def test_partial_fill_then_full_fill_tracks_real_quantity(self) -> None:
        self.monitor.submit(self.intent(), reference_price=100.0)
        partial = self.monitor.apply_fill("intent-1", 0.20, 100.0)
        self.assertEqual(partial.stage, OrderStage.ORDER_PARTLY_FILLED)
        self.assertAlmostEqual(partial.filled_quantity, 0.20)

        complete = self.monitor.apply_fill("intent-1", 0.30, 101.0)
        self.assertEqual(complete.stage, OrderStage.ORDER_FULLY_FILLED)
        self.assertAlmostEqual(complete.filled_quantity, 0.50)
        self.assertTrue(self.monitor.reconcile()["records_match"])

    def test_rejection_and_cancellation_are_explicit_states(self) -> None:
        self.venue.reject_next = True
        rejected = self.monitor.submit(self.intent("rejected"), reference_price=100.0)
        self.assertEqual(rejected.stage, OrderStage.ORDER_FAILED)

        self.monitor.submit(self.intent("cancelled"), reference_price=100.0)
        cancelled = self.monitor.cancel("cancelled")
        self.assertEqual(cancelled.stage, OrderStage.ORDER_CANCELLED)

    def test_disconnect_blocks_then_reconnect_recovers(self) -> None:
        self.monitor.submit(self.intent(), reference_price=100.0)
        self.venue.disconnect()
        blocked = self.monitor.reconcile()
        self.assertEqual(blocked["overall_status"], OverallStatus.BLOCKED.value)

        self.venue.reconnect()
        recovered = self.monitor.reconcile()
        self.assertEqual(recovered["overall_status"], OverallStatus.SAFE.value)
        self.assertTrue(recovered["records_match"])

    def test_stale_local_state_is_detected_and_recovered(self) -> None:
        record = self.monitor.submit(self.intent(), reference_price=100.0)
        self.venue.fill(record.venue_order_id, 0.25, 100.0)

        warning = self.monitor.reconcile()
        self.assertEqual(warning["overall_status"], OverallStatus.WARNING.value)
        self.assertFalse(warning["reconciliation"]["fills_match"])

        recovered = self.monitor.recover_from_venue()
        self.assertEqual(recovered["overall_status"], OverallStatus.SAFE.value)
        self.assertTrue(recovered["records_match"])
        self.assertEqual(recovered["order_stage"], OrderStage.ORDER_PARTLY_FILLED.value)

    def test_restart_loads_persisted_order_state(self) -> None:
        self.monitor.submit(self.intent(), reference_price=100.0)
        self.monitor.apply_fill("intent-1", 0.20, 100.0)
        self.monitor.close()

        self.monitor = ExecutionMonitor(
            self.db_path,
            self.venue,
            mode=Mode.SIMULATION,
            max_order_notional=1_000.0,
        )
        snapshot = self.monitor.reconcile()

        self.assertEqual(snapshot["order_stage"], OrderStage.ORDER_PARTLY_FILLED.value)
        self.assertTrue(snapshot["records_match"])

    def test_full_process_restart_recovers_new_monitor_and_new_venue_instances(self) -> None:
        self.monitor.close()
        venue_state = Path(self.temp_dir.name) / "venue.json"
        venue = SimulatedVenue(initial_balance=10_000.0, state_path=venue_state)
        self.monitor = ExecutionMonitor(
            self.db_path,
            venue,
            mode=Mode.SIMULATION,
            max_order_notional=1_000.0,
        )
        self.monitor.submit(self.intent(), reference_price=100.0)
        self.monitor.apply_fill("intent-1", 0.20, 100.0)
        self.monitor.close()

        restarted_venue = SimulatedVenue(initial_balance=10_000.0, state_path=venue_state)
        self.monitor = ExecutionMonitor(
            self.db_path,
            restarted_venue,
            mode=Mode.SIMULATION,
            max_order_notional=1_000.0,
        )
        snapshot = self.monitor.recover_from_venue()

        self.assertEqual(snapshot["overall_status"], OverallStatus.SAFE.value)
        self.assertEqual(snapshot["order_stage"], OrderStage.ORDER_PARTLY_FILLED.value)
        self.assertTrue(snapshot["records_match"])

    def test_emergency_stop_blocks_new_orders(self) -> None:
        self.monitor.activate_emergency_stop("operator test")
        record = self.monitor.submit(self.intent(), reference_price=100.0)

        self.assertEqual(record.stage, OrderStage.ORDER_FAILED)
        self.assertEqual(self.venue.submit_count, 0)
        self.assertEqual(self.monitor.snapshot()["overall_status"], OverallStatus.BLOCKED.value)


if __name__ == "__main__":
    unittest.main()
