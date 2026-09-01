# Architecture

## Human view

```text
TRADING SYSTEM  --->  EXECUTION MONITOR  --->  EXCHANGE OR SIMULATOR
      ^                       |                         |
      |                       v                         |
      +-------------- results and state <--------------+
                              |
                              v
                   TESTS + EVIDENCE + DASHBOARD
```

The trading system decides what to trade. The Execution Monitor decides whether a request is safe to send, records what happened, detects disagreement, and restores authoritative state.

## Components

- `ExecutionMonitor`: validation, idempotency, order lifecycle, reconciliation, recovery, and status.
- `JournalStore`: SQLite orders, events, run identity, operating mode, and emergency-stop state.
- `SimulatedVenue`: deterministic external authority for orders, fills, positions, balances, rejection, cancellation, disconnect, and restart tests.
- `Paper runner`: replays frozen public candles through the same monitor and simulator.
- `Local server`: serves static assets and read-only JSON from localhost.
- `Dashboard`: polls the status endpoint once per second and contains no state-changing controls.

## Order lifecycle

```text
NO ACTIVE ORDER
      |
      v
CHECKING ORDER --unsafe--> ORDER FAILED
      |
      v
SENDING ORDER --rejected/disconnected--> ORDER FAILED
      |
      v
WAITING FOR FILL --> PARTLY FILLED --> FULLY FILLED
      |
      +-----------------------------> CANCELLED
```

## Read-only interface

- `GET /api/status`: current mode, overall result, order stage, derived visible execution phase, safety checks, reconciliation checks, and the latest plain-English event with its timestamp.
- `GET /api/events?limit=20`: recent sanitized journal events.
- `GET /healthz`: local process health.
- `POST`, `PUT`, `PATCH`, and `DELETE`: always return `405 read_only`.

The API intentionally excludes quantities, prices, balances, account IDs, credentials, wallet information, and transaction identifiers.
