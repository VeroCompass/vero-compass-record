#!/usr/bin/env python3
"""
Generate the live performance summary from calls.json — never hand-written.

Writes `summary.json`, which the site renders. Every figure is derived from the log plus public prices, so
the summary cannot drift from the record it describes, and cannot be quietly improved.

It always includes the comparison against simply holding Bitcoin over the same window — including, and
especially, when that comparison is unflattering. A record that only shows its good side is marketing.

    python scripts/build_summary.py
"""
import json, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices, perf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build():
    with open(os.path.join(ROOT, 'calls.json'), encoding='utf-8-sig') as f:
        data = json.load(f)
    calls = data.get('calls') or []
    inception = data.get('log_inception')
    today = prices.today_utc()

    out = {'generated_utc': today, 'inception': inception, 'calls_logged': len(calls),
           'note': 'Every figure here is computed from calls.json and public prices by '
                   'scripts/build_summary.py. Nothing on this page is hand-written.'}

    if not calls:
        out['status'] = 'no calls logged yet'
        return out, data

    # --- equity path across completed periods, plus the still-open one ---
    equity, legs, unpriced = 1.0, [], []
    curve = [(inception, 1.0)] if inception else []
    daily_ok = True
    for i, prev in enumerate(calls):
        start = prev.get('effective_since') or prev.get('logged')
        if inception and start < inception:
            start = inception
        end = (calls[i + 1].get('effective_since') or calls[i + 1].get('logged')) if i + 1 < len(calls) else today
        if end < start:
            continue
        try:
            r, _ = perf.period_return(prev.get('allocation', {}), start, end, prices.price_on_or_after)
        except Exception as e:
            unpriced.append({'from': start, 'to': end, 'why': str(e)})
            daily_ok = False       # a hole in the curve means the drawdown below is not the whole story
            continue
        opening = equity
        equity *= (1.0 + r)
        legs.append({'from': start, 'to': end, 'held': prev.get('allocation', {}), 'return': r,
                     'open_period': i + 1 >= len(calls), 'equity_after': equity})
        # Fill in what happened BETWEEN the two calls. Without this, a dip that recovered before the next
        # call never appears in the drawdown at all — and drawdown is the number this product is sold on.
        try:
            path = perf.daily_path(prev.get('allocation', {}), start, end,
                                   prices.price_on_or_after, prices.daily_opens)
            scale = (1.0 + r) / path[-1][1] if path[-1][1] else 1.0    # end the leg exactly on the claim
            curve += [(d, opening * v * scale) for d, v in path]
        except Exception as e:
            daily_ok = False
            unpriced.append({'from': start, 'to': end, 'why': 'daily path unavailable: %s' % e,
                             'period_return_still_counted': True})
            curve.append((end, equity))

    days = (datetime.datetime.strptime(today, '%Y-%m-%d')
            - datetime.datetime.strptime(inception, '%Y-%m-%d')).days if inception else 0
    cash_days = sum((datetime.datetime.strptime(l['to'], '%Y-%m-%d')
                     - datetime.datetime.strptime(l['from'], '%Y-%m-%d')).days
                    for l in legs if perf.is_cash(l['held']))

    # Drawdown measured along the DAILY curve — every day between calls counts, not just the call dates.
    peak_eq = worst = 0.0
    peak_eq = 1.0
    for _, v in curve:
        peak_eq = max(peak_eq, v)
        worst = max(worst, (peak_eq - v) / peak_eq)
    cur_dd = (peak_eq - equity) / peak_eq if peak_eq > 0 else 0.0

    out.update({
        'days_live': days,
        'return_since_inception': equity - 1.0,
        'worst_drawdown_so_far': worst,
        'current_drawdown': cur_dd,
        'drawdown_basis': ('daily — every day between calls is measured' if daily_ok else
                           'INCOMPLETE — part of the curve could not be priced, so the true drawdown may '
                           'be worse than shown'),
        'days_in_cash': cash_days,
        'days_invested': max(days - cash_days, 0),
        'pct_time_in_cash': (cash_days / days) if days else None,
        'curve_points': len(curve),
        'periods': legs,
        'unpriced_periods': unpriced,
    })

    # --- the comparison, flattering or not ---
    try:
        _, b0 = prices.price_on_or_after('BTC', inception)
        _, b1 = prices.price_on_or_after('BTC', today)
        btc = b1 / b0 - 1.0
        out['btc_buy_hold_same_window'] = btc
        out['vs_btc'] = (equity - 1.0) - btc
        out['ahead_of_btc'] = (equity - 1.0) > btc
    except Exception as e:
        out['btc_buy_hold_same_window'] = None
        out['btc_comparison_error'] = str(e)

    if days < 90:
        out['caveat'] = ('This record is %d days old. That is far too short to judge a system whose '
                         'drawdowns last months — treat these numbers as a starting point, not evidence.'
                         % days)
    if unpriced:
        out['caveat_unpriced'] = ('%d period(s) could not be priced and are EXCLUDED from the figures '
                                  'above, which therefore understate or overstate the true result.'
                                  % len(unpriced))
    return out, data


if __name__ == '__main__':
    s, _ = build()
    with open(os.path.join(ROOT, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print('Wrote summary.json')
    print('  live %s days | return %s | worst DD %s | in cash %s of the time'
          % (s.get('days_live'), perf.fmt_pct(s.get('return_since_inception')),
             perf.fmt_mag(s.get('worst_drawdown_so_far')),
             perf.fmt_mag(s.get('pct_time_in_cash'))))
    b = s.get('btc_buy_hold_same_window')
    if b is not None:
        print('  Bitcoin over the same window: %s  -> we are %s' %
              (perf.fmt_pct(b), 'AHEAD' if s.get('ahead_of_btc') else 'BEHIND'))
    if s.get('caveat'):
        print('  ' + s['caveat'])
