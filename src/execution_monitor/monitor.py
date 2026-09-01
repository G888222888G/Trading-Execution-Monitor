from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from .models import (
    Mode,
    OrderIntent,
    OrderRecord,
    OrderStage,
    OverallStatus,
    utc_now,
)
from .simulator import SimulatedVenue, VenueDisconnected, VenueRejected
from .store import JournalStore


class ExecutionMonitor:
    """Guards order submission and keeps local execution state authoritative and inspectable."""

    def __init__(
        self,
        database_path: str | Path,
        venue: SimulatedVenue,
        *,
        mode: Mode = Mode.SIMULATION,
        max_order_notional: float = 10_000.0,
    ) -> None:
        self.store = JournalStore(database_path)
        self.venue = venue
        self.mode = mode
        self.max_order_notional = float(max_order_notional)
        self._lock = threading.RLock()
        self._closed = False

        run_id = self.store.get_metadata("run_id")
        if not run_id:
            run_id = uuid.uuid4().hex[:12]
            self.store.set_metadata("run_id", run_id)
        self.run_id = run_id

        self.store.set_metadata("mode", mode.value)
        self._emergency_stop_active = self.store.get_metadata("emergency_stop") == "true"
        if not self.store.recent_events(limit=1):
            self.store.add_event("Execution Monitor is ready.", kind="system")

    def begin_submission(self, intent: OrderIntent, reference_price: float) -> OrderRecord:
        with self._lock:
            existing = self.store.get_order(intent.intent_id)
            if existing is not None:
                self.store.add_event(
                    "Duplicate trade request blocked.",
                    kind="safety",
                    payload={"intent_id": intent.intent_id},
                )
                return existing

            record = OrderRecord(
                intent_id=intent.intent_id,
                venue_order_id="",
                symbol=intent.symbol,
                side=intent.normalized_side(),
                requested_quantity=float(intent.quantity),
                filled_quantity=0.0,
                average_fill_price=0.0,
                stage=OrderStage.CHECKING_ORDER,
                updated_at=utc_now(),
            )
            self.store.save_order(record)
            self.store.add_event(
                "Checking trade request.",
                payload={"intent_id": intent.intent_id},
            )

            failure = self._validation_failure(intent, reference_price)
            if failure:
                record.stage = OrderStage.ORDER_FAILED
                record.updated_at = utc_now()
                self.store.save_order(record)
                self.store.add_event(failure, kind="blocked", payload={"intent_id": intent.intent_id})
            return record

    def _validation_failure(self, intent: OrderIntent, reference_price: float) -> str | None:
        if self._emergency_stop_active:
            return "Order blocked because the emergency stop is active."
        if intent.normalized_side() not in {"buy", "sell"}:
            return "Order blocked because the side must be buy or sell."
        if intent.quantity <= 0 or reference_price <= 0:
            return "Order blocked because quantity and price must be positive."
        if intent.quantity * reference_price > self.max_order_notional:
            return "Order blocked because it exceeds the risk limit."
        if not self.venue.connected:
            return "Order blocked because the venue connection is unavailable."
        return None

    def prepare_dispatch(self, intent_id: str) -> OrderRecord:
        """Persist the real sending state before the venue call begins."""
        with self._lock:
            record = self._require_order(intent_id)
            if record.stage == OrderStage.ORDER_FAILED:
                return record
            if record.venue_order_id:
                return record

            record.stage = OrderStage.SENDING_ORDER
            record.updated_at = utc_now()
            self.store.save_order(record)
            self.store.add_event(
                "Sending approved trade request to the venue.",
                payload={"intent_id": intent_id},
            )
            return record

    def complete_dispatch(self, intent_id: str) -> OrderRecord:
        """Send a prepared request and persist the venue's acknowledgement."""
        with self._lock:
            record = self._require_order(intent_id)
            if record.stage == OrderStage.ORDER_FAILED:
                return record
            if record.venue_order_id:
                return record
            if record.stage != OrderStage.SENDING_ORDER:
                record = self.prepare_dispatch(intent_id)

            try:
                venue_order = self.venue.submit(
                    OrderIntent(
                        record.intent_id,
                        record.symbol,
                        record.side,
                        record.requested_quantity,
                    )
                )
            except VenueDisconnected:
                record.stage = OrderStage.ORDER_FAILED
                record.updated_at = utc_now()
                self.store.save_order(record)
                self.store.add_event(
                    "Order blocked because the venue connection is unavailable.",
                    kind="blocked",
                    payload={"intent_id": intent_id},
                )
                return record
            except VenueRejected:
                record.stage = OrderStage.ORDER_FAILED
                record.updated_at = utc_now()
                self.store.save_order(record)
                self.store.add_event(
                    "Order rejected by the venue.",
                    kind="blocked",
                    payload={"intent_id": intent_id},
                )
                return record

            record.venue_order_id = venue_order.venue_order_id
            record.stage = OrderStage.WAITING_FOR_FILL
            record.updated_at = utc_now()
            self.store.save_order(record)
            self.store.add_event(
                f"Order accepted by the simulator; waiting for a fill.",
                payload={"intent_id": intent_id, "venue_order_id": venue_order.venue_order_id},
            )
            return record

    def dispatch(self, intent_id: str) -> OrderRecord:
        with self._lock:
            record = self.prepare_dispatch(intent_id)
            if record.stage == OrderStage.ORDER_FAILED or record.venue_order_id:
                return record
            return self.complete_dispatch(intent_id)

    def submit(self, intent: OrderIntent, reference_price: float) -> OrderRecord:
        record = self.begin_submission(intent, reference_price)
        if record.stage == OrderStage.ORDER_FAILED or record.venue_order_id:
            return record
        return self.dispatch(intent.intent_id)

    def apply_fill(self, intent_id: str, quantity: float, price: float) -> OrderRecord:
        with self._lock:
            record = self._require_order(intent_id)
            if not record.venue_order_id:
                raise ValueError("The order was not accepted by the venue.")
            venue_order = self.venue.fill(record.venue_order_id, quantity, price)
            updated = self._record_from_venue(venue_order.to_dict())
            self.store.save_order(updated)
            message = (
                "Order fully filled."
                if updated.stage == OrderStage.ORDER_FULLY_FILLED
                else "Order partially filled; waiting for the remainder."
            )
            self.store.add_event(message, payload={"intent_id": intent_id})
            return updated

    def cancel(self, intent_id: str) -> OrderRecord:
        with self._lock:
            record = self._require_order(intent_id)
            if not record.venue_order_id:
                raise ValueError("The order was not accepted by the venue.")
            venue_order = self.venue.cancel(record.venue_order_id)
            updated = self._record_from_venue(venue_order.to_dict())
            self.store.save_order(updated)
            self.store.add_event("Order cancellation confirmed.", payload={"intent_id": intent_id})
            return updated

    def activate_emergency_stop(self, reason: str) -> None:
        with self._lock:
            self._emergency_stop_active = True
            self.store.set_metadata("emergency_stop", "true")
            self.store.add_event(
                "Emergency stop activated.",
                kind="blocked",
                payload={"reason": reason},
            )

    def clear_emergency_stop_for_test(self) -> None:
        """Test/demo-only reset; the browser intentionally has no route to call it."""
        with self._lock:
            self._emergency_stop_active = False
            self.store.set_metadata("emergency_stop", "false")
            self.store.add_event("Emergency stop cleared in the local test environment.", kind="system")

    def reset_automatic_demo(self) -> None:
        """Bound the disposable browser demonstration without exposing a web action."""
        with self._lock:
            self.venue.reset_for_demo()
            self.store.reset_demo_data()
            self._emergency_stop_active = False
            self.store.set_metadata("emergency_stop", "false")
            self.store.add_event(
                "Automatic demonstration reset to a clean simulated state.",
                kind="system",
            )

    def reconcile(self) -> dict[str, Any]:
        with self._lock:
            snapshot = self._build_snapshot()
            if snapshot["records_match"]:
                self.store.add_event("Local records match the venue.", kind="reconciliation")
            elif snapshot["safety_checks"]["connection_healthy"]:
                self.store.add_event(
                    "Warning: local records do not match the venue.",
                    kind="warning",
                )
            else:
                self.store.add_event(
                    "Reconciliation paused because the venue connection is unavailable.",
                    kind="blocked",
                )
            return self._build_snapshot()

    def recover_from_venue(self) -> dict[str, Any]:
        with self._lock:
            try:
                venue_snapshot = self.venue.snapshot()
            except VenueDisconnected:
                self.store.add_event(
                    "Recovery blocked because the venue connection is unavailable.",
                    kind="blocked",
                )
                return self._build_snapshot()

            for venue_order in venue_snapshot["orders"]:
                self.store.save_order(self._record_from_venue(venue_order))
            self.store.add_event(
                "Recovered authoritative order state from the venue.",
                kind="recovery",
            )
            return self._build_snapshot()

    def _record_from_venue(self, venue_order: dict[str, Any]) -> OrderRecord:
        return OrderRecord(
            intent_id=venue_order["intent_id"],
            venue_order_id=venue_order["venue_order_id"],
            symbol=venue_order["symbol"],
            side=venue_order["side"],
            requested_quantity=float(venue_order["requested_quantity"]),
            filled_quantity=float(venue_order["filled_quantity"]),
            average_fill_price=float(venue_order["average_fill_price"]),
            stage=OrderStage(venue_order["stage"]),
            updated_at=utc_now(),
        )

    def _require_order(self, intent_id: str) -> OrderRecord:
        order = self.store.get_order(intent_id)
        if order is None:
            raise KeyError(f"Unknown intent: {intent_id}")
        return order

    @staticmethod
    def _close_enough(left: float, right: float) -> bool:
        return abs(left - right) <= 1e-8

    def _reconciliation_checks(self) -> dict[str, bool]:
        if not self.venue.connected:
            return {
                "orders_match": False,
                "fills_match": False,
                "position_matches": False,
                "balance_matches": False,
            }

        venue_snapshot = self.venue.snapshot()
        venue_orders = {item["venue_order_id"]: item for item in venue_snapshot["orders"]}
        local_orders = {
            item.venue_order_id: item
            for item in self.store.list_orders()
            if item.venue_order_id
        }

        orders_match = set(local_orders) == set(venue_orders)
        fills_match = orders_match
        for venue_id, local in local_orders.items():
            venue = venue_orders.get(venue_id)
            if venue is None:
                fills_match = False
                continue
            if (
                venue["intent_id"] != local.intent_id
                or venue["symbol"] != local.symbol
                or venue["side"] != local.side
                or not self._close_enough(float(venue["requested_quantity"]), local.requested_quantity)
            ):
                orders_match = False
            if (
                not self._close_enough(float(venue["filled_quantity"]), local.filled_quantity)
                or venue["stage"] != local.stage.value
            ):
                fills_match = False

        local_positions: dict[str, float] = {}
        local_balance = self.venue.initial_balance
        for order in local_orders.values():
            direction = 1.0 if order.side == "buy" else -1.0
            local_positions[order.symbol] = (
                local_positions.get(order.symbol, 0.0) + direction * order.filled_quantity
            )
            local_balance -= direction * order.filled_quantity * order.average_fill_price

        all_symbols = set(local_positions) | set(venue_snapshot["positions"])
        position_matches = all(
            self._close_enough(
                local_positions.get(symbol, 0.0),
                float(venue_snapshot["positions"].get(symbol, 0.0)),
            )
            for symbol in all_symbols
        )
        balance_matches = self._close_enough(local_balance, float(venue_snapshot["balance"]))

        return {
            "orders_match": orders_match,
            "fills_match": fills_match,
            "position_matches": position_matches,
            "balance_matches": balance_matches,
        }

    def _build_snapshot(self) -> dict[str, Any]:
        latest_order = self.store.latest_order()
        latest_events = self.store.recent_events(limit=1)
        latest_event = latest_events[0] if latest_events else None
        reconciliation = self._reconciliation_checks()
        records_match = all(reconciliation.values())
        safety_checks = {
            "duplicate_protection": True,
            "risk_limit_active": True,
            "connection_healthy": bool(self.venue.connected),
            "emergency_stop_ready": not self._emergency_stop_active,
        }

        if not self.venue.connected or self._emergency_stop_active:
            overall = OverallStatus.BLOCKED
        elif latest_order and latest_order.stage == OrderStage.ORDER_FAILED:
            overall = OverallStatus.BLOCKED
        elif not records_match:
            overall = OverallStatus.WARNING
        else:
            overall = OverallStatus.SAFE

        if not self.venue.connected:
            reason = "The venue connection is unavailable."
        elif self._emergency_stop_active:
            reason = "The emergency stop is active."
        elif latest_order and latest_order.stage == OrderStage.ORDER_FAILED:
            reason = "The latest trade request was blocked or failed."
        elif not records_match:
            reason = "Local records do not match the venue."
        else:
            reason = "Safety checks passed and records match."

        order_stage = latest_order.stage.value if latest_order else OrderStage.NO_ACTIVE_ORDER.value
        execution_phase = order_stage
        if (
            latest_order
            and latest_order.stage == OrderStage.ORDER_FULLY_FILLED
            and records_match
            and latest_event
            and latest_event["kind"] in {"reconciliation", "recovery"}
        ):
            execution_phase = "reconciled"

        return {
            "run_id": self.run_id,
            "generated_at": utc_now(),
            "mode": self.mode.value,
            "overall_status": overall.value,
            "status_reason": reason,
            "order_stage": order_stage,
            "execution_phase": execution_phase,
            "safety_checks": safety_checks,
            "reconciliation": reconciliation,
            "records_match": records_match,
            "latest_event": latest_event["message"] if latest_event else "Execution Monitor is ready.",
            "latest_event_at": latest_event["created_at"] if latest_event else None,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._build_snapshot()

    def events(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.store.recent_events(limit=limit)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self.store.close()
            self._closed = True
