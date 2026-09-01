from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .models import OrderRecord, OrderStage, utc_now


class JournalStore:
    """Small durable execution journal used by tests, recovery, and the dashboard."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._closed = False
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    intent_id TEXT PRIMARY KEY,
                    venue_order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    requested_quantity REAL NOT NULL,
                    filled_quantity REAL NOT NULL,
                    average_fill_price REAL NOT NULL,
                    stage TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _row_to_order(row: sqlite3.Row | None) -> OrderRecord | None:
        if row is None:
            return None
        return OrderRecord(
            intent_id=row["intent_id"],
            venue_order_id=row["venue_order_id"],
            symbol=row["symbol"],
            side=row["side"],
            requested_quantity=float(row["requested_quantity"]),
            filled_quantity=float(row["filled_quantity"]),
            average_fill_price=float(row["average_fill_price"]),
            stage=OrderStage(row["stage"]),
            updated_at=row["updated_at"],
        )

    def save_order(self, order: OrderRecord) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO orders (
                    intent_id, venue_order_id, symbol, side, requested_quantity,
                    filled_quantity, average_fill_price, stage, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(intent_id) DO UPDATE SET
                    venue_order_id=excluded.venue_order_id,
                    symbol=excluded.symbol,
                    side=excluded.side,
                    requested_quantity=excluded.requested_quantity,
                    filled_quantity=excluded.filled_quantity,
                    average_fill_price=excluded.average_fill_price,
                    stage=excluded.stage,
                    updated_at=excluded.updated_at
                """,
                (
                    order.intent_id,
                    order.venue_order_id,
                    order.symbol,
                    order.side,
                    order.requested_quantity,
                    order.filled_quantity,
                    order.average_fill_price,
                    order.stage.value,
                    order.updated_at,
                ),
            )

    def get_order(self, intent_id: str) -> OrderRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM orders WHERE intent_id = ?", (intent_id,)
            ).fetchone()
        return self._row_to_order(row)

    def list_orders(self) -> list[OrderRecord]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM orders ORDER BY updated_at, intent_id"
            ).fetchall()
        return [order for row in rows if (order := self._row_to_order(row)) is not None]

    def latest_order(self) -> OrderRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM orders ORDER BY updated_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        return self._row_to_order(row)

    def add_event(
        self,
        message: str,
        *,
        kind: str = "info",
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO events (kind, message, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (kind, message, json.dumps(payload or {}, sort_keys=True), utc_now()),
            )

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 100))
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (safe_limit,)
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "kind": row["kind"],
                "message": row["message"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def latest_event_message(self) -> str:
        events = self.recent_events(limit=1)
        return events[0]["message"] if events else "Execution Monitor is ready."

    def get_metadata(self, key: str) -> str | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT value FROM metadata WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def set_metadata(self, key: str, value: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO metadata (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )

    def reset_demo_data(self) -> None:
        """Clear disposable automatic-demo records while preserving run metadata."""
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM orders")
            self._connection.execute("DELETE FROM events")

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True
