# An account's move is measured from its holdings, not its balance

Cha-Ching! decides whether an account has made a big move. The obvious measure is the account balance over time, but a deposit, a withdrawal or a sale into cash moves the balance without the market moving at all. Instead, the account's move is how today's holdings would have moved: each holding's share count times its price history, summed. Its volatility comes from the same series over the past year. Deposits and withdrawals never count, and no balance history is needed from the broker.

The cost is that the measure answers "how did what I own now do?", not "how did my account do?": a holding bought last week counts as if it had been held all year. For a display that asks whether today's market is unusual for this account, that is the right question.

## Considered Options

- **Account balance history**: what the broker reports, but distorted by every deposit and withdrawal, and only available from the aggregator as an estimated beta feature.
- **Balance history corrected for cash flows** (time-weighted return): accurate, but needs every transaction and much more code.
