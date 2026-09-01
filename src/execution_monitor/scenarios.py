from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .baseline import UnsafeBaselineSystem
from .models import Mode, OrderIntent, OrderStage, OverallStatus, utc_now
from .monitor import ExecutionMonitor
from .simulator import SimulatedVenue


def _intent(name: str, quantity: float = 0.50) -> OrderIntent:
    return OrderIntent(name, "BTC-USD", "buy", quantity)


def generate_verification_bundle(output_path: str | Path, *, mode: Mode) -> dict[str, Any]:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    baseline_venue = SimulatedVenue(initial_balance=10_000.0)
    baseline = UnsafeBaselineSystem(baseline_venue)
    baseline.submit_with_retry(_intent("baseline"), reference_price=100.0)
    baseline.record_partial_fill_as_complete(
        "baseline", filled_quantity=0.20, price=100.0
    )
    baseline.disconnect_without_recovery()
    baseline.restart_without_persistence()
    baseline_failures = baseline.detected_violations()

    corrected: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        venue = SimulatedVenue(initial_balance=10_000.0)
        monitor = ExecutionMonitor(root / "duplicate.db", venue, mode=mode)
        first = monitor.submit(_intent("duplicate"), 100.0)
        second = monitor.submit(_intent("duplicate"), 100.0)
        corrected["duplicate_retry"] = {
            "passed": venue.submit_count == 1 and first.venue_order_id == second.venue_order_id,
            "evidence": "One trade request produced one venue order.",
        }
        monitor.close()

        venue = SimulatedVenue(initial_balance=10_000.0)
        monitor = ExecutionMonitor(root / "partial.db", venue, mode=mode)
        monitor.submit(_intent("partial"), 100.0)
        partial = monitor.apply_fill("partial", 0.20, 100.0)
        complete = monitor.apply_fill("partial", 0.30, 101.0)
        corrected["partial_fill"] = {
            "passed": (
                partial.stage == OrderStage.ORDER_PARTLY_FILLED
                and complete.stage == OrderStage.ORDER_FULLY_FILLED
                and monitor.reconcile()["records_match"]
            ),
            "evidence": "Actual fills, position, and balance reconcile.",
        }
        monitor.close()

        venue = SimulatedVenue(initial_balance=10_000.0)
        monitor = ExecutionMonitor(root / "connection.db", venue, mode=mode)
        monitor.submit(_intent("connection"), 100.0)
        venue.disconnect()
        blocked = monitor.reconcile()
        venue.reconnect()
        recovered = monitor.recover_from_venue()
        corrected["disconnect_recovery"] = {
            "passed": (
                blocked["overall_status"] == OverallStatus.BLOCKED.value
                and recovered["overall_status"] == OverallStatus.SAFE.value
            ),
            "evidence": "Disconnect blocks execution; reconnect restores authoritative state.",
        }
        monitor.close()

        venue = SimulatedVenue(initial_balance=10_000.0)
        monitor = ExecutionMonitor(root / "stale.db", venue, mode=mode)
        record = monitor.submit(_intent("stale"), 100.0)
        venue.fill(record.venue_order_id, 0.25, 100.0)
        warning = monitor.reconcile()
        recovered = monitor.recover_from_venue()
        corrected["stale_state_recovery"] = {
            "passed": (
                warning["overall_status"] == OverallStatus.WARNING.value
                and recovered["overall_status"] == OverallStatus.SAFE.value
            ),
            "evidence": "A venue-only fill is detected, then reconciled.",
        }
        monitor.close()

        venue = SimulatedVenue(initial_balance=10_000.0)
        monitor = ExecutionMonitor(root / "outcomes.db", venue, mode=mode)
        venue.reject_next = True
        rejected = monitor.submit(_intent("rejected"), 100.0)
        monitor.submit(_intent("cancelled"), 100.0)
        cancelled = monitor.cancel("cancelled")
        corrected["rejection_and_cancellation"] = {
            "passed": (
                rejected.stage == OrderStage.ORDER_FAILED
                and cancelled.stage == OrderStage.ORDER_CANCELLED
            ),
            "evidence": "Rejected and cancelled orders retain explicit terminal states.",
        }
        monitor.close()

        venue_state = root / "restart-venue.json"
        venue = SimulatedVenue(initial_balance=10_000.0, state_path=venue_state)
        database = root / "restart.db"
        monitor = ExecutionMonitor(database, venue, mode=mode)
        monitor.submit(_intent("restart"), 100.0)
        monitor.apply_fill("restart", 0.20, 100.0)
        monitor.close()
        venue = SimulatedVenue(initial_balance=10_000.0, state_path=venue_state)
        monitor = ExecutionMonitor(database, venue, mode=mode)
        restart_snapshot = monitor.recover_from_venue()
        corrected["restart_recovery"] = {
            "passed": (
                restart_snapshot["overall_status"] == OverallStatus.SAFE.value
                and restart_snapshot["order_stage"]
                == OrderStage.ORDER_PARTLY_FILLED.value
            ),
            "evidence": "Journal and authoritative venue state survive a process restart.",
        }
        monitor.close()

        venue = SimulatedVenue(initial_balance=10_000.0)
        monitor = ExecutionMonitor(
            root / "risk.db", venue, mode=mode, max_order_notional=1_000.0
        )
        blocked_order = monitor.submit(_intent("risk", quantity=20.0), 100.0)
        corrected["risk_limit"] = {
            "passed": (
                blocked_order.stage == OrderStage.ORDER_FAILED and venue.submit_count == 0
            ),
            "evidence": "Oversized trade requests are blocked before the venue.",
        }
        monitor.close()

    bundle = {
        "generated_at": utc_now(),
        "mode": mode.value,
        "baseline_failures_detected": baseline_failures,
        "corrected_scenarios": corrected,
        "overall_result": (
            "passed"
            if all(baseline_failures.values())
            and all(item["passed"] for item in corrected.values())
            else "failed"
        ),
        "limitations": [
            "The venue is deterministic and contains no real account data.",
            "This verifies execution reliability, not trading profitability.",
            "No testnet or live venue is included in version one.",
        ],
    }
    output_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    return bundle
