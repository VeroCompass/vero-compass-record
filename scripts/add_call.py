#!/usr/bin/env python3
"""
Vero Compass — append a new allocation call to the public record and publish it, in real time.

Appends to calls.json + LOG.md, then commits and pushes (GitHub stamps the server-side push time — that
timestamp is the credibility). Append-only: this script never edits or removes a past entry, and it
VERIFIES that it hasn't before it commits.

USAGE (run from the repo root):
  # dry run first if you like — writes nothing, shows exactly what would be logged:
  python scripts/add_call.py --state risk-on --alloc "BTC:30,ETH:25,SOL:20,LINK:15,GOLD:10" --dry-run

  # risk-off (system to cash):
  python scripts/add_call.py --state risk-off --alloc cash --reason "BTC below its 120-day trend filter"

  # risk-on (holding coins; weights are the rounded 5% allocations):
  python scripts/add_call.py --state risk-on --alloc "BTC:30,ETH:25,SOL:20,LINK:15,GOLD:10" \
      --reason "Trend up; strongest trending coins by momentum + gold hedge" --result "+8.1% since prior entry"

Optional: --effective-since YYYY-MM-DD  (the date the indicator actually flipped, if you log a day later)

REAL-TIME / AUTOMATED: wire this to the TradingView alert for the tracked indicator so the push happens at
the moment of the call. Also send the same entry to your email list (see the EMAIL hook at the bottom).
"""
import argparse, json, os, subprocess, sys, datetime

# Windows consoles default to cp1252, which cannot encode the em-dashes and arrows this script prints.
# The FILE writes are already explicitly UTF-8; this fixes the same failure on stdout/stderr, which
# otherwise crashes a --dry-run (and would hide any message printed after the failure point).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, 'reconfigure'):
        _s.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices, perf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALLS = os.path.join(ROOT, 'calls.json')
LOG = os.path.join(ROOT, 'LOG.md')

# Every file read/write is explicitly UTF-8. Without this, Python on Windows defaults to cp1252, which
# (a) mangles the em-dashes already in calls.json — silently REWRITING past entries and breaking the
# append-only promise — and (b) writes invalid-UTF-8 bytes into LOG.md that GitHub renders as mojibake.
ENC = 'utf-8'

# The public record is the BRAND's, never an individual's. Forcing the identity on the commit itself means
# it cannot depend on whatever git config happens to exist on the machine — which would either fail
# ("Author identity unknown" on a fresh clone) or, worse, silently stamp a personal email onto a public
# brand commit.
AUTHOR_NAME = 'Vero Compass'
AUTHOR_EMAIL = 'vero-compass@users.noreply.github.com'
IDENT = ['-c', 'user.name=' + AUTHOR_NAME, '-c', 'user.email=' + AUTHOR_EMAIL]


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, **kw)


def die(msg):
    print('\n*** ABORTED: %s\n' % msg, file=sys.stderr)
    sys.exit(1)


def parse_alloc(s):
    if s.strip().lower() in ('cash', '100% cash', 'cash100'):
        return {'CASH': 100}
    out = {}
    for part in s.split(','):
        if ':' not in part:
            die('bad --alloc segment %r. Expected "COIN:weight" or "cash".' % part)
        k, v = part.split(':', 1)
        out[k.strip().upper()] = int(round(float(v)))
    tot = sum(out.values())
    if tot != 100:
        die('allocation sums to %d%%, not 100%%. Fix the weights and re-run — refusing to log a '
            'book that does not add up.' % tot)
    off = [k for k, v in out.items() if v % 5 != 0]
    if off:
        print('NOTE: these weights are not multiples of 5%%: %s (the product rounds to 5%% steps).'
              % ', '.join(off), file=sys.stderr)
    return out


def alloc_str(a):
    if list(a.keys()) == ['CASH']:
        return '100% cash'
    return ' · '.join('%s %d%%' % (k, v) for k, v in a.items())


def preflight(dry):
    if not os.path.isdir(os.path.join(ROOT, '.git')):
        die('not a git repo: %s' % ROOT)
    branch = run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                 capture_output=True, text=True).stdout.strip()
    if branch != 'main':
        die('on branch %r, not main. The public record lives on main.' % branch)
    dirty = run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout.strip()
    if dirty:
        die('working tree is not clean:\n%s\nCommit or stash first so this call is the only change.' % dirty)
    if not dry:
        run(['git', 'fetch', '--quiet', 'origin', 'main'])
        behind = run(['git', 'rev-list', '--count', 'HEAD..origin/main'],
                     capture_output=True, text=True).stdout.strip()
        if behind not in ('', '0'):
            die('local main is %s commit(s) behind origin/main. Run "git pull" first, '
                'then re-run — otherwise the push will be rejected.' % behind)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state', required=True, choices=['risk-on', 'risk-off'])
    ap.add_argument('--alloc', required=True, help='"cash" or "BTC:30,ETH:25,..."')
    ap.add_argument('--reason', default='')
    ap.add_argument('--result', default='', help='OVERRIDE the computed result. Using this marks the '
                    'entry as manually asserted rather than measured — avoid unless the computation is wrong.')
    ap.add_argument('--effective-since', default='', help='date the indicator flipped, if not today')
    ap.add_argument('--no-push', action='store_true', help='commit but do not push')
    ap.add_argument('--dry-run', action='store_true', help='show what would be written; change nothing')
    args = ap.parse_args()

    preflight(args.dry_run)

    # UTC, not local time. Market data is stamped in UTC, and a public record should not be ambiguous
    # about which day a call belongs to depending on where the person logging it happens to be sitting.
    today = prices.today_utc()
    with open(CALLS, encoding=ENC) as f:
        data = json.load(f)
    before = json.dumps(data['calls'], ensure_ascii=False, sort_keys=True)   # append-only snapshot

    n = (data['calls'][-1]['n'] + 1) if data['calls'] else 1
    alloc = parse_alloc(args.alloc)
    this_date = args.effective_since or today

    # --- the result is MEASURED from real prices, not typed in ---
    # Whatever the previous call put us into, priced from the day it took effect to the day this call
    # replaces it. If it cannot be priced, we stop — a period that cannot be measured must never quietly
    # become "0%".
    result_txt, basis, detail = None, None, None
    if data['calls']:
        prev = data['calls'][-1]
        inception = data.get('log_inception')
        start = prev.get('effective_since') or prev.get('logged')
        if inception and start < inception:
            start = inception          # we do not claim live performance from before the record existed
        if args.result:
            result_txt, basis = args.result, 'asserted'
            print('NOTE: --result given, so this entry is marked ASSERTED, not measured.', file=sys.stderr)
        else:
            try:
                r, detail = perf.period_return(prev.get('allocation', {}), start, this_date,
                                               prices.price_on_or_after)
                result_txt, basis = perf.fmt_pct(r), 'computed'
                print('Computed result for the period %s -> %s: %s' % (start, this_date, result_txt))
            except prices.PriceError as e:
                die('could not price the previous allocation (%s).\nNothing was written. Retry when the '
                    'data source is reachable, or pass --result "<x%%>" to record it as an ASSERTED '
                    'figure — which the log will label as such.' % e)
            except ValueError as e:
                die('%s' % e)

    entry = {'n': n, 'state': args.state, 'allocation': alloc, 'logged': today,
             'reason': args.reason, 'result_since_prior': result_txt}
    if basis:
        entry['result_basis'] = basis
        if basis == 'computed':
            entry['result_period'] = {'from': start, 'to': this_date,
                                      'allocation_held': prev.get('allocation', {}),
                                      'method': 'daily opens, net of 0.1%/side fee + per-coin spread',
                                      'detail': detail}
    if args.effective_since:
        entry['effective_since'] = args.effective_since

    tracked = data.get('tracked_config', '')
    # The state line must never contradict the allocation line directly beneath it. Risk-off does NOT
    # imply cash: the gold hedge is exempt from the crash filter, so the book can be risk-off and still
    # fully invested in gold. Hardcoding "100% CASH" here would publish a self-contradicting entry.
    if args.state == 'risk-off':
        st_txt = 'RISK-OFF — **100% CASH**' if list(alloc.keys()) == ['CASH'] \
                 else 'RISK-OFF — **no crypto qualifies; held in the hedge**'
    else:
        st_txt = 'RISK-ON'
    md = ['\n---\n', '\n### Entry #%d — %s\n' % (n, args.state.upper()),
          '- **Logged:** %s\n' % today,
          '- **State:** %s\n' % st_txt,
          '- **Allocation:** `%s`\n' % alloc_str(alloc)]
    if args.effective_since:
        md.append('- **In effect since:** %s\n' % args.effective_since)
    if args.reason:
        md.append('- **Why:** %s\n' % args.reason)
    if basis == 'computed':
        md.append('- **Result since prior entry:** %s  *(computed from daily opens %s → %s, net of fees '
                  'and spread — recompute it yourself with `scripts/verify.py`)*\n'
                  % (result_txt, start, this_date))
    elif basis == 'asserted':
        md.append('- **Result since prior entry:** %s  ⚠️ *(MANUALLY ENTERED, not computed from prices)*\n'
                  % result_txt)
    else:
        md.append('- **Result since prior entry:** — *(first entry)*\n')
    if tracked:
        md.append('- **Tracked config:** %s\n' % tracked)
    md_text = ''.join(md)

    if args.dry_run:
        print('--- DRY RUN, nothing written ---')
        print('calls.json entry:\n' + json.dumps(entry, indent=2, ensure_ascii=False))
        print('\nLOG.md entry:' + md_text)
        print('commit message: call #%d: %s — %s' % (n, args.state, alloc_str(alloc)))
        return

    data['calls'].append(entry)
    with open(CALLS, 'w', encoding=ENC) as f:
        json.dump(data, f, indent=2, ensure_ascii=False); f.write('\n')
    with open(LOG, 'a', encoding=ENC) as f:
        f.write(md_text)

    # APPEND-ONLY GUARD: re-read and prove every prior entry is byte-identical to what it was.
    with open(CALLS, encoding=ENC) as f:
        after = json.load(f)
    if json.dumps(after['calls'][:-1], ensure_ascii=False, sort_keys=True) != before:
        run(['git', 'checkout', '--', 'calls.json', 'LOG.md'])
        die('APPEND-ONLY VIOLATION: writing this call would have altered an earlier entry. '
            'Files restored, nothing committed. This is a bug — do not log by hand, fix the script.')
    for p in (CALLS, LOG):
        with open(p, 'rb') as f:
            try:
                f.read().decode('utf-8')
            except UnicodeDecodeError as e:
                run(['git', 'checkout', '--', 'calls.json', 'LOG.md'])
                die('%s is not valid UTF-8 after write (%s). Files restored, nothing committed.'
                    % (os.path.basename(p), e))

    # Regenerate the public performance summary so it can never drift from the log it describes.
    # A failure here must not lose the call — the entry is already written and correct.
    try:
        import build_summary
        s, _ = build_summary.build()
        with open(os.path.join(ROOT, 'summary.json'), 'w', encoding=ENC) as f:
            json.dump(s, f, indent=2, ensure_ascii=False); f.write('\n')
        print('Regenerated summary.json.')
    except Exception as e:
        print('WARNING: could not regenerate summary.json (%s). The call is still being logged; '
              'run "python scripts/build_summary.py" once the data source is back.' % e, file=sys.stderr)

    run(['git', 'add', 'calls.json', 'LOG.md', 'summary.json'], check=True)
    c = run(['git'] + IDENT + ['commit', '-m', 'call #%d: %s — %s' % (n, args.state, alloc_str(alloc))])
    if c.returncode != 0:
        die('commit failed (git exit %d). Nothing was published; the edited files are still in the '
            'working tree. Inspect with "git status" before re-running.' % c.returncode)
    if args.no_push:
        print('Logged call #%d and committed locally. NOT PUSHED — run "git push" to publish.' % n)
        return
    r = run(['git', 'push'])
    if r.returncode != 0:
        die('COMMIT SUCCEEDED BUT PUSH FAILED (git exit %d). The call is committed locally but is NOT '
            'public yet. Fix connectivity/auth and run "git push" — do NOT re-run this script, that '
            'would log the call twice.' % r.returncode)
    print('Logged call #%d and pushed. It is public now.' % n)
    # EMAIL hook: send `entry` to your list service here (Buttondown/ConvertKit/Mailgun API call).


if __name__ == '__main__':
    main()
