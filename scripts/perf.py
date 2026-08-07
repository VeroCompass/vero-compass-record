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


def period_return(alloc, start, end, get_price):
    """
    Return of `alloc` held from `start` to `end`, net of the round trip in and out of it.

    get_price(symbol, date) -> (actual_date_used, price). Any failure propagates: a period that cannot be
    priced must not silently become 0%.

    Returns (net_return_fraction, detail_rows).
    """
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
        d1, p1 = get_price(sym, end)
        chg = p1 / p0 - 1.0
        gross += (w / 100.0) * chg
        rows.append({'symbol': sym, 'weight': float(w), 'start_date': d0, 'end_date': d1,
                     'start_price': p0, 'end_price': p1, 'change': chg})
    cost = turnover_cost(alloc) * 2.0        # in at the start, out at the end
    return gross - cost, rows


def fmt_pct(x):
    return ('%+.1f%%' % (x * 100.0)) if x is not None else '—'
