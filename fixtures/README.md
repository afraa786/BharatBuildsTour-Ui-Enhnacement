# StockAware demo fixtures

These files are intentionally framework-neutral. The canonical Amir demo world is
`canonical-demo-data.json` for the first wholesaler, **Aarav Electricals & Hardware**
(`BIZ-DEMO-001`). The other files below are earlier compatibility fixtures and may
use different IDs or product values; see `docs/amir-data-reconciliation.md` before
joining them to a backend contract.

- `canonical-demo-data.json` — canonical products, scenarios, RFQs, quotes, payment/invoice examples, and vendor events.
- `inventory-demo.csv` — catalog, aliases, prices, stock, and substitutes.
- `workflow-cases.json` — RFQs and expected commercial/workflow outcomes.
- `vendor-message-examples.json` — normalized examples for vendor-update parsing.

Money values are integer paise. Quantities use the product's `unit` field. The
fixture values are demo-only: they are not tax or pricing advice.

Importers must treat `sku` as stable and must not create duplicate products on a
rerun. `alias` values in `aliases` are pipe-separated and should be normalized
before matching.
