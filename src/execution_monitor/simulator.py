from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .models import OrderIntent, OrderStage, VenueOrder


class VenueDisconnected(RuntimeError):
    pass


class VenueRejected(RuntimeError):
    pass


class SimulatedVenue:
    """Deterministic exchange stand-in with optional durable authoritative state."""

    def __init__(
        self,
        *,
        initial_balance: float = 100_000.0,
        state_path: str | Path | None = None,
    ) -> None:
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.state_path = Path(state_path) if state_path else None
        self.connected = True
        self.reject_next = False
        self.submit_count = 0
        self._counter = 0
        self._orders: dict[str, VenueOrder] = {}
        self._positions: dict[str, float] = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if not self.state_path or not self.state_path.exists():
            return
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.balance = float(payload["balance"])
        self.connected = bool(payload.get("connected", True))
        self.submit_count = int(payload.get("submit_count", 0))
        self._counter = int(payload.get("counter", 0))
        self._positions = {key: float(value) for key, value in payload.get("positions", {}).items()}
        self._orders = {
            item["venue_order_id"]: VenueOrder(
                intent_id=item["intent_id"],
                venue_order_id=item["venue_order_id"],
                symbol=item["symbol"],
                side=item["side"],
                requested_quantity=float(item["requested_quantity"]),
                filled_quantity=float(item["filled_quantity"]),
                average_fill_price=float(item["average_fill_price"]),
                stage=OrderStage(item["stage"]),
            )
            for item in payload.get("orders", [])
        }

    def _persist(self) -> None:
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "balance": self.balance,
            "connected": self.connected,
            "submit_count": self.submit_count,
            "counter": self._counter,
            "positions": self._positions,
            "orders": [order.to_dict() for order in self._orders.values()],
        }
        self.state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def submit(self, intent: OrderIntent) -> VenueOrder:
        with self._lock:
            if not self.connected:
                raise VenueDisconnected("The simulated venue is disconnected.")
            if self.reject_next:
                self.reject_next = False
                self._persist()
                raise VenueRejected("The simulated venue rejected the order.")
            self._counter += 1
            self.submit_count += 1
            venue_order_id = f"SIM-{self._counter:05d}"
            order = VenueOrder(
                intent_id=intent.intent_id,
                venue_order_id=venue_order_id,
                symbol=intent.symbol,
                side=intent.normalized_side(),
                requested_quantity=float(intent.quantity),
            )
            self._orders[venue_order_id] = order
            self._persist()
            return self._copy(order)

    def fill(self, venue_order_id: str, quantity: float, price: float) -> VenueOrder:
        with self._lock:
            if not self.connected:
                raise VenueDisconnected("The simulated venue is disconnected.")
            order = self._orders[venue_order_id]
            quantity = float(quantity)
            price = float(price)
            if quantity <= 0:
                raise ValueError("Fill quantity must be positive.")
            remaining = order.requested_quantity - order.filled_quantity
            if quantity > remaining + 1e-9:
                raise ValueError("Fill exceeds the remaining order quantity.")

            previous_notional = order.filled_quantity * order.average_fill_price
            order.filled_quantity += quantity
            order.average_fill_price = (
                previous_notional + quantity * price
            ) / order.filled_quantity
            order.stage = (
                OrderStage.ORDER_FULLY_FILLED
                if abs(order.filled_quantity - order.requested_quantity) <= 1e-9
                else OrderStage.ORDER_PARTLY_FILLED
            )

            direction = 1.0 if order.side == "buy" else -1.0
            self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) + direction * quantity
            self.balance -= direction * quantity * price
            self._persist()
            return self._copy(order)

    def cancel(self, venue_order_id: str) -> VenueOrder:
        with self._lock:
            if not self.connected:
                raise VenueDisconnected("The simulated venue is disconnected.")
            order = self._orders[venue_order_id]
            if order.stage != OrderStage.ORDER_FULLY_FILLED:
                order.stage = OrderStage.ORDER_CANCELLED
            self._persist()
            return self._copy(order)

    def disconnect(self) -> None:
        with self._lock:
            self.connected = False
            self._persist()

    def reconnect(self) -> None:
        with self._lock:
            self.connected = True
            self._persist()

    def reset_for_demo(self) -> None:
        """Reset only the disposable automatic demonstration venue."""
        with self._lock:
            self.balance = self.initial_balance
            self.connected = True
            self.reject_next = False
            self.submit_count = 0
            self._counter = 0
            self._orders.clear()
            self._positions.clear()
            self._persist()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if not self.connected:
                raise VenueDisconnected("The simulated venue is disconnected.")
            return {
                "orders": [self._copy(order).to_dict() for order in self._orders.values()],
                "positions": dict(self._positions),
                "balance": self.balance,
            }

    @staticmethod
    def _copy(order: VenueOrder) -> VenueOrder:
        return VenueOrder(
            intent_id=order.intent_id,
            venue_order_id=order.venue_order_id,
            symbol=order.symbol,
            side=order.side,
            requested_quantity=order.requested_quantity,
            filled_quantity=order.filled_quantity,
            average_fill_price=order.average_fill_price,
            stage=order.stage,
        )
