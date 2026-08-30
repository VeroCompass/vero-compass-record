#!/usr/bin/env python3
"""
Performance maths for the Vero Compass record.

One rule governs everything here: **a number in the log is computed from real market prices, or it is
labelled as asserted.** Nothing is typed in and presented as measured.

Method
------
A call establishes an allocation. It is held until the next call replaces it. The return of that holding
period is the weighted price change of what was actually held, priced at the DAILY OPENS on the two dates
(the system acts at the next open, so those are tradeable prices).

Costs use the same model as the backtest: a per-side charge of 0.1% fee plus a per-coin spread, applied to
the fraction of the book that changes hands at each end of the period. Cash costs nothing to hold.

Deliberately NOT modelled: exchange withdrawal fees, funding, slippage beyond the spread, and taxes. Those
are the follower's, vary by venue, and inventing them would be a fabricated precision.
"""
FEE = 0.001
SPREAD = {'BTC': 0.0002, 'ETH': 0.0003, 'SOL': 0.0004, 'BNB': 0.0004, 'XRP': 0.0004, 'ADA': 0.0005,
          'DOGE': 0.0005, 'AVAX': 0.0006, 'LINK': 0.0006, 'LTC': 0.0004, 'DOT': 0.0006,
          'TRX': 0.0004, 'GOLD': 0.0002}
DEFAULT_SPREAD = 0.0005


def is_cash(alloc):
    return not alloc or list(alloc.keys()) == ['CASH']


def turnover_cost(alloc):
    """One-way cost of moving the whole book into (or out of) this allocation."""
    if is_cash(alloc):
        return 0.0
    return sum((w / 100.0) * (FEE + SPREAD.get(c.upper(), DEFAULT_SPREAD)) for c, w in alloc.items())


def period_return(alloc, start, end, get_price, get_end_price=None):
    """
    Return of `alloc` held from `start` to `end`, net of the round trip in and out of it.

    get_price(symbol, date) -> (actual_date_used, price). Any failure propagates: a period that cannot be
    priced must not silently become 0%.

    get_end_price: optional separate getter for the CLOSING leg. The open (still-running) period needs a
    different primitive at each end - forward at entry, backward at valuation - because marking an open
    position to a bar that does not exist yet is how a published figure drifts.

    Returns (net_return_fraction, detail_rows).
    """
    if end < start:
        raise ValueError('period runs backwards (%s -> %s). Refusing to compute a return over a negative '
                         'window — check the --effective-since date against the previous entry.'
                         % (start, end))
    if is_cash(alloc):
        return 0.0, [{'symbol': 'CASH', 'weight': 100.0, 'start_price': None, 'end_price': None,
                      'change': 0.0, 'note': 'cash earns nothing and costs nothing'}]

    gross, rows = 0.0, []
    for c, w in alloc.items():
        sym = c.upper()
        if sym == 'CASH':
            rows.append({'symbol': 'CASH', 'weight': float(w), 'start_price': None, 'end_price': None,
                         'change': 0.0, 'note': 'idle cash'})
            continue
        d0, p0 = get_price(sym, start)
        d1, p1 = (get_end_price or get_price)(sym, end)
        chg = p1 / p0 - 1.0
        gross += (w / 100.0) * chg
        # rounded so the public JSON reads cleanly; the maths above uses full precision
        rows.append({'symbol': sym, 'weight': float(w), 'start_date': d0, 'end_date': d1,
                     'start_price': round(p0, 6), 'end_price': round(p1, 6), 'change': round(chg, 6)})
    cost = turnover_cost(alloc) * 2.0        # in at the start, out at the end
    return gross - cost, rows


def daily_path(alloc, start, end, get_price, get_series):
    """
    The DAILY value of `alloc` held from `start` to `end`, as [(date, multiple), ...] starting at 1.0.

    Why this exists: measuring drawdown only at the dates calls were made would quietly hide every dip that
    happened *between* calls — and since calls can be months apart, that would make the published drawdown
    look far better than what a follower actually lived through. Drawdown is the number this product is
    sold on, so it is measured every day.

    Weights are set at entry and then drift, which is what actually happens between rebalances. The entry
    cost is paid on day one and the exit cost at the end, so the final point equals the period return.
    """
    if end < start:
        raise ValueError('period runs backwards (%s -> %s).' % (start, end))
    coins = {c.upper(): float(w) for c, w in (alloc or {}).items() if c.upper() != 'CASH'}
    if not coins:
        return [(start, 1.0), (end, 1.0)]

    cash_w = max(0.0, 100.0 - sum(coins.values())) / 100.0
    series, base, dates = {}, {}, set()
    for sym in coins:
        s = get_series(sym, start, end)
        if not s:
            raise ValueError('no series for %s over %s..%s' % (sym, start, end))
        series[sym] = s
        _, base[sym] = get_price(sym, start)
        dates |= {d for d in s if start <= d <= end}
    axis = sorted(dates)
    if not axis or axis[0] > start:
        axis = [start] + axis
    if axis[-1] < end:
        axis.append(end)

    entry = turnover_cost(alloc)
    exit_ = turnover_cost(alloc)
    out, last = [], dict(base)
    for d in axis:
        v = cash_w
        for sym, w in coins.items():
            p = series[sym].get(d)
            if p:                       # gold does not trade at weekends: carry the last real price
                last[sym] = p
            v += (w / 100.0) * (last[sym] / base[sym])
        out.append((d, v * (1.0 - entry)))
    out[-1] = (out[-1][0], out[-1][1] * (1.0 - exit_))     # cost of getting back out, paid at the end
    return out


def fmt_pct(x):
    """Signed — for returns, where the direction is the point."""
    return ('%+.1f%%' % (x * 100.0)) if x is not None else '—'


def fmt_mag(x):
    """Unsigned — for magnitudes (drawdown, share of time). A drawdown shown as '+40%' reads as a gain."""
    return ('%.1f%%' % (abs(x) * 100.0)) if x is not None else '—'
