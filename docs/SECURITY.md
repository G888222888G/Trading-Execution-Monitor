# Security and Public-Sharing Boundary

- The server binds to `127.0.0.1` by default.
- Docker binds inside the container only when the explicit container environment flag is set; Compose publishes the host port to `127.0.0.1` only.
- The browser is read-only. All state-changing HTTP methods return `405`.
- The server exposes only `GET /api/status`, static dashboard assets, and a health check.
- The status API uses an explicit field allowlist and excludes run IDs, prices, quantities, balances, account IDs, credentials, wallet information, journal payloads, and transaction identifiers.
- Detailed events remain in the ignored local SQLite journal and are not exposed through HTTP.
- The repository contains no private strategy, client material, exchange credentials, private key, seed phrase, funded wallet, or real transaction history.
- Frozen market data is public and source-documented.

Before publication, run the full verification command, two independent secret scans, a staged-file review, and a manual image review. Publication is not authorized by the existence of this local folder.
