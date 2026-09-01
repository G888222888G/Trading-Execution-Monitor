# Foundation Decision

Decision date: 2026-08-30

## Decision

Use a small standalone Python implementation as the first public demonstration. Keep Freqtrade, Hummingbot, and NautilusTrader as later integration targets rather than making one of them the hidden foundation.

This is a project-fit score, not a judgment of general framework quality.

| Criterion | Weight | Standalone | NautilusTrader | Hummingbot | Freqtrade |
|---|---:|---:|---:|---:|---:|
| Matches takeover/reliability jobs | 25 | 25 | 20 | 17 | 16 |
| Makes failures easy to inject and explain | 20 | 20 | 17 | 13 | 12 |
| Keeps the client system and venue replaceable | 20 | 20 | 16 | 12 | 8 |
| Existing execution/recovery depth | 15 | 12 | 15 | 12 | 10 |
| Public demonstration clarity | 10 | 10 | 5 | 6 | 6 |
| Maintenance and dependency cost | 10 | 8 | 7 | 6 | 7 |
| **Total** | **100** | **95** | **80** | **66** | **59** |

## Evidence

- [NautilusTrader](https://nautilustrader.io/docs/) already supplies an event-driven engine spanning deterministic simulation, risk, execution, adapters, reconciliation, and live trading. It is the strongest existing-engine candidate, but using it as the core would make our demonstration prove configuration of its machinery rather than our ability to diagnose and repair that machinery.
- [Hummingbot](https://hummingbot.org/docs/) is connector- and deployment-oriented, with standardized CEX/DEX connectors, an API, Gateway, and a dashboard. It remains a strong Lane 2 integration target but is broader than the first reliability proof.
- [Freqtrade](https://github.com/freqtrade/freqtrade) is a GPL Python crypto bot with dry-run, backtesting, optimization, REST API, and web UI. It remains useful as a client-system fixture, but its strategy-centric architecture and built-in presentation would obscure the monitor boundary.
- Current buyer evidence in the Upwork planning workspace spans custom engines, brokers, exchanges, and existing systems. A framework-neutral boundary fits that market evidence better than a portfolio tied to one bot.

## Revisit Trigger

Revisit only when a specific job or Lane 2 adapter requires one named framework. Do not replace the core merely because a framework has more built-in features.
