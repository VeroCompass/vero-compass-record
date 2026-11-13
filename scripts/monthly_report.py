#!/usr/bin/env python3
"""
Vero Compass: draft the monthly honest report, from the public record and public prices.

    python scripts/monthly_report.py 2026-09                      # the draft, as Markdown, on stdout
    python scripts/monthly_report.py 2026-09 --out FILE           # the draft, written to FILE
    python scripts/monthly_report.py --check reports/2026-09.md   # recompute a published report's figures

It only DRAFTS. A person reads every draft before it goes out, and publishing one needs Enzo's OK.

HOW THE FIGURES ARE MEASURED, so anyone can recompute them:
- The record's equity is build_summary.equity_curve(): each call's holding period priced at daily opens, net of
  trading costs, on every day, and ended exactly on the result the record published for that period. It is the same
  curve the headline table on the page is built from.
- A month runs from its first daily open to the next month's first daily open, in UTC. When a call is acted on at
  that open, its trading costs count in the month that ends there.
- Bitcoin over the same days uses the same daily opens.
- Drawdown is measured against the record's highest value since it began, on every day of the curve.
- A published report carries its figures in a comment at the end. --check recomputes them, and so does verify.py
  for every report listed in calls.json.

HOUSE STYLE, enforced here:
- no engine numbers: call reasons, corrections and engine-change texts are never quoted, only pointed to;
- no em-dashes or en-dashes anywhere in the text;
- every honest negative is followed by its true context, computed from the same data.
"""
import argparse
import datetime
import json
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, 'reconfigure'):
        _s.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices
import perf
import build_summary
from add_call import alloc_str

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOL = 0.0015                                  # verify.py's tolerance: 0.15 percentage points
MARK = 'vero-compass-report-figures'
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December']


def month_bounds(month):
    """'2026-09' -> ('2026-09-01', '2026-10-01'): the month's first daily open, and the next month's."""
    y, m = (int(x) for x in month.split('-'))
    return datetime.date(y, m, 1).isoformat(), datetime.date(y + (m == 12), m % 12 + 1, 1).isoformat()


def days_between(a, b):
    return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days


def value_at(points, d):
    """Equity at the open of date d, after any trade made at that open: the last point dated on or before d."""
    v = None
    for day, val in points:
        if day > d:
            break
        v = val
    return v


def call_date(c):
    return c.get('effective_since') or c.get('logged')


def held_names(alloc):
    return [k for k in (alloc or {}) if k.upper() != 'CASH']


def name(sym):
    return 'gold' if sym.upper() == 'GOLD' else sym


def listing(names):
    names = [name(x) for x in names]
    return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]


def pts(x):
    """Percentage points, signed, ASCII minus. Below a tenth of a point it says so instead of printing -0.0."""
    if abs(x) < 0.0005:
        return 'less than 0.1 points'
    return '%+.1f points' % (x * 100.0)


def leg_points(path_row):
    """The daily points of one holding period, exactly as equity_curve() drew them."""
    start, end, alloc, opening, scale = path_row
    path = perf.daily_path(alloc, start, end, prices.price_on_or_after, prices.daily_opens)
    return [(d, opening * v * scale) for d, v in path]


def contributions(path_row, a, b):
    """How much each holding moved the book between a and b, as a fraction of the book at a's value scale.
    Mirrors perf.daily_path: value = opening * scale * (1 - entry cost) * (cash + sum(w * price / start price))."""
    start, end, alloc, opening, scale = path_row
    k = opening * scale * (1.0 - perf.turnover_cost(alloc))
    out = {}
    for sym in held_names(alloc):
        w = float(alloc[sym]) / 100.0
        _, base = prices.price_on_or_after(sym.upper(), start)
        series = prices.daily_opens(sym.upper(), start, end)

        def px(d):
            have = [x for x in series if x <= d]
            return series[max(have)] if have else base
        pa, pb = px(a), px(b)
        out[sym.upper()] = {'value': k * w * (pb - pa) / base, 'price_change': pb / pa - 1.0}
    return out


def figures(data, month, as_of=None):
    """Every number a report states, for one month. Reads the record and public prices; writes nothing."""
    as_of = as_of or prices.last_settled_date()
    m0, m1 = month_bounds(month)
    inception = data.get('log_inception')
    ec = build_summary.equity_curve(data, as_of)
    curve, resolved, pending = ec['curve'], ec['resolved'], ec['pending']
    covered = max((d for d, _ in curve), default=None)
    f = {'month': month, 'month_start': m0, 'month_end': m1, 'as_of': as_of, 'inception': inception,
         'covered_through': covered,
         'pending_count': len(pending)}
    w0 = max(m0, inception) if inception else m0
    w1 = min(m1, covered) if covered else None
    calls_in = [c for c in resolved if m0 <= call_date(c) < m1]
    f['calls'] = []
    for c in calls_in:
        i = resolved.index(c)
        prev = resolved[i - 1] if i > 0 else None
        f['calls'].append({'n': c['n'], 'date': call_date(c), 'logged': c.get('logged'), 'state': c.get('state'),
                           'allocation': c.get('allocation'), 'previous': prev.get('allocation') if prev else None,
                           'previous_n': prev.get('n') if prev else None,
                           'previous_state': prev.get('state') if prev else None,
                           'previous_date': call_date(prev) if prev else None,
                           'result': c.get('result_since_prior'), 'basis': c.get('result_basis'),
                           'late': 'LOGGED LATE' in (c.get('reason') or '')})
    f['corrections'] = []
    nums_in = {c['n'] for c in calls_in}
    for c in data.get('corrections') or []:
        refs = sorted({int(x) for x in re.findall(r'#(\d+)', c.get('corrects') or '')} & nums_in)
        if refs:
            f['corrections'].append({'date': c.get('date'), 'calls': refs})
    f['engine_changes'] = [{'date': e.get('date'), 'from': e.get('from'), 'to': e.get('to')}
                           for e in data.get('engine_changes') or [] if m0 <= (e.get('date') or '') < m1]

    if not curve or w1 is None or w1 <= w0:
        f['window'] = None
        return f
    f['window'] = [w0, w1]
    f['partial'] = (w0, w1) != (m0, m1)
    e0, e1 = value_at(curve, w0), value_at(curve, w1)
    f['return'] = e1 / e0 - 1.0

    # Bitcoin over the same days: the open period ends at the last settled bar, so it is valued backward there
    _, b0 = prices.price_on_or_after('BTC', w0)
    end_getter = prices.price_on_or_before if (w1 == as_of and not pending) else prices.price_on_or_after
    _, b1 = end_getter('BTC', w1)
    f['btc_return'] = b1 / b0 - 1.0

    # Drawdown and time below the previous high, on every day of the curve since the record began
    peak, peak_day, worst, worst_day, below = 0.0, None, 0.0, None, {}
    for d, v in curve:
        if v > peak:
            peak, peak_day = v, d
        if w0 <= d <= w1 and (peak - v) / peak > worst:
            worst, worst_day = (peak - v) / peak, d
        if w0 <= d < w1:
            below[d] = v < peak * (1.0 - 1e-12)
        if d > w1:
            break
    f['worst_drawdown'] = worst
    f['worst_day'] = worst_day
    f['days'] = days_between(w0, w1)
    f['days_below_high'] = sum(1 for x in below.values() if x)
    f['high_day'] = peak_day
    f['end_drawdown'] = (peak - e1) / peak

    bpx = prices.daily_opens('BTC', inception or w0, w1)
    bpeak, bworst = 0.0, 0.0
    for d in sorted(bpx):
        bpeak = max(bpeak, bpx[d])
        if w0 <= d <= w1:
            bworst = max(bworst, (bpeak - bpx[d]) / bpeak)
    f['btc_worst_drawdown'] = bworst

    # What each holding did, period by period inside the window
    f['periods'], f['contributions'], f['price_change'], f['held_days'] = [], {}, {}, {}
    riskoff = 0
    for row in ec['paths']:
        start, end = row[0], row[1]
        a, b = max(start, w0), min(end, w1)
        if a >= b:
            continue
        lp = leg_points(row)
        call = next((c for c in resolved if call_date(c) == start or (c is resolved[0] and start == inception)),
                    None)
        state = (call or {}).get('state')
        if state == 'risk-off':
            riskoff += days_between(a, b)
        f['periods'].append({'from': a, 'to': b, 'held': row[2], 'state': state, 'call': (call or {}).get('n'),
                             'return': value_at(lp, b) / value_at(lp, a) - 1.0})
        for sym, x in contributions(row, a, b).items():
            f['contributions'][sym] = f['contributions'].get(sym, 0.0) + x['value'] / e0
            f['price_change'][sym] = (1.0 + f['price_change'].get(sym, 0.0)) * (1.0 + x['price_change']) - 1.0
            f['held_days'][sym] = f['held_days'].get(sym, 0) + days_between(a, b)
    f['riskoff_days'] = riskoff
    f['costs_and_rounding'] = f['return'] - sum(f['contributions'].values())
    f['start_holding'] = next((p for p in f['periods'] if p['from'] == w0), None)
    f['end_holding'] = f['periods'][-1] if f['periods'] else None
    return f


def checkable(f):
    """The figures a report states, as stored in its comment and recomputed by --check and verify.py."""
    keys = ('return', 'btc_return', 'worst_drawdown', 'end_drawdown', 'btc_worst_drawdown', 'costs_and_rounding',
            'days', 'days_below_high', 'riskoff_days')
    out = {k: f.get(k) for k in keys}
    out.update({'month': f['month'], 'window': f.get('window'),
                'contributions': {k: round(v, 6) for k, v in (f.get('contributions') or {}).items()}})
    return out


def render(f, generated=None):
    """The report as Markdown. Every negative is followed by its context."""
    generated = generated or prices.today_utc()
    y, m = f['month'].split('-')
    title = '%s %s' % (MONTHS[int(m) - 1], y)
    L = ['<!-- DRAFT generated %s by scripts/monthly_report.py. A person reads it before it is published, and '
         'publishing needs Enzo\'s OK. -->' % generated, '', '# Vero Compass: %s' % title, '']
    if not f.get('window'):
        L += ['No figures for %s yet.' % title, '']
        return '\n'.join(L) + '\n'
    w0, w1 = f['window']
    span = 'From %s to %s' % (w0, w1)
    why_short = ''
    if f.get('partial') and w1 == f['as_of']:
        why_short = ', the last settled day so far'
    L += ['%s (daily opens, UTC)%s. Every figure is computed from the public record and public prices, the same way '
          'as the record\'s headline table; see "Check it yourself" at the end.' % (span, why_short), '']

    # --- what the system did ---
    L += ['## What the system did', '']
    sh = f.get('start_holding')
    if sh:
        L.append('- It began %s %s, holding %s%s.' % ('the month' if w0 == f['month_start'] else 'on ' + w0,
                                                    sh['state'] or '', alloc_str(sh['held']),
                                                    ' (call #%d)' % sh['call'] if sh.get('call') else ''))
    for c in f['calls']:
        prev = c.get('previous') or {}
        new = c.get('allocation') or {}
        sold = [k for k in held_names(prev) if k not in new]
        bought = [k for k in held_names(new) if k not in prev]
        kept = [k for k in held_names(new) if k in prev]
        moves = []
        if sold:
            moves.append('sold %s' % listing(sold))
        if bought:
            moves.append('bought %s' % listing(bought))
        if kept:
            moves.append('kept %s' % listing(kept))
        if len(moves) > 1:
            moves[-1] = 'and ' + moves[-1]
        changed_state = c.get('state') and c.get('previous_state') and c['state'] != c['previous_state']
        turned = ('turned %s' if changed_state else 'stayed %s') % (c.get('state') or '')
        line = '- On %s (call #%d) it %s%s. It then held %s.' % (
            c['date'], c['n'], turned, (': it ' + ', '.join(moves)) if moves else '', alloc_str(new))
        L.append(line)
        if c.get('late'):
            L.append('  Call #%d was logged late: the indicator made the move before it was written here. The record '
                     'counts it from %s, as the entry says.' % (c['n'], c['date']))
    eh = f.get('end_holding')
    if eh:
        L.append('- It %s %s, holding %s.' % ('ended the month' if w1 == f['month_end'] else 'was, on ' + w1 + ',',
                                            eh['state'] or '', alloc_str(eh['held'])))
    L.append('')

    # --- the result ---
    r, b = f['return'], f['btc_return']
    L += ['## The month\'s result', '',
          'The record returned %s after trading costs. Simply holding Bitcoin over the same days returned %s.'
          % (perf.fmt_pct(r), perf.fmt_pct(b))]
    if r < 0:
        L.append('The record lost money this month. Context: Bitcoin %s %s over the same days.'
                 % ('fell' if b < 0 else 'rose', perf.fmt_mag(b)))
    if r < b:
        ctx = []
        if f['riskoff_days']:
            held = {tuple(sorted(held_names(p['held']))) for p in f['periods'] if p['state'] == 'risk-off'}
            what = 'only gold' if held == {('GOLD',)} else 'only cash' if held == {()} else 'only gold or cash'
            s = 'for %d of the %d days the book was risk-off and held %s' % (f['riskoff_days'], f['days'], what)
            # Facts only: a risk-off stretch ended by a call that was logged late lasted longer in the record than
            # in the indicator, and the reader must be told so rather than given the rule's usual reason.
            late = [c for c in f['calls'] if c.get('late') and c.get('previous_state') == 'risk-off'
                    and c.get('state') == 'risk-on']
            if late:
                s += (', and the call that ended that stretch (call #%d) was logged late, so the record stayed '
                      'out longer than the indicator did' % late[0]['n'])
            ctx.append(s)
        drags = sorted(((v, k) for k, v in f['contributions'].items() if v < 0))
        if drags:
            ctx.append('the largest drag was %s (%s)' % (name(drags[0][1]), pts(drags[0][0])))
        elif f['contributions']:
            top = max(f['contributions'].items(), key=lambda kv: kv[1])
            ctx.append('every holding rose, the most being %s (%s), but not as far as Bitcoin' % (name(top[0]),
                                                                                                   pts(top[1])))
        L.append('That is %.1f points behind simply holding Bitcoin. Context: %s.' % ((b - r) * 100.0, '; '.join(ctx)
                                                                                      or 'see the holdings below'))
    elif r > b:
        L.append('That is %.1f points ahead of simply holding Bitcoin.' % ((r - b) * 100.0))
    L.append('')

    # --- drawdown ---
    L += ['## Drawdown and time below the previous high', '']
    if f['worst_drawdown'] > 0 or f['days_below_high']:
        L.append('Its deepest point this month was %s below its previous high, and it spent %d of the %d days below '
                 'that high. It ended the month %s below it. Context: Bitcoin\'s deepest point over the same days was '
                 '%s below its own high since the record began.'
                 % (perf.fmt_mag(f['worst_drawdown']), f['days_below_high'], f['days'],
                    perf.fmt_mag(f['end_drawdown']), perf.fmt_mag(f['btc_worst_drawdown'])))
        where = next((p for p in f['periods'] if p['from'] <= (f['worst_day'] or '') <= p['to']), None)
        if f['worst_day'] and where:
            L.append('The deepest point came on %s, while the book held %s.' % (f['worst_day'],
                                                                             alloc_str(where['held'])))
        if f['high_day'] and f['high_day'] < w0:
            L.append('Its previous high was set on %s.' % f['high_day'])
    else:
        L.append('It was never below its previous high this month. Bitcoin\'s deepest point over the same days was '
                 '%s below its own high since the record began.' % perf.fmt_mag(f['btc_worst_drawdown']))
    L.append('')

    # --- wins and losses ---
    L += ['## Wins and losses', '']
    order = sorted(f['contributions'].items(), key=lambda kv: -kv[1])
    wins = [(k, v) for k, v in order if v > 0.00005]
    losses = [(k, v) for k, v in order if v < -0.00005][::-1]
    def held_line(k, v):
        days = f['held_days'][k]
        return '- %s: %s. Held %s; its price %s %s over those days.' % (
            name(k)[0].upper() + name(k)[1:], pts(v), 'all %d days' % f['days'] if days >= f['days'] else
            'for %d of the %d days' % (days, f['days']), 'rose' if f['price_change'][k] >= 0 else 'fell',
            perf.fmt_mag(f['price_change'][k]))
    L += ['What helped:'] + ([held_line(k, v) for k, v in wins] or ['- nothing this month'])
    L += ['', 'What hurt:'] + ([held_line(k, v) for k, v in losses] or ['- nothing this month'])
    if not f['contributions']:
        L += ['', 'The book held only cash, which neither gains nor loses.']
    costs = 'Trading costs and small pricing differences: %s.' % pts(f['costs_and_rounding'])
    if f['costs_and_rounding'] <= -0.0005:
        costs += (' The record charges a full exit and re-entry of the whole book at every call, including the '
                  'holdings it keeps, so a follower who trades only the changes pays less.')
    L += ['', costs, '']

    # --- each call's published result ---
    if f['calls']:
        L += ['## Each call\'s published result', '',
              'The record publishes each period\'s result with the call that ends it:', '']
        for c in f['calls']:
            if c.get('result') and c.get('previous_n'):
                L.append('- Call #%d: %s for call #%d\'s holding, from %s to %s (%s).'
                         % (c['n'], c['result'], c['previous_n'], c['previous_date'], c['date'],
                            'measured from prices' if c.get('basis') == 'computed' else 'entered by hand'))
        L.append('')

    # --- corrections and changes ---
    notes = []
    for c in f['corrections']:
        notes.append('- On %s, a correction concerning call%s %s was published. The original entr%s as %s, and the '
                     'correction is on the record page under "Corrections".'
                     % (c['date'], 's' if len(c['calls']) > 1 else '', listing(['#%d' % n for n in c['calls']]),
                        'ies stay' if len(c['calls']) > 1 else 'y stays', 'they were' if len(c['calls']) > 1
                        else 'it was'))
    for e in f['engine_changes']:
        notes.append('- On %s, the engine changed from %s to %s. What changed, why, and what it costs are on the '
                     'record page under "What has changed, and when".' % (e['date'], e['from'], e['to']))
    if notes:
        L += ['## Corrections and changes', ''] + notes + ['']

    L += ['## Check it yourself', '',
          'Every figure here is recomputed from public prices by `python scripts/monthly_report.py --check '
          'reports/%s.md`, with the code that builds the record\'s headline table. `python scripts/verify.py` runs '
          'the same check on every published report.' % f['month'], '',
          '<!-- %s %s -->' % (MARK, json.dumps(checkable(f), sort_keys=True))]
    text = '\n'.join(L) + '\n'
    bad = [ch for ch in ('—', '–') if ch in text]
    assert not bad, 'house style: no em-dashes or en-dashes in a report'
    return text


def check_text(text, data, as_of=None):
    """Recompute a report's stored figures. Returns (ok, lines)."""
    m = re.search(r'<!-- %s (\{.*\}) -->' % MARK, text)
    if not m:
        return False, ['  !! no figures block in this report, so it cannot be checked']
    stored = json.loads(m.group(1))
    fresh = checkable(figures(data, stored['month'], as_of))
    lines, ok = [], True
    for k, v in stored.items():
        w = fresh.get(k)
        if isinstance(v, float) or isinstance(w, float):
            good = v is not None and w is not None and abs(v - w) <= TOL
        elif isinstance(v, dict):
            good = set(v) == set(w or {}) and all(abs(v[x] - w[x]) <= TOL for x in v)
        else:
            good = v == w
        if not good:
            ok = False
            lines.append('  !! %s: the report says %s, recomputed %s' % (k, v, w))
    lines.insert(0, '  report %s: %s' % (stored['month'], 'every figure reproduces' if ok else 'DOES NOT REPRODUCE'))
    return ok, lines


def main():
    ap = argparse.ArgumentParser(description='Draft the monthly honest report from the public record.')
    ap.add_argument('month', nargs='?', help='YYYY-MM')
    ap.add_argument('--out', default='', help='write the draft to this file instead of stdout')
    ap.add_argument('--check', default='', help='recompute the figures of a published report')
    ap.add_argument('--root', default=ROOT, help='the record to read (default: this repository)')
    a = ap.parse_args()
    with open(os.path.join(a.root, 'calls.json'), encoding='utf-8-sig') as fh:
        data = json.load(fh)
    if a.check:
        with open(a.check, encoding='utf-8') as fh:
            ok, lines = check_text(fh.read(), data)
        print('\n'.join(lines))
        sys.exit(0 if ok else 1)
    if not a.month or not re.fullmatch(r'\d{4}-\d{2}', a.month):
        ap.error('give a month as YYYY-MM')
    text = render(figures(data, a.month))
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as fh:
            fh.write(text)
        print('draft written to %s' % a.out)
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main()
