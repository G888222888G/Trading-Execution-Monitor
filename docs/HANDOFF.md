# Handoff

## Start

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\execution-monitor serve
```

Open `http://127.0.0.1:8765`.

## Verify

```powershell
python scripts/verify.py
```

Expected result: every unit/integration/API test passes, the baseline failures are detected, each corrected scenario passes, and the public-data paper evidence reports matching records.

## Important paths

- Core: `src/execution_monitor/monitor.py`
- Venue fixture: `src/execution_monitor/simulator.py`
- Dashboard: `src/execution_monitor/static/`
- Tests: `tests/`
- Evidence: `evidence/`
- Public documentation: `docs/`

## Next engineering milestone

Add a named venue adapter only after current job evidence selects it. Keep the monitor contract unchanged, add offline adapter tests first, then use paper/testnet evidence. Any funded test requires exact approval of the venue, account or wallet, amount, and procedure.
