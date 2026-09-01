from __future__ import annotations

import unittest

from execution_monitor.baseline import UnsafeBaselineSystem
from execution_monitor.models import OrderIntent
from execution_monitor.simulator import SimulatedVenue


class BaselineFailureEvidenceTests(unittest.TestCase):
    def test_unreliable_baseline_exposes_expected_failures(self) -> None:
        venue = SimulatedVenue()
        baseline = UnsafeBaselineSystem(venue)
        intent = OrderIntent("baseline-1", "BTC-USD", "buy", 0.50)

        baseline.submit_with_retry(intent, reference_price=100.0)
        baseline.record_partial_fill_as_complete(intent.intent_id, filled_quantity=0.20, price=100.0)
        baseline.disconnect_without_recovery()
        baseline.restart_without_persistence()

        violations = baseline.detected_violations()
        self.assertTrue(violations["duplicate_order"])
        self.assertTrue(violations["partial_fill_mismatch"])
        self.assertTrue(violations["connection_not_recovered"])
        self.assertTrue(violations["state_lost_after_restart"])


if __name__ == "__main__":
    unittest.main()
