from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from execution_monitor.models import Mode
from execution_monitor.scenarios import generate_verification_bundle


class VerificationBundleTests(unittest.TestCase):
    def test_bundle_contains_baseline_failures_and_corrected_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "verification.json"
            bundle = generate_verification_bundle(output_path, mode=Mode.SIMULATION)

            self.assertTrue(output_path.exists())
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), bundle)
            self.assertTrue(all(bundle["baseline_failures_detected"].values()))
            self.assertTrue(all(result["passed"] for result in bundle["corrected_scenarios"].values()))
            self.assertEqual(bundle["overall_result"], "passed")


if __name__ == "__main__":
    unittest.main()
