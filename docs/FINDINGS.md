# Before / After Findings

## Before-state failures

The intentionally unreliable baseline demonstrates four common failure classes:

| Failure | Before behavior | Evidence |
|---|---|---|
| Retry duplication | One logical request creates two venue orders | `tests/test_baseline_failures.py` |
| Partial-fill drift | Local state treats a partial fill as complete | `tests/test_baseline_failures.py` |
| Disconnect | The system remains disconnected and has no recovery path | `tests/test_baseline_failures.py` |
| Restart | In-memory order knowledge disappears | `tests/test_baseline_failures.py` |

## Corrected behavior

| Safeguard | Result | Evidence |
|---|---|---|
| Idempotent intent ID | Duplicate retry returns the existing order | `tests/test_execution_monitor.py` |
| Pre-venue risk limit | Oversized request never reaches the venue | `tests/test_execution_monitor.py` |
| Actual-fill accounting | Partial and full quantities remain explicit | `tests/test_execution_monitor.py` |
| Rejection and cancellation | Each keeps a truthful terminal state | `tests/test_execution_monitor.py` |
| Connection boundary | Disconnect changes the system to `BLOCKED` | `tests/test_execution_monitor.py` |
| Reconciliation | Venue-only changes produce `WARNING`, then recover | `tests/test_execution_monitor.py` |
| Restart recovery | New process instances restore journal and venue state | `tests/test_execution_monitor.py` |

Machine-readable results are in [`evidence/latest-verification.json`](../evidence/latest-verification.json).

## Remaining boundaries

- The simulator is not a claim of experience with a named broker or exchange.
- The public-data paper run exercises execution state; it is not a strategy-performance test.
- Network latency, rate limits, authentication, WebSocket resubscription, and venue-specific rules belong to a future adapter milestone.
- Testnet and funded live execution require a separate adapter and explicit authorization.
