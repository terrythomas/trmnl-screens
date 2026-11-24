# Spec: Bull or Bear? and Cha-Ching! screens (v1)

Status: requirements settled (2026-11-24); Bull or Bear? layout chosen (Poster theme, split-scale chart); Cha-Ching! layout to follow in the same language; source facts to confirm (see Open source checks)
Glossary: [CONTEXT.md](../../CONTEXT.md) · Decisions: [docs/adr/](../adr/)

## Problem

The household holds a few individual stocks and a couple of brokerage accounts, but does not watch the market. They want the display to speak up only when something worth knowing happens, during the hours it can happen: a stock or an account has made a move that is unusual for it, a company reports earnings, or a dividend is paid. On a quiet day, a weekend or a market holiday, neither screen appears.

## Solution

Two new **Screens**, each fed by a **Collector** like the other screens ([ADR-0001](../adr/0001-collector-pushes-to-larapaper.md)):

- **Bull or Bear?** (`screens/bull-or-bear/`): one stock per screen. Each configured stock has its own LaraPaper plugin and webhook, so each is its own playlist item.
- **Cha-Ching!** (`screens/cha-ching/`): one **Account** per screen, again one plugin per account. Accounts are kept apart because they serve different purposes.

Both share one set of market rules: the **Trading day**, the **Market window** and the **Big move** test. Prices come from Yahoo's chart endpoint ([ADR-0014](../adr/0014-prices-from-yahoo-chart-endpoint.md)); holdings come from SnapTrade ([ADR-0013](../adr/0013-holdings-through-snaptrade.md)); an account's move is worked out from its holdings, not its balance ([ADR-0015](../adr/0015-account-moves-from-holdings.md)).

The collector works out every number, label and trigger; the template only lays them out and hides itself outside the market window.

The primary **Device** for both is the OG, the display watched during the working day. The X renders the same template ([ADR-0005](../adr/0005-one-template-per-screen-across-devices.md)) and is part of the same work.

## Shared market rules

### Trading day and market window
- A **Trading day** is a day the New York Stock Exchange holds a session, from `exchange_calendars` (`XNYS`), offline. Early-close days are trading days; their regular session ends at the early close and after hours runs four hours past it.
- The **Market window** is 09:30 to 20:00 ET on a trading day (earlier end on early-close days, as above). Pre-market trading is ignored.
- The collector runs every 15 minutes inside the market window and not at all outside it: `next_run_minutes` sleeps until the next window opens.
- Each payload carries `visible_until`, the end of the current market window. The template sets `TRMNL_SKIP_DISPLAY` when the render time is past it, so a screen shown at 19:45 is gone at 20:00 without another push.

### Volatility and big move
- **Volatility** is the standard deviation of daily price changes over the past 252 trading days (about a year), from daily closes.
- The **30-day** volatility is the standard deviation of 21-trading-day changes over the same year.
- A **Big move** is a day change larger than **1.5×** the daily volatility, or a 30-day change larger than **3×** the 30-day volatility, up or down. Both multipliers are adjustable per stock and per account.
- After the 16:00 close, the day change is measured to the latest after-hours price, so an earnings reaction at 16:30 counts as the day's move.
- The one-year change is shown but never makes a big move.
- Measured on two volatile tech stocks over the past year, 1.5× daily showed each on about 43–57 days a year, and 3× over 30 days on about 30–38.

## Bull or Bear?

### When it shows
Inside the market window, when any of these holds:
- a big move (day, including after hours, or 30-day);
- an **Earnings day** for the stock;
- a **Pay date** for one of the stock's dividends.

Otherwise the template sets `TRMNL_SKIP_DISPLAY`.

### What it shows
- **Lead:** the change that triggered the screen, large, with the current price beside it. Order of preference when several hold: after-hours big move, day big move, 30-day big move. On an earnings day or pay date with no big move, a badge leads instead: "Earnings after close", "Earnings before open", "Earnings today" (time not given), or "Dividend paid today".
- **Row of changes:** previous close, the day change, the 30-day change (with the price 21 trading days ago) and the one-year change, all plain price changes as stock quotes show them. A change already shown as the lead is left out of the row: the day change when the lead is the day or after hours (the close line carries it), the 30-day change when the lead is the 30-day move (the lead then reads "from $223.41").
- **After hours:** after 16:00, two lines: "Close $142.80 (+2.3%)" and "After hours $131.40 (−8.0%)". With no after-hours trade yet, only the close line.
- **Dividend line:** when a declared dividend's pay date is today or within 7 days: "Pays $0.27 · Nov 16". Left off when no data.
- **Chart:** one year of daily closes on a **split time scale**: the first 231 trading days fill the left 64% of the width and the last 21 (30 days) the right 36%, separated by a vertical divider and labelled "1 YEAR" and "30 DAYS". Both parts share one price scale. The 30-day part is drawn heavier, with a dashed line at its starting price so its change reads at a glance. At true scale the last 30 days would fill only 8% of the width, which tested too thin to read on the OG. The one-year high and low are marked with their price and date ("High $231 · Feb 12").
- **Title bar:** the ticker and company name, and "as of 2:45 PM" (the price's own time, not the push time).

## Cha-Ching!

### Holdings and pricing
- An account's **Holdings** (symbol and share count) come from SnapTrade once a day, before the market window opens. Cash is left out of the move.
- Prices and one-year daily histories come from Yahoo, every 15 minutes in the market window, as for Bull or Bear?.
- An account's move over a span is how today's holdings would have moved over it: the sum of each holding's shares × its value change, divided by the holdings' value at the start of the span. Deposits, withdrawals and trades never count as moves.
- Moves are **Total return**: the 30-day and one-year changes use Yahoo's dividend-adjusted closes. The day change uses price, since dividends land on the ex-dividend day only.
- Volatility comes from the same calculation applied to the past year: the daily total-return series of today's holdings.

### When it shows
Inside the market window, when any of these holds:
- a big move for the account (1.5× daily, 3× 30-day);
- a dividend paid into the account today, from SnapTrade's account activity.

### What it shows
- **Lead:** the triggering change in % (day or 30-day), large; on a dividend-only day, "Dividends paid today".
- **Top contributors:** the two or three holdings that did the most to the move, each with its own % change.
- **Row of changes:** day, 30-day and one-year, in % only.
- **Dividends:** holdings that paid today, by symbol and per-share amount ("O $0.27/share"). Never totals.
- **Chart:** the one-year total-return line of today's holdings, on the same split time scale as Bull or Bear?, high and low marked with date.
- **Title bar:** the account's nickname from `.env`, and "as of 2:45 PM".
- **No dollar values anywhere:** no account value, no position sizes, no dividend totals.

## Failure behaviour
- If Yahoo fails, the collector pushes its last good data marked stale and raises the error banner, as on the other screens. Yahoo is known to answer HTTP 429 to bursts; one request per stock per run keeps well under that.
- If SnapTrade fails, Cha-Ching! keeps pricing the last holdings it read. The banner appears only once holdings are more than a day old.
- If Finnhub or Nasdaq fails, the earnings badge or dividend line is left off, logged, and never marks the screen stale.
- A missing or rejected key is reported as its own source (`snaptrade-key`, `finnhub-key`), as on Where's My Stuff?.
- Outside the market window a failure stays hidden with the screen; the banner rule of Where's My Stuff? (show after 24 hours of errors) does not apply, since a hidden screen is the normal state.
- Errors never contain URLs, keys, account numbers or holdings ([ADR-0003](../adr/0003-public-repo-secrets-policy.md)).

## Sources

| Data | Source | How often |
|---|---|---|
| Price, after-hours price, one-year daily closes (raw and adjusted) | Yahoo `v8/finance/chart`, browser User-Agent, no key ([ADR-0014](../adr/0014-prices-from-yahoo-chart-endpoint.md)) | every run |
| Trading days, early closes | `exchange_calendars` (offline) | every run |
| Next earnings date and time of day | Finnhub `/calendar/earnings` (free key) | once a day |
| Upcoming dividends with pay dates | Nasdaq `api/quote/{symbol}/dividends` (unofficial, browser User-Agent) | once a day |
| Holdings, dividends paid into an account | SnapTrade personal API key, read-only connections ([ADR-0013](../adr/0013-holdings-through-snaptrade.md)) | once a day |

Daily data is cached in `STATE_DIR/bull-or-bear/` and `STATE_DIR/cha-ching/`.

## Configuration

- `.env`, Bull or Bear?: the stocks, each with its symbol, LaraPaper webhook and plugin id, and optional multipliers; `FINNHUB_API_KEY`.
- `.env`, Cha-Ching!: the accounts, each with a nickname, its SnapTrade account id, webhook and plugin id, and optional multipliers; `SNAPTRADE_CLIENT_ID`, `SNAPTRADE_CONSUMER_KEY`.
- Plus the existing `LARAPAPER_URL`, `TZ`, `STATE_DIR`. Symbols, nicknames and account ids live only in `.env`.

## Testing

- **Market rules:** pytest with fixed dates for trading days, an early close, a holiday, the window edges and `visible_until`.
- **Volatility and big move:** pytest on invented price series with known standard deviations, at and either side of each multiplier, including the after-hours case.
- **Account move:** pytest on invented holdings and histories: contributors, total return, and a deposit not counting as a move.
- **Source adapters:** `httpx.MockTransport` against invented responses in each source's real shape, never real responses or real holdings ([ADR-0003](../adr/0003-public-repo-secrets-policy.md)).
- **Template:** by eye in `trmnlp serve` on the OG and the X with fixtures for each lead (day, after hours, 30-day, earnings, pay date), a stale run, and a long company name.

## Out of scope (v1)

- **Balance-only accounts** (accounts whose holdings can't be read): tracked in a separate issue.
- Pre-market moves, options, crypto, and non-US exchanges.
- Combining several stocks or accounts on one screen.
- Dollar values of any kind on Cha-Ching!.

## Open source checks

Confirm with real data before calling the screens done, then delete this section:
- Whether a SnapTrade personal key gets live or once-a-day holdings, and whether its account activity reports dividends with the pay date.
- Finnhub's free earnings calendar with a real key: how far ahead it reaches and its time-of-day values.
- Yahoo's after-hours bars after 16:00 (seen in pre-market only so far).
- Nasdaq's dividend coverage: it returned nothing for one NYSE-listed monthly payer.
