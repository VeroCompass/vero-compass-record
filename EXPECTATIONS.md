# Pre-Registered Expectations for the Live Record

**Written 2026-08-06, BEFORE this log contains any live allocation calls.**
This document exists so the forward record can be judged against expectations set *in advance*, rather than
explained after the fact. It is committed to a public, timestamped repository for exactly that reason —
anyone can verify it predates the results it will be measured against.

Every figure below is derived from backtests on **survivorship-free data** (a universe that includes coins
which later collapsed, such as LUNA), documented in the research record. **Backtests are not promises.**

---

## What this system is
A rules-based crypto allocation system whose defensible property is **drawdown control**. It ranks a pool of
major coins by momentum, holds the strongest that are trending, sizes them by inverse volatility (calmer
coins get larger positions), and moves fully to cash when Bitcoin breaks its long-term trend.
**The coin pool is a disclosed input you can change; the rules are the product.**

**Tracked configuration:** Vero Compass v1.4 — a 12-coin pool, up to 6 held, inverse-volatility sizing,
periodic re-ranking with immediate exits, and a Bitcoin-trend crash filter to cash. Numerically identical to
v1.3; v1.4 adds separate exit and entry alerts. Any change of the tracked engine will be announced in the
log itself.

## ⚠️ Correction, made before this record contains any live call
An earlier version of this document quoted return and time-underwater figures that were **measured on the
wrong basis** — a crypto-only book with the gold hedge removed, and a different configuration from the one
actually tracked. The return figure in particular was wrong by roughly six times, in the *understating*
direction. Those figures have been corrected or withdrawn below.

This correction is made **before the log contains a single live allocation call**, so nothing here is being
revised after the fact to fit a result. The full edit history is public in this repository's commits. Where
a figure has not yet been re-measured on the corrected basis, **it has been withdrawn rather than restated**
— a number known to be measured wrongly does not belong in a document whose entire purpose is to be judged
against later.

## Where these expectation bands come from — read this before the numbers
The tracked configuration's own backtest runs on a **coin list chosen with hindsight**, which flatters it.
The bands below come instead from **survivorship-free testing** — a universe containing the coins as they
actually ranked at the time, including those that later went to zero — with the gold hedge included, as the
shipped product holds it.

**That is the honest basis, and it is still a backtest.** If the live record lands above these bands, good.
If it lands below them, that is a genuine problem, and this document exists so we cannot pretend otherwise.

## What we expect the live record to show, if the system works as characterised

**Returns — the backtest is strong, and you should still expect materially less.**
- On survivorship-free data including the hedge, the tested decade compounded at roughly **60% a year**.
  **Do not plan around that number.** A backtest flatters in ways a live record cannot: the parameters were
  chosen with this history visible, and a single exceptional year does much of the work.
- **The honest forward expectation is materially lower than the backtest**, and this record exists precisely
  because no one — including us — can tell you by how much until it has run.
- Large returns, when they come, are concentrated in strong alt-seasons rather than earned steadily.
  **The live record should not be assumed to contain one.**
- **Expect losing years.** A meaningful fraction of one-year starting points in the backtest ended below
  where they began. Which year you start in matters more than most people expect.

**Drawdown — expect it to be deep but controlled.**
- Expect drawdowns around **40–55%**, and be unsurprised by 50%.
- The system's job is to be **materially shallower than holding**: in five separate historical crashes it
  cut losses by 40–60 percentage points versus buy-and-hold. **That gap — not the absolute number — is the
  thing to judge.**
- **This is the claim with the strongest evidence behind it, and it has now been tested on two independent
  eras.** The protective rule was re-tested on Bitcoin data from **2011–2017** — a completely separate cycle
  containing an 85% collapse — and it cut the drawdown from 84.9% to 70.3% there, at a ~10% cost in return.
  Combined with the 2018–2026 evidence, the protection holds across two cycles years apart. *(An earlier
  attempt on a 2014–2017 window showed no benefit — but that window contained no major crash for the rule
  to catch, which is itself consistent with how the system is described: it protects in crashes and costs
  you in sustained bull markets.)*

**Time underwater — expect this to be the hardest part.**
- Expect to spend **the great majority of your time below your best-ever balance.** This is not a
  qualification; it is the normal state of this kind of system.
- Expect flat or losing stretches lasting **well over a year.**
- This is the normal shape of a trend-following system, and it is where most people quit.
- *(Precise figures for time-underwater and worst flat stretch are being re-measured on the corrected
  basis — see the correction note at the top of this document — and will be stated here once measured.
  They are not quoted meanwhile rather than quote figures known to be measured wrongly.)*

**Execution — one rule matters more than the rest.**
- **Act on EXIT signals the same day.** Being two days late on exits destroyed roughly 40% of risk-adjusted
  performance in testing, because the protection only works if you actually get out.
- **Entry signals are not urgent** — being a couple of days late cost effectively nothing.

## What would FALSIFY the characterisation
These are stated now so they cannot be rationalised away later. The system should be considered **not
performing as described** if, over a meaningful live sample (2+ years):

1. **A crypto-wide crash occurs and the system does not materially outperform buy-and-hold through it.**
   This is the core claim; failing it is the most serious falsification.
2. **Drawdown materially exceeds the historical band** (say, beyond ~60%) in conditions no worse than 2018
   or 2022.
3. **The system underperforms a simple "hold Bitcoin, exit below its long-term trend" rule** over a full
   cycle. Research found that simple alternative to be surprisingly competitive — if it wins live too, the
   added complexity is not earning its keep and we will say so.
4. **Live results diverge persistently from the published rules** — i.e. the calls in this log stop matching
   what the stated rules would produce.

## Known limitations, stated up front
- **The rules are crypto-specific.** Applied unchanged to US equity sector ETFs over 21 years they
  underperformed a simple index hold on risk-adjusted terms, while still protecting in every crisis.
  This is not a universal market edge.
- **We cannot yet distinguish "the edge has decayed" from "no alt-season has occurred since 2021."** Both
  predict the same recent data. Only this forward record will separate them.
- **The specific trend-filter setting is not a magic number.** Testing across three separate market cycles,
  a different lookback length was "best" in each one. On crash-heavy periods the choice barely mattered —
  the *mechanism* works across a wide range of settings even though no single setting is special. We use a
  fixed, disclosed value and do not tune it to history.
- **The coin-rotation part of the system is less proven than the protection part.** Its historical advantage
  was concentrated in the 2021 alt-season; a much simpler "hold Bitcoin, step aside when it breaks trend"
  rule was competitive in other periods. We think the rotation adds value, but that is the part this live
  record most needs to demonstrate.
- **Capacity is limited** — comfortable to a few hundred thousand dollars, bounded by the least liquid coin
  the system might hold.
- **The historical figures are backtests.** They assume prompt execution and realistic but modelled costs.

## How to judge this record
Compare the live results against the bands above — *not* against the headline backtest figures, which are
concentrated in one exceptional year and were measured on a favourable parameter choice. If the live record
lands within these expectations, the system is behaving as described. If it does not, that will be visible
here, permanently, and we will say so.

*Nothing here is financial advice. Crypto is volatile; only risk what you can afford to lose.*
