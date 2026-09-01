from __future__ import annotations

from .models import OrderIntent
from .simulator import SimulatedVenue


class UnsafeBaselineSystem:
    """Small intentionally flawed system used only to preserve before-state evidence."""

    def __init__(self, venue: SimulatedVenue) -> None:
        self.venue = venue
        self._intents: dict[str, OrderIntent] = {}
        self._partial_fill_mismatch = False
        self._state_lost = False

    def submit_with_retry(self, intent: OrderIntent, reference_price: float) -> None:
        del reference_price
        self._intents[intent.intent_id] = intent
        for attempt in (1, 2):
            unsafe_intent = OrderIntent(
                f"{intent.intent_id}-attempt-{attempt}",
                intent.symbol,
                intent.side,
                intent.quantity,
            )
            self.venue.submit(unsafe_intent)

    def record_partial_fill_as_complete(
        self,
        intent_id: str,
        *,
        filled_quantity: float,
        price: float,
    ) -> None:
        first_order = self.venue.snapshot()["orders"][0]
        self.venue.fill(first_order["venue_order_id"], filled_quantity, price)
        intended = self._intents[intent_id]
        self._partial_fill_mismatch = filled_quantity < intended.quantity

    def disconnect_without_recovery(self) -> None:
        self.venue.disconnect()

    def restart_without_persistence(self) -> None:
        self._intents.clear()
        self._state_lost = True

    def detected_violations(self) -> dict[str, bool]:
        return {
            "duplicate_order": self.venue.submit_count > 1,
            "partial_fill_mismatch": self._partial_fill_mismatch,
            "connection_not_recovered": not self.venue.connected,
            "state_lost_after_restart": self._state_lost and not self._intents,
        }
