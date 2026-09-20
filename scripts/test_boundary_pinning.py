#!/usr/bin/env python3
"""
Does a published period still reproduce after the boundary moves?

THE BUG THIS PROTECTS AGAINST, which is not hypothetical — it shipped on 2026-09-20. Call #3 was logged
on a Sunday. Gold had no session on or after that date, so `price_on_or_after` substituted the previous
Friday's open and the entry recorded that session. On Monday the same boundary resolves to Monday's open,
so re-deriving the period from today's data gives a different answer than the one published — and
`verify.py` would have reported the log as not reproducing, on an entry that was honest.

Two behaviours are tested, and both are mutated to prove the test can fail:
  1. a published period is priced at the SESSIONS THE ENTRY NAMED  (perf.pinned_getter)
  2. the PRICE still comes from the source, never from the entry    (so a faked price cannot hide)

No network: the price getters here are fakes, which is also the point — the mechanism is about which
DATE is asked for, and that is testable without a market.

    python scripts/test_boundary_pinning.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perf

# gold: no Saturday/Sunday session. Friday 09-18 and Monday 09-21 exist, and they differ enough that
# using the wrong one moves the period well past verify.py's 0.15pp tolerance.
SOURCE = {('GOLD', '2026-08-10'): 4400.0,
          ('GOLD', '2026-09-18'): 4381.6,
          ('GOLD', '2026-09-21'): 4300.0}
PUBLISHED_DETAIL = [{'symbol': 'GOLD', 'weight': 100.0,
                     'start_date': '2026-08-10', 'end_date': '2026-09-18',
                     'start_price': 4400.0, 'end_price': 4381.6}]
ALLOC = {'GOLD': 100}
FAILURES = []


def exact(symbol, date):
    key = (symbol.upper(), date)
    if key not in SOURCE:
        raise KeyError('no %s session on %s' % (symbol, date))
    return date, SOURCE[key]


def resolve_forward(symbol, date):
    """Stand-in for prices.price_on_or_after: the first session on or after `date`, else the last one
    before it — the fallback that makes an already-published boundary move."""
    have = sorted(d for (s, d) in SOURCE if s == symbol.upper())
    fwd = [d for d in have if d >= date]
    d = fwd[0] if fwd else [d for d in have if d < date][-1]
    return d, SOURCE[(symbol.upper(), d)]


def check(name, condition, detail=''):
    print(('  PASS  ' if condition else '  FAIL  ') + name + (('   ' + detail) if detail else ''))
    if not condition:
        FAILURES.append(name)


def period(detail, end_boundary='2026-09-20'):
    g0 = perf.pinned_getter(detail, 'start_date', exact, resolve_forward)
    g1 = perf.pinned_getter(detail, 'end_date', exact, resolve_forward)
    r, rows = perf.period_return(ALLOC, '2026-08-09', end_boundary, g0, g1)
    return r, rows


print('1. a published period reproduces on the sessions the entry named')
pinned, rows = period(PUBLISHED_DETAIL)
check('prices the legs on 2026-08-10 -> 2026-09-18',
      (rows[0]['start_date'], rows[0]['end_date']) == ('2026-08-10', '2026-09-18'),
      '%s -> %s' % (rows[0]['start_date'], rows[0]['end_date']))
check('published claim reproduces', abs(pinned - (-0.00718)) < 0.0015, '%.4f' % pinned)

print('\n2. MUTATION — drop the recorded dates and the same code re-resolves the boundary')
moved, moved_rows = period(None)
check('boundary moves to the Monday session', moved_rows[0]['end_date'] == '2026-09-21',
      moved_rows[0]['end_date'])
check('and the period moves past verify.py\'s 0.15pp tolerance (so test 1 could have failed)',
      abs(moved - pinned) > 0.0015, '%.2fpp apart' % (abs(moved - pinned) * 100))

print('\n3. the PRICE comes from the source, not from the entry')
lying = [dict(PUBLISHED_DETAIL[0], end_price=9999.0)]      # entry claims a price the source disagrees with
r_lie, _ = period(lying)
check('a faked price in the entry changes nothing', abs(r_lie - pinned) < 1e-12, '%.6f' % r_lie)

print('\n4. MUTATION — an entry naming a session that does not exist must raise, never guess')
try:
    period([dict(PUBLISHED_DETAIL[0], end_date='2026-09-19')])   # a Saturday: no session
    check('raises on an impossible session', False, 'it returned a number instead')
except KeyError:
    check('raises on an impossible session', True)

print('\n' + ('FAILED: ' + ', '.join(FAILURES) if FAILURES else 'All boundary-pinning checks passed.'))
sys.exit(1 if FAILURES else 0)
