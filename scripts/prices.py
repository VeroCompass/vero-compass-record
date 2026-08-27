#!/usr/bin/env python3
"""
Public price data for the Vero Compass record — standard library only, no API keys, no accounts.

Deliberately dependency-free so that ANYONE can run the verification script on a plain Python install and
check the numbers in this log for themselves. Crypto comes from Binance's public endpoint; gold comes from
Yahoo's public chart endpoint. Both are free and keyless.

Prices used are DAILY OPENS, because the system acts at the next open after a signal — so the opens are
the prices a follower could actually have traded at.
"""
import json, urllib.request, urllib.error, datetime

# Binance's public klines, tried in order. The first is the canonical host; the second is Binance's own
# public data mirror. api.binance.com answers 451 to a number of cloud/CI address ranges, so a scheduled
# refresh running in a datacentre needs the second door. Same exchange, same candles — this changes where
# the data is fetched from, never what is being measured.
BINANCE_HOSTS = ('https://api.binance.com', 'https://data-api.binance.vision')
KLINES_PATH = '/api/v3/klines?symbol=%sUSDT&interval=1d&startTime=%d&endTime=%d&limit=1000'
YAHOO = 'https://query1.finance.yahoo.com/v8/finance/chart/%s?period1=%d&period2=%d&interval=1d'
GOLD_TICKER = 'GC=F'          # gold futures — the public stand-in for the indicator's spot gold feed
UA = {'User-Agent': 'Mozilla/5.0 (vero-compass-verify)'}


class PriceError(Exception):
    """Raised when a price genuinely could not be obtained. Never swallowed — a missing price must stop
    the calculation, not quietly produce a wrong number."""


def _ts(d):
    return int(datetime.datetime.strptime(d, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc).timestamp())


_CACHE = {}


def _fetch(url):
    # Cached for the life of the process only. Building the summary asks for overlapping windows many
    # times over; re-downloading them would be slow and rude to a free public endpoint. Nothing is cached
    # to disk, so a fresh run always re-checks the real source.
    if url in _CACHE:
        return _CACHE[url]
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read().decode('utf-8', 'replace'))
    _CACHE[url] = j
    return j


def _klines(symbol, lo, hi):
    """Daily klines for `symbol`, falling through to the mirror if the first host refuses us.

    Only a geo-block or a refusal is retried elsewhere. Any other failure is a real one and is raised, so
    a genuine outage can never be quietly papered over by trying another host and getting nothing.
    """
    last = None
    for host in BINANCE_HOSTS:
        try:
            return _fetch(host + KLINES_PATH % (symbol.upper(), lo, hi))
        except urllib.error.HTTPError as e:
            if e.code not in (403, 451):      # 451 = blocked for legal/region reasons, 403 = refused
                raise
            last = 'HTTP %s from %s' % (e.code, host)
        except urllib.error.URLError as e:
            last = '%s from %s' % (e.reason, host)
    raise PriceError('no Binance host would serve %s (last: %s)' % (symbol, last))


def daily_opens(symbol, start, end):
    """{'YYYY-MM-DD': open_price} for symbol, inclusive of start, through end."""
    lo, hi = _ts(start) * 1000, (_ts(end) + 86400) * 1000
    out = {}
    if symbol.upper() == 'GOLD':
        j = _fetch(YAHOO % (GOLD_TICKER, _ts(start) - 86400 * 5, _ts(end) + 86400))
        res = (j.get('chart') or {}).get('result')
        if not res:
            raise PriceError('no gold data returned for %s..%s' % (start, end))
        ts = res[0].get('timestamp') or []
        op = (res[0]['indicators']['quote'][0] or {}).get('open') or []
        for i, t in enumerate(ts):
            v = op[i] if i < len(op) else None
            if v:
                out[datetime.datetime.utcfromtimestamp(t).strftime('%Y-%m-%d')] = float(v)
    else:
        j = _klines(symbol, lo, hi)
        if not isinstance(j, list):
            raise PriceError('unexpected response for %s (symbol delisted or renamed?)' % symbol)
        for k in j:
            out[datetime.datetime.utcfromtimestamp(k[0] / 1000).strftime('%Y-%m-%d')] = float(k[1])
    if not out:
        raise PriceError('no prices for %s between %s and %s' % (symbol, start, end))
    return out


def today_utc():
    """Market data is timestamped in UTC. Using a local date (e.g. Bangkok, UTC+7) asks for a candle that
    does not exist yet for most of the day."""
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')


def price_on_or_after(symbol, date, window=10, back=5):
    """
    The daily open to use for `date`.

    Prefers the first session on/after the date — crypto trades daily but gold does not (weekends,
    holidays), so we step forward to the next session rather than inventing a price. If no session exists
    on/after it yet (asking for today before the UTC candle has formed, or a market that is closed), we
    fall back to the most recent session within `back` days and RETURN THAT DATE, so the caller records
    the price actually used. Beyond that window we raise, rather than quietly mispricing a period.
    """
    d0 = datetime.datetime.strptime(date, '%Y-%m-%d')
    start = (d0 - datetime.timedelta(days=back)).strftime('%Y-%m-%d')
    end = (d0 + datetime.timedelta(days=window)).strftime('%Y-%m-%d')
    px = daily_opens(symbol, start, end)
    fwd = sorted(d for d in px if d >= date)
    if fwd:
        return fwd[0], px[fwd[0]]
    prior = sorted(d for d in px if d < date)
    if prior:
        return prior[-1], px[prior[-1]]
    raise PriceError('no %s price near %s' % (symbol, date))
