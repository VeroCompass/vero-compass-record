# Vero Compass — Allocation Log

Append-only. Newest entries at the bottom. Times of publication are recorded server-side by GitHub in this
repository's commit history. See [`README.md`](README.md) for the honesty rules.

**Log inception: 2026-08-02.** From this date forward, every call is a LIVE, real-time entry. Any state
noted as in effect *before* inception (e.g. the current cash position) is not a live claim — it is
verifiable on the Vero Compass indicator's own backtest; the live forward record starts at inception.

---

### Entry #1 — RISK-OFF (100% cash)
- **Logged (live inception):** 2026-08-02
- **State:** RISK-OFF — **100% CASH**
- **Allocation:** `100% cash` (no crypto held)
- **In effect since:** 2026-06-01 *(per the indicator; verifiable on its backtest — not a live-tracked claim)*
- **Why:** Bitcoin is below its 120-day trend filter, so the system holds no crypto and sits in cash.
- **Result since prior entry:** — *(first entry)*
- **Tracked config:** Vero Compass v1.4 — 12-coin pool, up to 6 held, inverse-volatility sizing, Bitcoin-trend crash filter to cash. (Numerically identical to v1.3; v1.4 adds separate exit/entry alerts.)

*The system is currently in cash, so no live trades are being missed — the timeline is anchored now, and
the first live allocation call will be appended here the moment the system leaves cash.*

---

### Entry #2 — RISK-OFF
- **Logged:** 2026-08-10
- **State:** RISK-OFF — **no crypto qualifies; held in the hedge**
- **Allocation:** `GOLD 100%`
- **In effect since:** 2026-08-09
- **Why:** Bitcoin is still below its long-term trend, so no crypto qualifies. Gold has now passed its own trend gate, so the book moves out of cash and into the gold hedge.
- **Result since prior entry:** +0.0%  *(computed from daily opens 2026-08-02 → 2026-08-09, net of fees and spread — recompute it yourself with `scripts/verify.py`)*
- **Tracked config:** Vero Compass v1.3/v1.4 (12-asset pool including gold, up to 6 held, inverse-volatility sizing, BTC-trend crash filter — crypto moves to cash while the gold hedge is exempt and may stay held). v1.4 is numerically identical to v1.3 and adds separate exit/entry alerts.
