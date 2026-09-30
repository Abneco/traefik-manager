import ipaddress
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import requests

from core import i18n as _i18n

POOL_WORKERS = 6
UNREACHABLE = (502, 503, 504)
REDIRECTS   = (301, 302, 303, 307, 308)
TIMEOUT     = 5

_DOWN_MARKERS    = ('connection refused', 'no route to host', 'network is unreachable',
                    'connection reset', 'remote end closed')
_DOWN_WHY        = (('connection refused', 'refused'),
                    ('no route to host', 'no_route'),
                    ('network is unreachable', 'network'),
                    ('connection reset', 'reset'),
                    ('remote end closed', 'closed'))
_UNKNOWN_MARKERS = ('name or service not known', 'nodename nor servname', 'temporary failure in name resolution',
                    'nameresolutionerror', 'getaddrinfo failed', 'timed out', 'timeout')


MAX_REDIRECT_HOPS = 5


class BlockedTarget(Exception):
    pass


def ssrf_ok(url: str) -> bool:
    try:
        host = urlparse(url).hostname
        if not host:
            return False
        for res in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(res[4][0])
            if ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                return False
        return True
    except Exception:
        return False


def safe_get(url: str, *, ssrf=None, getter=None, **kwargs):
    ssrf = ssrf or ssrf_ok
    getter = getter or requests.get
    kwargs['allow_redirects'] = False
    target = url
    for _ in range(MAX_REDIRECT_HOPS + 1):
        if not _is_http(target):
            raise BlockedTarget(_i18n.lazy_gettext('%(url)s is not an http(s) address', url=target))
        if not ssrf(target):
            raise BlockedTarget(_i18n.lazy_gettext('%(url)s is not an allowed address', url=target))
        resp = getter(target, **kwargs)
        location = ''
        try:
            location = resp.headers.get('Location', '') or ''
        except Exception:
            pass
        if resp.status_code not in REDIRECTS or not location:
            return resp
        target = urljoin(target, location)
    raise BlockedTarget(_i18n.lazy_ngettext('%(url)s redirected more than %(num)d time',
                                            '%(url)s redirected more than %(num)d times',
                                            MAX_REDIRECT_HOPS, url=url))


def _is_http(url: str) -> bool:
    return str(url or '').startswith(('http://', 'https://'))


def _head(target, head):
    t0   = time.monotonic()
    resp = head(target, timeout=TIMEOUT, allow_redirects=False, verify=False)
    ms   = round((time.monotonic() - t0) * 1000)
    location = ''
    try:
        location = resp.headers.get('Location', '') or ''
    except Exception:
        pass
    return ms, resp.status_code, location


def _error_text(exc) -> str:
    err = str(exc)[:80]
    return _i18n.lazy_gettext('Timeout') if 'timeout' in err.lower() else err


def redirect_target_host(url: str, code: int, location: str) -> str:
    if code not in REDIRECTS or not location:
        return ''
    try:
        to   = (urlparse(urljoin(url, location)).hostname or '').lower()
        here = (urlparse(url).hostname or '').lower()
    except Exception:
        return ''
    return to if to and to != here else ''


def _classify_failure(exc) -> str:
    text = str(exc).lower()
    if isinstance(exc, (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout)):
        return 'unknown'
    if any(m in text for m in _DOWN_MARKERS):
        return 'down'
    if any(m in text for m in _UNKNOWN_MARKERS):
        return 'unknown'
    return 'down' if isinstance(exc, requests.exceptions.ConnectionError) else 'unknown'


def _down_why(exc) -> str:
    text = str(exc).lower()
    return next((why for marker, why in _DOWN_WHY if marker in text), 'unreachable')


def redirect_reason(host: str, why) -> str:
    kind, detail = why if isinstance(why, tuple) else (why, '')
    if kind == 'refused':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend refused the connection', host=host)
    if kind == 'no_route':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend is unreachable (no route to host)', host=host)
    if kind == 'network':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend is unreachable (network unreachable)', host=host)
    if kind == 'reset':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend reset the connection', host=host)
    if kind == 'closed':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend closed the connection without answering', host=host)
    if kind == 'no_address':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend has no address to check', host=host)
    if kind == 'error':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend could not be reached from Traefik Manager (%(error)s)',
                                  host=host, error=detail)
    if kind == 'answered':
        return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                                  'and the backend answered %(code)s', host=host, code=detail)
    return _i18n.lazy_gettext('The proxy redirected to %(host)s before reaching the backend, '
                              'and the backend is unreachable', host=host)


def _backend(fallback, ssrf, head):
    if not (fallback and _is_http(fallback) and ssrf(fallback)):
        return 'unknown', None, ('no_address', '')
    try:
        ms, code, _loc = _head(fallback, head)
    except Exception as exc:
        verdict = _classify_failure(exc)
        why = (_down_why(exc), '') if verdict == 'down' else ('error', _error_text(exc))
        return verdict, None, why
    if code in UNREACHABLE:
        return 'down', None, ('answered', code)
    return 'up', {'ok': True, 'latency_ms': ms, 'status_code': code, 'via_target': True}, ('', '')


def backend_state(url: str, ssrf=None, head=None) -> str:
    verdict, _alt, _why = _backend(url, ssrf or ssrf_ok, head or requests.head)
    return verdict


def pool_health(urls, ssrf=None, head=None):
    clean = [str(u) for u in (urls or []) if str(u).startswith(('http://', 'https://'))]
    if len(clean) < 2:
        return None
    probe = backend_state if (ssrf is None and head is None) else (lambda u: backend_state(u, ssrf, head))
    with ThreadPoolExecutor(max_workers=min(POOL_WORKERS, len(clean))) as pool:
        verdicts = list(pool.map(probe, clean))
    if 'unknown' in verdicts:
        return None
    return {'up': verdicts.count('up'), 'total': len(clean),
            'down_servers': [u for u, v in zip(clean, verdicts) if v != 'up']}


def pool_result(pool: dict) -> dict:
    state = 'down' if pool['up'] == 0 else ('degraded' if pool['up'] < pool['total'] else 'up')
    out = {'ok': pool['up'] > 0, 'state': state, 'source': 'servers',
           'servers': {'up': pool['up'], 'total': pool['total']}}
    if pool['down_servers']:
        out['down_servers'] = pool['down_servers']
    return out


def probe(url: str, fallback: str = '', ssrf=None, head=None, verify_backend: bool = True) -> dict:
    ssrf = ssrf or ssrf_ok
    head = head or requests.head

    try:
        ms, code, location = _head(url, head)
    except Exception as primary_err:
        verdict, alt, _why = _backend(fallback, ssrf, head)
        if alt:
            return alt
        return {'ok': False, 'error': _error_text(primary_err), 'latency_ms': None}

    if code in UNREACHABLE:
        verdict, alt, _why = _backend(fallback, ssrf, head)
        if alt:
            return alt
        return {'ok': False, 'latency_ms': ms, 'status_code': code,
                'error': _i18n.lazy_gettext('The proxy answered %(code)s, the backend is not reachable', code=code)}

    auth_host = redirect_target_host(url, code, location) if verify_backend else ''
    if auth_host:
        verdict, alt, why = _backend(fallback, ssrf, head)
        if alt:
            return alt
        if verdict == 'down':
            return {'ok': False, 'latency_ms': ms, 'status_code': code,
                    'error': redirect_reason(auth_host, why)}
        return {'ok': True, 'latency_ms': ms, 'status_code': code, 'unverified': True,
                'note': redirect_reason(auth_host, why)}

    return {'ok': True, 'latency_ms': ms, 'status_code': code}
