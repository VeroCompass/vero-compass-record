#!/usr/bin/env python3
"""
VERIFY THIS RECORD YOURSELF.

You do not have to trust any number in this log. This script re-derives every performance figure from
public market data and tells you whether the record's own claims hold up. It needs nothing but Python —
no account, no API key, no installed packages.

    python scripts/verify.py

What it does:
  * reads calls.json (the log)
  * for every completed call, fetches the real daily opening prices of whatever was held, on the exact
    dates it was held, from Binance (crypto) and Yahoo (gold) — both public and free
  * recomputes the return, net of the same fee and spread model the backtest uses
  * compares its own answer to what the log claims, and prints any disagreement
  * shows the same window for simply holding Bitcoin, so you can see whether this beat doing nothing

Exit code 0 = every claim reproduced. 1 = at least one did not. 2 = could not check (say so, don't guess).

If you find a discrepancy this script cannot explain, that is a real finding — and the whole point of
publishing it.
"""
import json, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices, perf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOL = 0.0015           # 0.15pp — allows for rounding and small feed differences between exchanges
SUMMARY_MAX_AGE_DAYS = 3   # the page advertises a real-time record; 3 days is grace, not target



def _days(a, b):
    f = '%Y-%m-%d'
    return (datetime.datetime.strptime(b, f) - datetime.datetime.strptime(a, f)).days


def check_summary(data, calls, equity, complete):
    """
    Check summary.json — the headline table the site renders, and the numbers most people actually read.

    This check did not exist, and the table sat eighteen days stale while this script reported
    'ALL CLAIMS REPRODUCED' — truthfully, about calls.json, which was never the part that had rotted.
    A derived, human-read figure needs a FRESHNESS test as much as a correctness one: computed perfectly,
    three weeks ago, is still a broken promise on a page that advertises a record kept in real time.
    """
    print('-' * 72)
    print('  THE HEADLINE TABLE (summary.json)')
    try:
        with open(os.path.join(ROOT, 'summary.json'), encoding='utf-8-sig') as f:
            s = json.load(f)
    except Exception as e:
        print('  !! could not read summary.json (%s) — the site has nothing to render.' % e)
        return 1

    gen = s.get('generated_utc')
    inception = s.get('inception') or data.get('log_inception')
    today = prices.today_utc()
    if not (gen and inception):
        print('  !! summary.json does not record when it was generated, so it cannot be trusted.')
        return 1

    age, rc = _days(gen, today), 0
    print('  generated %s · %d day(s) ago · today is %s (UTC)' % (gen, age, today))

    stated, expect = s.get('days_live'), _days(inception, gen)
    if stated != expect:
        print('  !! self-inconsistent: days_live says %s, but %s minus %s is %d.'
              % (stated, gen, inception, expect))
        rc = 1

    if age > SUMMARY_MAX_AGE_DAYS:
        print('  !! STALE by %d days. Nothing here is false — it is old, and old drifts whichever' % age)
        print('     way the market happened to move, including the flattering way.')
        print('     It says "%s days live"; the true figure today is %d.' % (stated, _days(inception, today)))
        print('     A record that advertises itself as real-time has to actually be one.')
        return 1

    if not complete:
        print('  (a period above could not be priced, so the total is not cross-checked here.)')
        return rc

    last = calls[-1]
    start = last.get('effective_since') or last.get('logged')
    try:
        openr, _ = perf.period_return(last.get('allocation', {}), start, gen, prices.price_on_or_after)
    except Exception as e:
        print('  could not price the still-open period (%s) — total not cross-checked.' % e)
        return rc

    mine = equity * (1.0 + openr) - 1.0
    claimed = s.get('return_since_inception')
    print('  Independently computed return since inception: %s' % perf.fmt_pct(mine))
    print('  The table claims                             : %s' % perf.fmt_pct(claimed))
    if claimed is None or abs(float(claimed) - mine) > TOL:
        print('  => DISAGREES — the published table does not reproduce.')
        return 1
    print('  => MATCHES (within %.2fpp)' % (TOL * 100))
    return rc


def main():
    path = os.path.join(ROOT, 'calls.json')
    try:
        with open(path, encoding='utf-8-sig') as f:
            data = json.load(f)
    except Exception as e:
        print('Could not read %s (%s).' % (path, e)); return 2
    calls = data.get('calls') or []

    print('=' * 72)
    print('  VERO COMPASS — INDEPENDENT VERIFICATION')
    print('=' * 72)
    print('  Recomputing every claim from public prices. Nothing here trusts the log.')
    print('  %d call(s) on record. Inception %s.\n' % (len(calls), data.get('log_inception', '?')))

    if len(calls) < 2:
        print('  Only the opening entry exists, so there is no completed holding period to check yet.')
        print('  The record is anchored but has not yet made a claim that can be verified.')
        print('\n  Nothing to disprove — and nothing to take on faith either.')
        return check_summary(data, calls, 1.0, True)

    bad = failed = 0
    equity = 1.0
    for i in range(1, len(calls)):
        prev, cur = calls[i - 1], calls[i]
        start = prev.get('effective_since') or prev.get('logged')
        inception = data.get('log_inception')
        if inception and start < inception:
            start = inception
        end = cur.get('effective_since') or cur.get('logged')
        held = prev.get('allocation', {})
        claimed = cur.get('result_since_prior')
        basis = cur.get('result_basis', 'unstated')

        print('-' * 72)
        print('  Call #%s -> #%s   %s to %s' % (prev.get('n'), cur.get('n'), start, end))
        print('  Held: %s' % (', '.join('%s %s%%' % (k, v) for k, v in held.items()) or 'nothing'))

        try:
            mine, rows = perf.period_return(held, start, end, prices.price_on_or_after)
        except Exception as e:
            print('  !! could not verify: %s' % e); failed += 1; continue

        for r in rows:
            if r.get('start_price') is None:
                print('     %-5s %5.1f%%   (cash)' % (r['symbol'], r['weight']))
            else:
                print('     %-5s %5.1f%%   %.6g -> %.6g   %s'
                      % (r['symbol'], r['weight'], r['start_price'], r['end_price'], perf.fmt_pct(r['change'])))

        print('  Independently computed: %s' % perf.fmt_pct(mine))
        equity *= (1.0 + mine)
        print('  The log claims        : %s   (%s)' % (claimed or '—', basis))

        if basis == 'asserted':
            print('  NOTE: this figure was entered by hand, not measured. Treat it with more suspicion')
            print('        than the computed ones — the log flags it for exactly that reason.')
        if claimed:
            try:
                claimed_f = float(str(claimed).replace('%', '').replace('+', '')) / 100.0
                diff = abs(claimed_f - mine)
                if diff <= TOL:
                    print('  => MATCHES (within %.2fpp)' % (TOL * 100))
                else:
                    print('  => DISAGREES by %.2fpp  <-- the log does not reproduce' % (diff * 100)); bad += 1
            except ValueError:
                print('  => claim not machine-readable, skipped')

        try:
            d0, b0 = prices.price_on_or_after('BTC', start)
            d1, b1 = prices.price_on_or_after('BTC', end)
            print('  For comparison, simply holding Bitcoin over the same window: %s'
                  % perf.fmt_pct(b1 / b0 - 1.0))
        except Exception:
            pass

    rc_summary = check_summary(data, calls, equity, failed == 0)

    print('\n' + '=' * 72)
    if failed:
        print('  COULD NOT COMPLETE — %d period(s) unverifiable (data unavailable).' % failed)
        print('  That is not a pass. Re-run when the price sources are reachable.')
        return 2
    if bad:
        print('  %d CLAIM(S) DID NOT REPRODUCE. Treat this record with suspicion until explained.' % bad)
        return 1
    if rc_summary:
        print('  The LOG reproduces in full — every logged call checks out against public prices.')
        print('  The published SUMMARY does not. The record is sound; the table describing it')
        print('  is not, and both have to hold for this page to be honest.')
        return 1
    print('  ALL CLAIMS REPRODUCED from public price data.')
    print('  You did not have to trust anything above — you just checked it.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
