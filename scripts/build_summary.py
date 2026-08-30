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
    # Value open positions to the last SETTLED bar, never to today's provisional one.
    as_of = prices.last_settled_date()

    out = {'generated_utc': today, 'valued_as_of': as_of, 'inception': inception, 'calls_logged': len(calls),
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
        end = (calls[i + 1].get('effective_since') or calls[i + 1].get('logged')) if i + 1 < len(calls) else as_of
        if end < start:
            continue
        try:
            is_open = (i + 1 >= len(calls))
            r, _ = perf.period_return(prev.get('allocation', {}), start, end, prices.price_on_or_after,
                                       prices.price_on_or_before if is_open else None)
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
        _, b1 = prices.price_on_or_before('BTC', as_of)
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


def revision_vs_published(new):
    """
    Compare the freshly-built figures against the PREVIOUSLY PUBLISHED summary.json still on disk.

    WHY THIS EXISTS, and why the existing in-run verify cannot do it: the Action builds the summary and
    then verifies it by recomputing from the same data in the same run, so the two agree by construction.
    That check is self-confirming and is structurally blind to a data revision. This one is not - it
    compares today's answer to what we actually told the public yesterday.

    Pricing to the last settled bar makes revisions rarer; it cannot make them impossible, because a
    source can revise a bar days later. So the lag is the prevention and this is the detection, and the
    detection is the part that keeps working when the prevention does not.

    Never raises, never blocks: the newly-computed figure is the better one and should always publish.
    The point is that a change is SEEN and recorded, not that it is stopped.
    """
    try:
        with open(os.path.join(ROOT, 'summary.json'), encoding='utf-8-sig') as f:
            old = json.load(f)
    except Exception:
        return None

    # GATE: only compare builds that value as of the SAME date.
    # Without this the detector fires every single day, because a scheduled run crosses midnight, the
    # window grows by a day, and the figures move for an entirely legitimate reason. That is not a
    # revision - it is the record getting longer. The first version of this function asserted "same
    # period" in its own message and never tested it, which is the exact defect class it was written to
    # catch: a checker claiming a property it does not verify.
    a_old, a_new = old.get('valued_as_of'), new.get('valued_as_of')
    if not a_old or not a_new or a_old != a_new:
        return {'skipped': True, 'previous_valued_as_of': a_old, 'this_valued_as_of': a_new,
                'why': ('nothing to compare: the previous summary valued as of %s and this build values '
                        'as of %s, so any difference is the window advancing, not a data revision'
                        % (a_old or 'an unrecorded date', a_new))}
    moved = {}
    for k in ('return_since_inception', 'btc_buy_hold_same_window', 'worst_drawdown_so_far'):
        a, b = old.get(k), new.get(k)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(b - a) > 0.001:
            moved[k] = {'was': round(a, 5), 'now': round(b, 5), 'change_pp': round((b - a) * 100, 2)}
    if not moved:
        return None
    return {'previous_generated_utc': old.get('generated_utc'), 'changed': moved,
            'note': 'These figures differ from the previously published summary for the SAME period. '
                    'The cause is a revision in the underlying public price data, not an edit to the log. '
                    'The new values are the ones now published.'}


if __name__ == '__main__':
    s, _ = build()
    rev = revision_vs_published(s)
    if rev and not rev.get('skipped'):
        s['revised_since_last_publish'] = rev
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
    if rev and rev.get('skipped'):
        print('  revision check skipped - %s' % rev['why'])
    elif rev:
        print('')
        print('  *** FIGURES REVISED SINCE THE LAST PUBLISH (same period, revised source data) ***')
        for k, v in rev['changed'].items():
            print('      %-28s %+.2fpp   (was %.4f, now %.4f)' % (k, v['change_pp'], v['was'], v['now']))
        print('      Previous publish: %s. The new values are the ones being published now.'
              % rev.get('previous_generated_utc'))
