# Vero Compass — Live Track Record

This repository is the **canonical, public, append-only log** of every allocation call made by the
Vero Compass system. It is owned infrastructure — not a social account, not rented land. A record that
grows in public, one commit at a time, cannot be back-fabricated: GitHub stamps the server-side time of
every push, and the full history is open for anyone to audit.

## Don't trust this record — check it

Every performance figure in this log is **computed from public market prices**, not typed in by hand. And
you can re-derive all of them yourself:

```bash
python scripts/verify.py
```

No account, no API key, nothing to install — just Python. It reads the log, fetches the real daily opening
prices of whatever was actually held on the exact dates it was held (Binance for crypto, Yahoo for gold),
recomputes each return net of the same fee and spread model the backtest uses, and tells you whether the
log's own claims reproduce. It also prints what simply holding Bitcoin did over the same window — including
when that is the more flattering number.

It exits **0** if every claim reproduced and **1** if any did not. If you find a discrepancy this script
cannot explain, that is a real finding, and publishing the tool to find it is the point.

**How to read the entries:** a result marked *computed* was measured from prices by
[`scripts/add_call.py`](scripts/add_call.py). A result marked ⚠️ *manually entered* was asserted by a human
and is not independently measured — the log labels those explicitly so you know which is which. The
maths lives in [`scripts/perf.py`](scripts/perf.py) and the price fetching in
[`scripts/prices.py`](scripts/prices.py); both are short enough to read in a few minutes.

**What is deliberately not modelled:** exchange withdrawal fees, funding, slippage beyond the spread, and
taxes. Those depend on your venue and your jurisdiction, and inventing them would be false precision.

## Pre-registered expectations
**[`EXPECTATIONS.md`](EXPECTATIONS.md)** — written *before* this log contains any live call. It states what
the record should look like if the system works as described, **and what would falsify that claim**. It is
committed here so it is timestamped ahead of the results it will be judged against. Read it before reading
the log; judge the live record against those bands, not against headline backtest figures.

## How to read the log
- **[`LOG.md`](LOG.md)** — the human-readable, chronological log. Newest entries at the bottom.
- **[`calls.json`](calls.json)** — the same log, machine-readable (what the site renders).
- Each entry records: the **date**, the **state** (risk-on / risk-off), the **allocation** (coins +
  rounded weights, or `100% cash`), and — as outcomes arrive — the **result since the prior entry**.

## The honesty rules (these are the whole point)
1. **LIVE vs BACKTEST are labeled, always.** The *backtest* is independently verifiable by anyone — load
   the Vero Compass indicator on TradingView and read its historical calls; no platform or trust in us
   required. **This log is the LIVE, real-time forward record** — the calls as they happen, from the log's
   inception date forward.
2. **The pool is a disclosed input, never a claimed edge.** Vero Compass sells the *rules* (rotation +
   risk-parity sizing + a crash filter), not a magic coin list. A backtest run over a hand-picked list of
   coins that happened to survive is survivorship-biased and is **never** presented as a performance
   headline. **The forward log is the proof.**
3. **Append-only. Never back-dated, never edited.** A wrong call stays in the record permanently. That
   permanence is the asset — you are watching the record form, not reading a story told after the fact.
4. **Not financial advice.** This is the transparent output of a research system. Crypto is volatile; only
   risk what you can afford to lose. Do your own diligence.

## Currently tracked configuration
The officially tracked system is the **locked, live configuration** (Vero Compass v1.x). Any change of the
tracked engine (for example, a future v3 once its validation is complete and it is formally locked) will be
**announced in the log itself** — no engine is ever switched mid-record silently.

## How each call gets published (real time, to three places at once)
When the system changes allocation, one action fans out to all owned channels:
1. **This log** — `scripts/add_call.py` appends the entry and commits + pushes it (GitHub stamps the time).
2. **The site** — GitHub Pages re-renders `calls.json` automatically on push.
3. **Email** — the same entry goes to the newsletter list (see `scripts/add_call.py` notes).

Ideally `add_call.py` is triggered off the indicator's TradingView alert, so the push time is genuine
(machine-set at the moment of the call), not typed by hand.

---
*Vero Compass is a rules-based crypto allocation research system. This repository is its public record.*
