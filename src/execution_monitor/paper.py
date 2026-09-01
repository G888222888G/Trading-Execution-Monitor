from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .models import Mode, OrderIntent, OrderStage, utc_now
from .monitor import ExecutionMonitor
from .simulator import SimulatedVenue


def run_paper_soak(
    data_path: str | Path,
    *,
    database_path: str | Path,
    venue_state_path: str | Path,
    output_path: str | Path,
    trade_every: int = 6,
) -> dict[str, Any]:
    data_path = Path(data_path)
    output_path = Path(output_path)
    if trade_every < 1:
        raise ValueError("trade_every must be at least one candle.")

    with data_path.open("r", encoding="utf-8", newline="") as handle:
        candles = list(csv.DictReader(handle))
    if len(candles) < 2:
        raise ValueError("Paper verification requires at least two candles.")

    venue = SimulatedVenue(initial_balance=100_000.0, state_path=venue_state_path)
    monitor = ExecutionMonitor(
        database_path,
        venue,
        mode=Mode.PAPER,
        max_order_notional=1_000.0,
    )
    monitor.recover_from_venue()

    completed = 0
    reconciled_after_each_order = True
    for index, candle in enumerate(candles):
        if index % trade_every != 0:
            continue
        close_price = float(candle["close"])
        side = "buy" if completed % 2 == 0 else "sell"
        timestamp_key = candle["timestamp"].replace(":", "").replace("-", "")
        intent_id = f"paper-{timestamp_key}-{side}"
        order = monitor.submit(
            OrderIntent(intent_id, "BTC-USD", side, 0.001),
            reference_price=close_price,
        )
        if order.stage not in {
            OrderStage.ORDER_FULLY_FILLED,
            OrderStage.ORDER_CANCELLED,
            OrderStage.ORDER_FAILED,
        }:
            remaining = order.requested_quantity - order.filled_quantity
            monitor.apply_fill(intent_id, remaining, close_price)
        snapshot = monitor.reconcile()
        reconciled_after_each_order &= snapshot["records_match"]
        completed += 1

    final = monitor.snapshot()
    result = {
        "generated_at": utc_now(),
        "mode": Mode.PAPER.value,
        "data_file": data_path.name,
        "data_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "candle_start": candles[0]["timestamp"],
        "candle_end": candles[-1]["timestamp"],
        "candles_processed": len(candles),
        "orders_completed": completed,
        "records_match": bool(final["records_match"] and reconciled_after_each_order),
        "overall_result": (
            "passed"
            if completed > 0 and final["records_match"] and reconciled_after_each_order
            else "failed"
        ),
        "limitations": [
            "The strategy is a deterministic exercise fixture, not a trading recommendation.",
            "Orders are filled by the local paper venue at recorded candle closes.",
            "No credentials, account data, or funded execution are used.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    monitor.close()
    return result
