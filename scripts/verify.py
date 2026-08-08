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
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices, perf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOL = 0.0015           # 0.15pp — allows for rounding and small feed differences between exchanges


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
        return 0

    bad = failed = 0
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

    print('\n' + '=' * 72)
    if failed:
        print('  COULD NOT COMPLETE — %d period(s) unverifiable (data unavailable).' % failed)
        print('  That is not a pass. Re-run when the price sources are reachable.')
        return 2
    if bad:
        print('  %d CLAIM(S) DID NOT REPRODUCE. Treat this record with suspicion until explained.' % bad)
        return 1
    print('  ALL CLAIMS REPRODUCED from public price data.')
    print('  You did not have to trust anything above — you just checked it.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
