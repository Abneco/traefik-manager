import json
import os
import threading
import time
from collections import deque
from contextlib import contextmanager

import requests
from ruamel.yaml import YAML as SafeYAML

from core import env
from core import i18n as _i18n
from core import settings as settings_mod
from core import notify_providers as providers
from core.env import logger

try:
    import fcntl
except ImportError:
    fcntl = None

MAX_ENTRIES = 200

_notifications = deque(maxlen=MAX_ENTRIES)
_notif_lock    = threading.Lock()


def _lock_path():
    return env.NOTIFICATIONS_PATH + '.lock'


@contextmanager
def _file_lock():
    fh = None
    if fcntl is not None:
        try:
            fh = open(_lock_path(), 'a+')
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except Exception:
            if fh is not None:
                try:
                    fh.close()
                except Exception:
                    pass
            fh = None
    try:
        yield
    finally:
        if fh is not None:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                fh.close()
            except Exception:
                pass


def _epoch_of(ts):
    try:
        return int(time.mktime(time.strptime(str(ts), "%Y-%m-%d %H:%M:%S")))
    except Exception:
        return 0


def _backfill(entries):
    nxt = max((e['id'] for e in entries
               if isinstance(e.get('id'), int) and e['id'] > 0), default=0) + 1
    for e in entries:
        if not isinstance(e.get('id'), int) or e['id'] <= 0:
            e['id'] = nxt
            nxt += 1
        if not isinstance(e.get('at'), int):
            e['at'] = _epoch_of(e.get('ts'))
    return entries


def _counter_path():
    return env.NOTIFICATIONS_PATH + '.next_id'


def _read_counter():
    try:
        with open(_counter_path(), 'r') as f:
            return int((f.read() or '0').strip())
    except Exception:
        return 0


def _write_counter(next_id):
    path = _counter_path()
    tmp  = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, 'w') as f:
            f.write(str(int(next_id)))
        os.replace(tmp, path)
    except Exception:
        try:
            with open(path, 'w') as f:
                f.write(str(int(next_id)))
        except Exception:
            logger.exception("Failed to persist the notification id counter")
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


def _read_state():
    try:
        with open(env.NOTIFICATIONS_PATH, 'r') as f:
            data = SafeYAML(typ='safe').load(f)
    except Exception:
        data = []
    if isinstance(data, dict):
        raw = data.get('items') or []
    else:
        raw = data or []
    entries = _backfill([e for e in raw if isinstance(e, dict)])
    highest = max((e['id'] for e in entries), default=0) + 1
    return entries, max(_read_counter(), highest)


def _read_file():
    return _read_state()[0]


def _write_file(entries, next_id=None):
    from core.config import _replace_or_copy
    if next_id is None:
        next_id = max(_read_counter(),
                      max((e.get('id', 0) for e in entries), default=0) + 1)
    _write_counter(next_id)
    path = env.NOTIFICATIONS_PATH
    tmp  = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, 'w') as f:
            SafeYAML(typ='safe').dump(list(entries), f)
        _replace_or_copy(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


def _sync(entries):
    _notifications.clear()
    for e in entries[-MAX_ENTRIES:]:
        _notifications.append(e)


def _send_webhook(url: str, wtype: str, type_: str, msg: str, ts: str, username: str = '', password: str = ''):
    color_map = {'warning': 0xf0a500, 'error': 0xf85149, 'info': 0x58a6ff, 'success': 0x3fb950}
    color = color_map.get(type_, 0x58a6ff)
    tag_map = {'warning': 'warning', 'error': 'rotating_light', 'success': 'white_check_mark', 'info': 'information_source'}
    auth = (username, password) if username else None
    if wtype == 'discord':
        payload = {'embeds': [{'title': msg, 'color': color, 'footer': {'text': f'Traefik Manager - {ts}'}}]}
        requests.post(url, json=payload, timeout=5, auth=auth)
    elif wtype == 'slack':
        icon = {'warning': ':warning:', 'error': ':x:', 'success': ':white_check_mark:', 'info': ':information_source:'}.get(type_, ':bell:')
        requests.post(url, json={'text': f'{icon} *Traefik Manager* - {msg}'}, timeout=5, auth=auth)
    elif wtype == 'ntfy':
        headers = {
            'X-Title': 'Traefik Manager',
            'X-Priority': '4' if type_ in ('warning', 'error') else '3',
            'X-Tags': tag_map.get(type_, 'bell'),
        }
        requests.post(url, data=msg.encode('utf-8'), headers=headers, timeout=5, auth=auth)
    else:
        requests.post(url, json={'event': type_, 'message': msg, 'timestamp': ts}, timeout=5, auth=auth)

QUEUE_MAX = 500

CATEGORY_LABELS = {
    'config': 'Config', 'backup': 'Backups', 'security': 'Security',
    'traefik': 'Traefik', 'certs': 'Certificates', 'crowdsec': 'CrowdSec',
    'agent': 'Agents', 'update': 'Updates',
}

CATEGORY_SPECS = {
    'config': _i18n.lazy_pgettext('notification category', 'Config'),
    'backup': _i18n.lazy_pgettext('notification category', 'Backups'),
    'security': _i18n.lazy_pgettext('notification category', 'Security'),
    'traefik': _i18n.lazy_pgettext('notification category', 'Traefik'),
    'certs': _i18n.lazy_pgettext('notification category', 'Certificates'),
    'crowdsec': _i18n.lazy_pgettext('notification category', 'CrowdSec'),
    'agent': _i18n.lazy_pgettext('notification category', 'Agents'),
    'update': _i18n.lazy_pgettext('notification category', 'Updates'),
}


def outgoing_translations():
    try:
        tag = settings_mod.load_settings().get('default_language', '')
    except Exception:
        tag = ''
    try:
        return _i18n.translations_for(tag)
    except Exception:
        return _i18n.translations_for('')


def _category_label(category, translations):
    spec = CATEGORY_SPECS.get(category)
    if spec is None:
        return CATEGORY_LABELS.get(category, '') or str(category or '').title()
    return _i18n.render(spec.spec, translations)


def _queue_path():
    return os.path.join(os.path.dirname(env.NOTIFICATIONS_PATH), 'notification_queue.json')


def _queue_read():
    try:
        with open(_queue_path(), 'r') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _queue_write(data):
    path = _queue_path()
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, 'w') as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except Exception:
        logger.exception("Failed to write the notification queue")
        try:
            os.unlink(tmp)
        except Exception:
            pass


def queue_add(channel_id, type_, msg, ts, category):
    if not channel_id:
        return
    with _notif_lock, _file_lock():
        q = _queue_read()
        held = q.setdefault(channel_id, {'items': [], 'dropped': 0, 'started': time.time()})
        held.setdefault('started', time.time())
        if len(held['items']) >= QUEUE_MAX:
            held['dropped'] = held.get('dropped', 0) + 1
        else:
            held['items'].append({'type': type_, 'msg': msg, 'ts': ts,
                                  'category': category, 'at': time.time()})
        _queue_write(q)


def build_report(items, dropped=0, translations=None) -> str:
    if not items:
        return ''
    tr = translations if translations is not None else _i18n.translations_for('')
    order = [c for c in CATEGORY_LABELS if any(i.get('category') == c for i in items)]
    order += [c for c in dict.fromkeys(i.get('category') for i in items) if c not in order]
    lines = []
    for cat in order:
        rows = [i for i in items if i.get('category') == cat]
        label = _category_label(cat, tr)
        if len(rows) == 1:
            lines.append(_i18n.render(_i18n.lazy_gettext('%(label)s: %(message)s', label=label, message=rows[0]['msg']).spec, tr))
            continue
        lines.append(_i18n.render(_i18n.lazy_ngettext(
            '%(label)s: %(num)d event, latest %(message)s', '%(label)s: %(num)d events, latest %(message)s',
            len(rows), label=label, message=rows[-1]['msg']).spec, tr))
    if dropped:
        lines.append(_i18n.render(_i18n.lazy_ngettext('and %(num)d more', 'and %(num)d more', dropped).spec, tr))
    head = _i18n.render(_i18n.lazy_gettext('Summary %(start)s to %(end)s', start=items[0]['ts'], end=items[-1]['ts']).spec, tr)
    return head + "\n" + "\n".join(lines)


DIGEST_SECONDS = {'hourly': 3600, 'daily': 86400}
FLUSH_INTERVAL = 60
QUEUE_MAX_AGE  = 86400


def _item_epoch(item):
    at = item.get('at')
    if isinstance(at, (int, float)):
        return float(at)
    try:
        return time.mktime(time.strptime(str(item.get('ts', '')), "%Y-%m-%d %H:%M:%S"))
    except (ValueError, TypeError):
        return None


def _fresh_items(ch, items, now=None):
    period = DIGEST_SECONDS.get(str(ch.get('digest', 'immediate')).strip().lower()) or 0
    cutoff = (now if now is not None else time.time()) - max(QUEUE_MAX_AGE, period * 2)
    fresh = []
    for item in items:
        at = _item_epoch(item)
        if at is not None and at >= cutoff:
            fresh.append(item)
    return fresh


def _digest_due(ch, held, now=None) -> bool:
    period = DIGEST_SECONDS.get(str(ch.get('digest', 'immediate')).strip().lower())
    if not period:
        return True
    started = held.get('started')
    if not isinstance(started, (int, float)):
        return True
    return ((now if now is not None else time.time()) - started) >= period


def flush_due():
    try:
        flush_queue()
    except Exception:
        logger.exception("Queue flush failed")
    return []


def flush_queue(channel_id=None, force=False) -> int:
    try:
        channels = settings_mod.load_settings().get('notification_channels', [])
    except Exception:
        return 0
    by_id = {c.get('id'): c for c in channels}
    sent = 0
    with _notif_lock, _file_lock():
        q = _queue_read()
        for cid in list(q):
            if channel_id and cid != channel_id:
                continue
            ch = by_id.get(cid)
            if not ch or not ch.get('enabled', True):
                del q[cid]
                continue
            if not force and _in_quiet_hours(ch.get('quiet_hours', '')):
                continue
            held = q.get(cid) or {}
            if not force and not _digest_due(ch, held):
                continue
            items = _fresh_items(ch, held.get('items') or [])
            if not items:
                del q[cid]
                continue
            report = build_report(items, held.get('dropped', 0), outgoing_translations())
            worst = max(items, key=lambda r: SEVERITY_RANK.get(r.get('type'), 0))
            try:
                _deliver(ch, worst.get('type', 'info'), report, items[-1]['ts'], '')
                sent += 1
            except Exception:
                logger.exception("Queue flush delivery raised")
            del q[cid]
        _queue_write(q)
    return sent


SEVERITY_RANK = {'info': 0, 'success': 0, 'warning': 1, 'error': 2}


def _in_quiet_hours(window: str, when=None) -> bool:
    if not window or '-' not in window:
        return False
    try:
        start_s, end_s = window.split('-', 1)
        sh, sm = [int(x) for x in start_s.strip().split(':')]
        eh, em = [int(x) for x in end_s.strip().split(':')]
    except Exception:
        return False
    t = time.localtime(when if when is not None else time.time())
    cur   = t.tm_hour * 60 + t.tm_min
    start = sh * 60 + sm
    end   = eh * 60 + em
    if start == end:
        return False
    if start < end:
        return start <= cur < end
    return cur >= start or cur < end


def _wants(channel: dict, type_: str, category: str) -> bool:
    if not channel.get('enabled', True):
        return False
    cats = channel.get('categories') or []
    if cats and category not in cats:
        return False
    floor = SEVERITY_RANK.get(channel.get('min_severity', 'info'), 0)
    return SEVERITY_RANK.get(type_, 0) >= floor


def _deliver(channel: dict, type_: str, msg: str, ts: str, category: str = 'config'):
    missing = providers.missing_fields(channel)
    if missing:
        logger.warning(f"Channel {channel.get('name')} is missing {', '.join(missing)}")
        return
    source = (_category_label(category, outgoing_translations()) if category in CATEGORY_LABELS else '') or 'Traefik Manager'
    ok, err = providers.send(channel, type_, source, msg, ts)
    if not ok:
        logger.warning(f"Channel {channel.get('name')} delivery failed: {err}")


def _fire_webhook(type_: str, msg: str, ts: str, category: str = 'config'):
    try:
        channels = settings_mod.load_settings().get('notification_channels', [])
    except Exception:
        return
    for ch in channels:
        try:
            if not _wants(ch, type_, category):
                continue
            quiet = _in_quiet_hours(ch.get('quiet_hours', ''))
            breaks = ch.get('break_through') and type_ == 'error'
            if quiet and not breaks:
                queue_add(ch.get('id', ''), type_, msg, ts, category)
                continue
            if ch.get('digest', 'immediate') != 'immediate':
                queue_add(ch.get('id', ''), type_, msg, ts, category)
                continue
            _deliver(ch, type_, msg, ts, category)
        except Exception:
            logger.exception("Channel delivery raised")


def _load_notifications():
    with _notif_lock, _file_lock():
        _sync(_read_file())

DEDUPE_WINDOW = 8


def _recently_logged(entries, msg, now):
    for entry in reversed(entries):
        try:
            age = now - time.mktime(time.strptime(entry.get('ts', ''), "%Y-%m-%d %H:%M:%S"))
        except (ValueError, TypeError):
            continue
        if age > DEDUPE_WINDOW:
            return False
        if entry.get('msg') == msg:
            return True
    return False


def get_notifications():
    with _notif_lock, _file_lock():
        entries = _read_file()
        _sync(entries)
        return list(reversed(entries[-MAX_ENTRIES:]))


def shown_entries(entries, translations=None):
    out = []
    for entry in entries:
        if isinstance(entry, dict) and 'i18n' in entry:
            entry = dict(entry)
            spec = entry.pop('i18n')
            if _i18n.is_spec(spec):
                entry['msg'] = _i18n.render(spec, translations) or entry.get('msg', '')
        out.append(entry)
    return out


def delete_notification(ts):
    with _notif_lock, _file_lock():
        entries, next_id = _read_state()
        for i, entry in enumerate(entries):
            if entry.get('ts') == ts:
                del entries[i]
                break
        _write_file(entries, next_id)
        _sync(entries)
    return True


def delete_notification_by_id(nid):
    try:
        nid = int(nid)
    except (TypeError, ValueError):
        return False
    with _notif_lock, _file_lock():
        entries, next_id = _read_state()
        keep = [e for e in entries if e.get('id') != nid]
        if len(keep) == len(entries):
            _sync(entries)
            return False
        _write_file(keep, next_id)
        _sync(keep)
    return True


def clear_notifications():
    with _notif_lock, _file_lock():
        _, next_id = _read_state()
        _write_file([], next_id)
        _sync([])
    return True


def highest_id():
    with _notif_lock, _file_lock():
        entries, _ = _read_state()
        return max((e.get('id', 0) for e in entries), default=0)


def add_notification(type_, msg, category='config', webhook=True):
    spec = _i18n.to_stored(msg) if isinstance(msg, _i18n.Message) else None
    msg = str(msg or '').strip()
    if not msg:
        return False
    now   = time.time()
    entry = {'ts': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
             'type': type_, 'msg': msg, 'category': category,
             'at': int(now)}
    if _i18n.is_spec(spec):
        entry['i18n'] = spec
    try:
        with _notif_lock, _file_lock():
            entries, next_id = _read_state()
            if _recently_logged(entries, msg, now):
                _sync(entries)
                return False
            entry['id'] = next_id
            entries.append(entry)
            entries = entries[-MAX_ENTRIES:]
            _write_file(entries, next_id + 1)
            _sync(entries)
    except Exception:
        logger.exception("Failed to store notification")
        return False
    if webhook:
        out = msg
        if _i18n.is_spec(spec):
            try:
                out = _i18n.render(spec, outgoing_translations()).strip() or msg
            except Exception:
                out = msg
        threading.Thread(target=_fire_webhook,
                         args=(type_, out, entry['ts'], category), daemon=True).start()
    return True
