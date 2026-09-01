# Recovery Runbook

## Browser refresh

Refresh normally. The browser has no execution state; it reloads the authoritative status from the monitor.

## Monitor process restart

1. Stop the local process with `Ctrl+C`.
2. Keep the SQLite database and simulator state under `var/`.
3. Start the same command again.
4. The monitor loads its journal and reconciles against the simulator before continuing.
5. Confirm the dashboard shows **System operating safely** and every reconciliation row is `MATCHED`.

## Disconnected venue

1. Stop new submissions. The monitor reports `BLOCKED`.
2. Restore the venue connection.
3. Query authoritative orders, fills, positions, and balance.
4. Run recovery, then reconciliation.
5. Resume only when every record check passes.

## Mismatch

1. Treat `WARNING` as a real stop condition for unattended execution.
2. Preserve the journal and venue snapshot.
3. Recover authoritative venue orders.
4. Reconcile orders, fills, position, and balance.
5. Do not hide a remaining mismatch; record it as a limitation or unresolved incident.

## Emergency stop

Activation is implemented and tested in Python but intentionally absent from the browser. Clearing it is a local test-only operation. A real operator workflow requires authentication and a separate safety design.
