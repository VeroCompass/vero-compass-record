#!/usr/bin/env python3
"""
Two properties, and the second one is the one that matters.

An alarm has to do BOTH of these or it gets ignored by a human within a week:
  1. FIRE when the same as-of date produces different numbers  -> a real source revision
  2. STAY SILENT when the as-of date simply advanced           -> the window got longer, nothing is wrong

The first version of this detector had property 1 and not property 2. It looked correct because it was
tested three times inside one UTC day, so valued_as_of never moved - the exact condition every scheduled
run changes. It would have fired every single day, asserting "same period" while comparing two different
periods, and been muted as noise long before a real revision arrived.

No network: these tests drive the comparison function with fixtures.

    python scripts/test_revision_detector.py
"""
import json, os, sys, tempfile, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_summary


def run_case(name, published, fresh, expect_fire):
    """Point the module at a temp ROOT holding `published`, then compare `fresh` against it."""
    tmp = tempfile.mkdtemp(prefix='revdet_')
    real_root = build_summary.ROOT
    try:
        build_summary.ROOT = tmp
        with open(os.path.join(tmp, 'summary.json'), 'w', encoding='utf-8') as f:
            json.dump(published, f)
        rev = build_summary.revision_vs_published(fresh)
        fired = bool(rev) and not rev.get('skipped')
        ok = (fired == expect_fire)
        print('  %-52s %s' % (name, 'PASS' if ok else 'FAIL'))
        if not ok:
            print('        expected %s, got %s (%s)'
                  % ('FIRE' if expect_fire else 'SILENCE', 'FIRE' if fired else 'SILENCE', rev))
        elif fired:
            print('        -> %s' % ', '.join('%s %+.2fpp' % (k, v['change_pp'])
                                              for k, v in rev['changed'].items()))
        return ok
    finally:
        build_summary.ROOT = real_root
        shutil.rmtree(tmp, ignore_errors=True)


BASE = {'valued_as_of': '2026-08-28', 'return_since_inception': 0.0710,
        'btc_buy_hold_same_window': 0.2774, 'worst_drawdown_so_far': 0.0196}


def main():
    ok = True
    print('  REVISION DETECTOR - both properties\n')

    # 1. FIRES: same as-of date, revised numbers. This is the real 2026-08-28 gold incident.
    ok &= run_case('fires on a real revision (same as-of, +7.1% -> +5.8%)',
                   BASE, dict(BASE, return_since_inception=0.0583), True)

    # 2. SILENT: the as-of date advanced. Numbers move because the window grew, not because data changed.
    #    This is the case that fired every day in the first version.
    ok &= run_case('SILENT when as-of advances (the daily-run case)',
                   BASE, dict(BASE, valued_as_of='2026-08-29',
                              return_since_inception=0.0583,
                              btc_buy_hold_same_window=0.2391), False)

    # 3. SILENT: nothing changed at all.
    ok &= run_case('silent when nothing changed', BASE, dict(BASE), False)

    # 4. SILENT: a legacy summary with no valued_as_of - same period cannot be established, so no claim.
    legacy = {k: v for k, v in BASE.items() if k != 'valued_as_of'}
    ok &= run_case('silent when the previous summary predates valued_as_of', legacy, dict(BASE), False)

    # 5. FIRES: a move below the noise floor must NOT fire; a move above it must.
    ok &= run_case('silent on a move inside the 0.1pp noise floor',
                   BASE, dict(BASE, return_since_inception=0.07105), False)
    ok &= run_case('fires just above the noise floor',
                   BASE, dict(BASE, return_since_inception=0.0725), True)

    print('\n  %s' % ('BOTH PROPERTIES HOLD.' if ok else 'A PROPERTY FAILED - do not trust this alarm.'))
    return 0 if ok else 1


if __name__ == '__main__':
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    sys.exit(main())
