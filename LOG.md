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

---

### Entry #3 — RISK-ON
- **Logged:** 2026-09-20
- **State:** RISK-ON
- **Allocation:** `BTC 12% · ETH 24% · SOL 16% · LINK 15% · GOLD 33%`
- **Why:** Bitcoin is back above its 120-day trend, so coins qualify again beside the gold hedge. LOGGED LATE - the indicator made this move on 2026-08-30 and it was not written here until today, so we count this call from today, not from then. See the correction in calls.json.
- **Result since prior entry:** -0.7%  *(computed from daily opens 2026-08-09 → 2026-09-20, net of fees and spread — recompute it yourself with `scripts/verify.py`)*
- **Tracked config:** Vero Compass v1.6 (12-asset pool including gold, up to 6 coins held, plus gold as a permanent hedge sleeve whenever it passes its own trend gate (so up to 7 positions), inverse-volatility sizing, BTC-trend crash filter − crypto moves to cash while the gold hedge is exempt and may stay held; the hedge is funded by selling the WEAKEST-ranked holdings rather than proportionally from all of them). Tracked from 2026-08-28; entries #1 and #2 were produced by v1.3/v1.4 − see engine_changes.

---

### Entry #4 — RISK-ON
- **Logged:** 2026-09-25
- **State:** RISK-ON
- **Allocation:** `ETH 23% · SOL 16% · ADA 3% · AVAX 10% · LINK 15% · GOLD 33%`
- **Why:** The 21-day rebalance on 2026-09-20 moved the book: BTC left, ADA and AVAX came in, and the gold hedge stayed. These are the weights the system's alert gave on 2026-09-21. LOGGED LATE - written here on 2026-09-25 and counted from today, not from the 20th. That alert also named XRP and LTC, and neither was traded; v1.6.2 fixes that alert text.
- **Result since prior entry:** +1.8%  *(computed from daily opens 2026-09-20 → 2026-09-25, net of fees and spread — recompute it yourself with `scripts/verify.py`)*
- **Tracked config:** Vero Compass v1.6.2 (12-asset pool including gold, up to 6 coins held, plus gold as a permanent hedge sleeve whenever it passes its own trend gate (so up to 7 positions), inverse-volatility sizing, BTC-trend crash filter − crypto moves to cash while the gold hedge is exempt and may stay held; the hedge is funded by selling the WEAKEST-ranked holdings rather than proportionally from all of them). Tracked from 2026-08-28; entries #1 and #2 were produced by v1.3/v1.4 − see engine_changes.
