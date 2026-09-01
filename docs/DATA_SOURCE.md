# Frozen Public Candle Source

- Product: `BTC-USD`
- Window: 2026-08-29 00:00–02:00 UTC
- Granularity: five minutes
- Rows: 24
- Retrieved: 2026-08-30
- Source endpoint: `https://api.exchange.coinbase.com/products/BTC-USD/candles`
- Official schema: [Coinbase Exchange get product candles](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)

Coinbase documents each row as timestamp, low, high, open, close, and volume. The repository converts that array into a labeled CSV and freezes it so verification does not depend on a network request.

The dataset is used only to exercise deterministic paper execution and reconciliation. It is not evidence of returns, forecasting skill, or funded Coinbase execution.
