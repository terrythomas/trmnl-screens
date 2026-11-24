# Account holdings come through SnapTrade, not broker APIs

Cha-Ching! needs each account's holdings. Some brokers offer a personal API, but each is a separate integration, some keys can place trades, and writing adapters for brokers the deployment doesn't use means code that can never be tested. SnapTrade is one aggregator that covers many brokers through a single API, has a free personal plan (up to 20 connections), and makes connections read-only by default (checked 2026-11-24). The repo also never has to say which broker any account is held at.

The cost is a third party holding a read-only connection to each account, and possibly holdings that refresh only once a day on the free plan. Holdings rarely change and prices come from elsewhere ([ADR-0014](0014-prices-from-yahoo-chart-endpoint.md)), so a daily refresh is enough.

## Considered Options

- **A broker's own personal API**: no third party, but one integration per broker, and at least one such key can place trades with no read-only scope.
- **Several broker APIs side by side**: hides which broker is used, but most adapters would be untested.
- **Plaid**: wide coverage, but no free personal tier.
- **Holdings typed into `.env`**: no third party, but goes stale whenever the holdings change.
