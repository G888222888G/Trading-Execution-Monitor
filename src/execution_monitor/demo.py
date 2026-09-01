from __future__ import annotations

import threading
import time
from typing import Any

from .models import OrderIntent, OrderStage
from .monitor import ExecutionMonitor


class DemoLoop:
    """Runs real monitor operations slowly enough for a human to observe them."""

    def __init__(
        self,
        monitor: ExecutionMonitor,
        *,
        delay: float = 1.5,
        max_cycles: int = 12,
    ) -> None:
        self.monitor = monitor
        self.delay = max(0.1, float(delay))
        self.max_cycles = max(1, int(max_cycles))
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="execution-demo")
        self._counter = 0
        self._cycles_since_reset = 0
        self.status_trace: list[str] = []
        self.phase_trace: list[str] = []

    def start(self) -> None:
        self.monitor.reset_automatic_demo()
        self._cycles_since_reset = 0
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=max(2.0, self.delay * 2))

    def _wait(self, multiplier: float = 1.0) -> bool:
        return self._stop.wait(self.delay * multiplier)

    def _capture_status(self) -> dict[str, Any]:
        snapshot = self.monitor.snapshot()
        self.status_trace.append(snapshot["overall_status"])
        self.phase_trace.append(snapshot["execution_phase"])
        return snapshot

    def run_cycle(self) -> bool:
        """Run one real SAFE → WARNING → SAFE → BLOCKED → SAFE demonstration."""
        if self.monitor.store.list_orders() or self._cycles_since_reset >= self.max_cycles:
            self.monitor.reset_automatic_demo()
            self._cycles_since_reset = 0
        self._cycles_since_reset += 1
        self.status_trace.clear()
        self.phase_trace.clear()
        self._counter += 1
        intent_id = f"demo-{int(time.time())}-{self._counter}"
        intent = OrderIntent(intent_id, "BTC-USD", "buy", 0.50)

        if not self.monitor.venue.connected:
            self.monitor.venue.reconnect()
            self.monitor.recover_from_venue()

        self._capture_status()
        if self._wait():
            return False

        record = self.monitor.begin_submission(intent, reference_price=100.0)
        self._capture_status()
        if self._wait():
            return False
        if record.stage == OrderStage.ORDER_FAILED:
            self._wait(2)
            return not self._stop.is_set()

        record = self.monitor.prepare_dispatch(intent_id)
        self._capture_status()
        if self._wait():
            return False

        record = self.monitor.complete_dispatch(intent_id)
        self._capture_status()
        if self._wait():
            return False

        # Create a real venue/local mismatch so the monitor—not the browser—raises WARNING.
        self.monitor.venue.fill(record.venue_order_id, 0.20, 100.0)
        self.monitor.reconcile()
        self._capture_status()
        if self._wait(1.5):
            return False

        self.monitor.recover_from_venue()
        self._capture_status()
        if self._wait():
            return False

        self.monitor.apply_fill(intent_id, 0.30, 101.0)
        self._capture_status()
        if self._wait():
            return False

        self.monitor.reconcile()
        self._capture_status()
        if self._wait():
            return False

        # Disconnect the actual simulator so the status API reports BLOCKED.
        self.monitor.venue.disconnect()
        self.monitor.reconcile()
        self._capture_status()
        if self._wait(1.5):
            self.monitor.venue.reconnect()
            self.monitor.recover_from_venue()
            return False

        self.monitor.venue.reconnect()
        self.monitor.recover_from_venue()
        self._capture_status()
        if self._wait(2.5):
            return False
        return True

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self.run_cycle():
                return
