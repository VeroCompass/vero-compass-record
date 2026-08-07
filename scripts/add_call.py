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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALLS = os.path.join(ROOT, 'calls.json')
LOG = os.path.join(ROOT, 'LOG.md')

# Every file read/write is explicitly UTF-8. Without this, Python on Windows defaults to cp1252, which
# (a) mangles the em-dashes already in calls.json — silently REWRITING past entries and breaking the
# append-only promise — and (b) writes invalid-UTF-8 bytes into LOG.md that GitHub renders as mojibake.
ENC = 'utf-8'


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
    ap.add_argument('--result', default='', help='result since prior entry, e.g. "+8.1%"')
    ap.add_argument('--effective-since', default='', help='date the indicator flipped, if not today')
    ap.add_argument('--no-push', action='store_true', help='commit but do not push')
    ap.add_argument('--dry-run', action='store_true', help='show what would be written; change nothing')
    args = ap.parse_args()

    preflight(args.dry_run)

    today = datetime.date.today().isoformat()
    with open(CALLS, encoding=ENC) as f:
        data = json.load(f)
    before = json.dumps(data['calls'], ensure_ascii=False, sort_keys=True)   # append-only snapshot

    n = (data['calls'][-1]['n'] + 1) if data['calls'] else 1
    alloc = parse_alloc(args.alloc)
    entry = {'n': n, 'state': args.state, 'allocation': alloc, 'logged': today,
             'reason': args.reason, 'result_since_prior': args.result or None}
    if args.effective_since:
        entry['effective_since'] = args.effective_since

    tracked = data.get('tracked_config', '')
    md = ['\n---\n', '\n### Entry #%d — %s\n' % (n, args.state.upper()),
          '- **Logged:** %s\n' % today,
          '- **State:** %s\n' % ('RISK-OFF — **100% CASH**' if args.state == 'risk-off' else 'RISK-ON'),
          '- **Allocation:** `%s`\n' % alloc_str(alloc)]
    if args.effective_since:
        md.append('- **In effect since:** %s\n' % args.effective_since)
    if args.reason:
        md.append('- **Why:** %s\n' % args.reason)
    md.append('- **Result since prior entry:** %s\n' % (args.result or '—'))
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

    run(['git', 'add', 'calls.json', 'LOG.md'], check=True)
    run(['git', 'commit', '-m', 'call #%d: %s — %s' % (n, args.state, alloc_str(alloc))], check=True)
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
