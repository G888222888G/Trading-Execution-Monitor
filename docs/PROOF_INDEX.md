# Proof Index

| Buyer-facing claim | Inspectable proof |
|---|---|
| Failure-first takeover | [`test_baseline_failures.py`](../tests/test_baseline_failures.py) and [`FINDINGS.md`](FINDINGS.md) |
| Duplicate prevention | `test_duplicate_intent_is_not_submitted_twice` |
| Risk boundary | `test_risk_limit_blocks_order_before_venue` |
| Partial fills | `test_partial_fill_then_full_fill_tracks_real_quantity` |
| Cancellation and rejection | `test_rejection_and_cancellation_are_explicit_states` |
| Disconnect handling | `test_disconnect_blocks_then_reconnect_recovers` |
| Reconciliation | `test_stale_local_state_is_detected_and_recovered` |
| Full restart recovery | `test_full_process_restart_recovers_new_monitor_and_new_venue_instances` |
| Read-only and identifier-free interface | [`test_server_contract.py`](../tests/test_server_contract.py) |
| Dashboard contract | [`test_dashboard_static.py`](../tests/test_dashboard_static.py) and the desktop/mobile screenshots |
| Public-data paper run | [`paper-soak.json`](../evidence/paper-soak.json) and [`DATA_SOURCE.md`](DATA_SOURCE.md) |
| One-command verification | [`scripts/verify.py`](../scripts/verify.py) |
| CI and container setup | [CI workflow](../.github/workflows/ci.yml), [Dockerfile](../Dockerfile), and [Compose](../compose.yaml) |

Run `python scripts/verify.py` to regenerate the current machine-readable evidence.
