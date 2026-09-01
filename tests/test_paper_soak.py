from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from execution_monitor.paper import run_paper_soak


class PaperSoakTests(unittest.TestCase):
    def test_frozen_public_candles_drive_a_reconciled_paper_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_path = root / "candles.csv"
            with data_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["timestamp", "open", "high", "low", "close", "volume"],
                )
                writer.writeheader()
                for index, close in enumerate([100.0, 101.0, 99.0, 102.0, 103.0, 100.0]):
                    writer.writerow(
                        {
                            "timestamp": f"2026-08-29T00:0{index}:00Z",
                            "open": close,
                            "high": close + 1,
                            "low": close - 1,
                            "close": close,
                            "volume": 10 + index,
                        }
                    )

            result = run_paper_soak(
                data_path,
                database_path=root / "paper.db",
                venue_state_path=root / "venue.json",
                output_path=root / "paper-evidence.json",
                trade_every=2,
            )

            self.assertEqual(result["overall_result"], "passed")
            self.assertEqual(result["candles_processed"], 6)
            self.assertEqual(result["orders_completed"], 3)
            self.assertTrue(result["records_match"])
            self.assertTrue((root / "paper-evidence.json").exists())


if __name__ == "__main__":
    unittest.main()
