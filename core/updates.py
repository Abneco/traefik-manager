import time

import requests
from flask_babel import gettext

from core import env, i18n
from core import monitor as monitor_mod
from core import traefik as traefik_mod
from core.env import logger

UPDATE_INTERVAL = 86400
UPDATE_TIMEOUT  = 10
TRAEFIK_REPO    = 'traefik/traefik'
GITHUB_LATEST   = 'https://api.github.com/repos/{repo}/releases/latest'


def _strip_v(value) -> str:
    text = str(value or '').strip()
    return text[1:] if text[:1] in ('v', 'V') else text


def _version_parts(value) -> list:
    parts = []
    for chunk in _strip_v(value).split('.'):
        digits = ''
        for ch in chunk:
            if not ch.isdigit():
                break
            digits += ch
        parts.append(int(digits) if digits else 0)
    return parts


def compare_versions(a, b) -> int:
    pa, pb = _version_parts(a), _version_parts(b)
    for i in range(max(len(pa), len(pb))):
        diff = (pa[i] if i < len(pa) else 0) - (pb[i] if i < len(pb) else 0)
        if diff != 0:
            return diff
    return 0


def latest_release(repo: str) -> str:
    return release_info(repo).get('tag', '')


RELEASE_CACHE_TTL = 3600
RELEASE_RETRY_TTL = 300
_release_cache = {}


def _cached_release(repo, now):
    hit = _release_cache.get(repo)
    if not hit:
        return None
    stamp, info = hit[0], hit[1]
    ttl = hit[2] if len(hit) > 2 else RELEASE_CACHE_TTL
    return info if (now - stamp) < ttl else None


def release_info(repo: str) -> dict:
    now = time.time()
    fresh = _cached_release(repo, now)
    if fresh is not None:
        return fresh
    previous = (_release_cache.get(repo) or (0, {}))[1]
    info = {'tag': '', 'url': '', 'notes': '', 'error': ''}
    ttl = RELEASE_CACHE_TTL
    try:
        resp = requests.get(GITHUB_LATEST.format(repo=repo), timeout=UPDATE_TIMEOUT,
                            headers={'Accept': 'application/vnd.github.v3+json'})
        if resp.status_code == 200:
            data = resp.json() or {}
            info['tag'] = _strip_v(data.get('tag_name'))
            info['url'] = str(data.get('html_url') or '')
            info['notes'] = str(data.get('body') or '')
        elif resp.status_code in (403, 429):
            info['error'] = i18n.Message('rate limited by GitHub, retrying later',
                                         lambda: gettext('rate limited by GitHub, retrying later'))
        else:
            code = resp.status_code
            info['error'] = i18n.Message('GitHub returned HTTP %d' % code,
                                         lambda: gettext('GitHub returned HTTP %(status_code)d', status_code=code))
            ttl = RELEASE_RETRY_TTL
    except Exception as e:
        info['error'] = str(e)[:120]
        ttl = RELEASE_RETRY_TTL
        logger.debug(f"Release lookup for {repo} failed: {e}")
    if not info['tag'] and previous.get('tag'):
        kept = dict(previous)
        kept['error'] = info['error']
        info = kept
    _release_cache[repo] = (now, info, ttl)
    return info


def running_traefik_version() -> str:
    info = traefik_mod.traefik_api_get('/api/version')
    return _strip_v(info.get('Version')) if isinstance(info, dict) else ''


def _update_alert(key, product, current, latest, seen):
    if not latest or seen.get(key) == latest:
        return None
    if compare_versions(latest, current) <= 0:
        return None
    seen[key] = latest
    return ('info', f"{product} v{latest} is available - update now", 'update')


def _latest_cached(repo, cache) -> str:
    if repo not in cache:
        cache[repo] = latest_release(repo)
    return cache[repo]


def agent_traefik_version(agent) -> str:
    try:
        info = monitor_mod._agent_json(agent, '/api/traefik/version')
    except Exception as e:
        logger.debug(f"Traefik version check failed for agent {agent.get('name', '')}: {e}")
        return ''
    return _strip_v(info.get('Version')) if isinstance(info, dict) else ''


def check_updates(seen: dict = None) -> list:
    if seen is None:
        seen = monitor_mod._section('updates')
    cache  = {}
    raised = []
    for key, product, repo, current in (
            ('manager', 'Traefik Manager', env.GITHUB_REPO,   env.APP_VERSION),
            ('traefik', 'Traefik',         TRAEFIK_REPO,      running_traefik_version())):
        if not current:
            continue
        alert = _update_alert(key, product, current, _latest_cached(repo, cache), seen)
        if alert:
            raised.append(alert)
    for agent in monitor_mod._agents():
        agent_id = str(agent.get('id') or '')
        if not agent_id or not monitor_mod._agent_reachable(agent):
            continue
        current = agent_traefik_version(agent)
        if not current:
            continue
        name  = str(agent.get('name') or agent_id)
        alert = _update_alert(f"traefik:{agent_id}", f"Traefik on {name}", current,
                              _latest_cached(TRAEFIK_REPO, cache), seen)
        if alert:
            raised.append(alert)
    return raised
