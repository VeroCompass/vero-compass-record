#!/usr/bin/env python3
"""
Vero Compass — append a new allocation call to the public record and publish it, in real time.

Appends to calls.json + LOG.md, then commits and pushes (GitHub stamps the server-side push time — that
timestamp is the credibility). Append-only: this script never edits or removes a past entry.

USAGE (run from the repo root):
  # risk-off (system to cash):
  python scripts/add_call.py --state risk-off --alloc cash --reason "BTC below 120d trend filter"

  # risk-on (holding coins; weights are the rounded 5% allocations):
  python scripts/add_call.py --state risk-on --alloc "BTC:30,ETH:25,SOL:20,LINK:15,GOLD:10" \
      --reason "Trend up; top-4 by momentum + gold hedge" --result "+8.1% since prior entry"

REAL-TIME / AUTOMATED: wire this to the TradingView alert for the tracked indicator so the push happens at
the moment of the call (e.g. alert -> webhook -> a tiny handler on a box you own -> runs this script), so
the commit time is machine-set, not hand-typed. Also send the same entry to your email list here (see the
EMAIL hook at the bottom).
"""
import argparse, json, os, subprocess, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALLS = os.path.join(ROOT, 'calls.json')
LOG = os.path.join(ROOT, 'LOG.md')

def parse_alloc(s):
    if s.strip().lower() in ('cash', '100% cash', 'cash100'):
        return {'CASH': 100}
    out = {}
    for part in s.split(','):
        k, v = part.split(':'); out[k.strip().upper()] = round(float(v))
    tot = sum(out.values())
    if abs(tot - 100) > 0:
        print('WARNING: allocation sums to %d%%, not 100%%.' % tot, file=sys.stderr)
    return out

def alloc_str(a):
    if list(a.keys()) == ['CASH']:
        return '100% cash'
    return ' · '.join('%s %d%%' % (k, v) for k, v in a.items())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state', required=True, choices=['risk-on', 'risk-off'])
    ap.add_argument('--alloc', required=True, help='"cash" or "BTC:30,ETH:25,..."')
    ap.add_argument('--reason', default='')
    ap.add_argument('--result', default='', help='result since prior entry, e.g. "+8.1%"')
    ap.add_argument('--no-push', action='store_true', help='commit but do not push')
    args = ap.parse_args()

    # Date.now equivalent — real wall clock at the moment of the call.
    today = datetime.date.today().isoformat()
    with open(CALLS) as f:
        data = json.load(f)
    n = (data['calls'][-1]['n'] + 1) if data['calls'] else 1
    entry = {'n': n, 'state': args.state, 'allocation': parse_alloc(args.alloc), 'logged': today,
             'reason': args.reason, 'result_since_prior': args.result or None}
    data['calls'].append(entry)
    with open(CALLS, 'w') as f:
        json.dump(data, f, indent=2); f.write('\n')

    with open(LOG, 'a') as f:
        f.write('\n---\n\n### Entry #%d — %s\n' % (n, args.state.upper()))
        f.write('- **Logged:** %s\n' % today)
        f.write('- **State:** %s\n' % ('RISK-OFF — 100%% CASH' if args.state == 'risk-off' else 'RISK-ON'))
        f.write('- **Allocation:** `%s`\n' % alloc_str(entry['allocation']))
        if args.reason: f.write('- **Why:** %s\n' % args.reason)
        f.write('- **Result since prior entry:** %s\n' % (args.result or '—'))

    subprocess.run(['git', '-C', ROOT, 'add', 'calls.json', 'LOG.md'], check=True)
    subprocess.run(['git', '-C', ROOT, 'commit', '-m', 'call #%d: %s — %s' % (n, args.state, alloc_str(entry['allocation']))], check=True)
    if not args.no_push:
        subprocess.run(['git', '-C', ROOT, 'push'], check=True)
    # EMAIL hook: send `entry` to your list service here (Buttondown/ConvertKit/Mailgun API call).
    print('Logged call #%d and %s.' % (n, 'pushed' if not args.no_push else 'committed (not pushed)'))

if __name__ == '__main__':
    main()
