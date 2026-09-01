from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class Mode(str, Enum):
    SIMULATION = "simulation"
    REPLAY = "replay"
    PAPER = "paper"
    TESTNET = "testnet"
    AUTHORIZED_LIVE = "authorized_live"


class OrderStage(str, Enum):
    NO_ACTIVE_ORDER = "no_active_order"
    CHECKING_ORDER = "checking_order"
    SENDING_ORDER = "sending_order"
    WAITING_FOR_FILL = "waiting_for_fill"
    ORDER_PARTLY_FILLED = "order_partly_filled"
    ORDER_FULLY_FILLED = "order_fully_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_FAILED = "order_failed"


class OverallStatus(str, Enum):
    SAFE = "safe"
    WARNING = "warning"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class OrderIntent:
    intent_id: str
    symbol: str
    side: str
    quantity: float

    def normalized_side(self) -> str:
        return self.side.strip().lower()


@dataclass(slots=True)
class OrderRecord:
    intent_id: str
    venue_order_id: str
    symbol: str
    side: str
    requested_quantity: float
    filled_quantity: float
    average_fill_price: float
    stage: OrderStage
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        return payload


@dataclass(slots=True)
class VenueOrder:
    intent_id: str
    venue_order_id: str
    symbol: str
    side: str
    requested_quantity: float
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    stage: OrderStage = OrderStage.WAITING_FOR_FILL

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        return payload
