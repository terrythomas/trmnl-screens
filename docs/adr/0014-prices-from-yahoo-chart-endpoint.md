# Prices come from Yahoo's unofficial chart endpoint

Bull or Bear? and Cha-Ching! need a current price, the after-hours price, and a year of daily closes, both raw and dividend-adjusted, for every stock every 15 minutes. Yahoo's `v8/finance/chart` endpoint returns all of that in one request with no key, only a browser User-Agent (checked 2026-11-24: 252 daily bars, near real-time price, pre- and after-hours bars with `includePrePost`). It is undocumented, and it answers HTTP 429 to bursts, so the screens rely on the error banner and stale data when it fails rather than on a fallback source.

## Considered Options

- **Twelve Data**: official and free with a key (800 requests a day), but history depth on the free plan is not stated, and it means managing another key.
- **Finnhub**: free real-time quotes, but daily history is paid.
- **Alpha Vantage**: free key, but 25 requests a day and end-of-day only.
- **Stooq**: free CSV, but now behind a browser check that scripts can't pass.
