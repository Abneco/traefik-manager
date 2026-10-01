import ast
import json
import os

from babel.support import NullTranslations

from core import i18n as _i18n
from core import notifications as N
from tests.conftest import post_json, tm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNTRANSLATED = NullTranslations()


def _capture(monkeypatch):
    sent = []
    monkeypatch.setattr(tm, 'add_notification', lambda type_, msg, **kw: sent.append((type_, msg, kw)) or True)
    return sent


def test_every_app_notification_is_a_lazy_message_or_forwarded_user_text():
    with open(os.path.join(ROOT, 'app.py'), encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'add_notification'):
            continue
        msg = node.args[1]
        assert not isinstance(msg, (ast.JoinedStr, ast.Constant)), \
            f'app.py:{node.lineno} passes English text to add_notification'
        if isinstance(msg, ast.BinOp):
            raise AssertionError(f'app.py:{node.lineno} glues a notification together')


def test_the_update_notification_keeps_its_english_and_renders_per_viewer(client, monkeypatch):
    sent = _capture(monkeypatch)
    r = post_json(client, '/api/notifications/update', {'version': '9.9.9', 'product': 'manager'})
    assert r.status_code == 200
    (type_, msg, kw), = sent
    assert (type_, kw) == ('info', {'category': 'update'})
    assert msg == 'Traefik Manager v9.9.9 is available - update now'
    stored = json.loads(json.dumps(_i18n.to_stored(msg)))
    assert stored == msg.spec
    assert _i18n.render(stored, UNTRANSLATED) == 'Traefik Manager v9.9.9 is available - update now'
    assert _i18n.revive(stored) == msg


def test_the_bell_stores_a_route_save_notification_as_a_spec(monkeypatch):
    monkeypatch.setattr(N, '_fire_webhook', lambda *a, **k: None)
    msg = _i18n.lazy_ngettext('Backup created (%(num)d file)', 'Backup created (%(num)d files)', 2)
    assert msg == 'Backup created (2 files)'
    assert N.add_notification('success', msg, category='backup', webhook=False)
    entry = next(e for e in N.get_notifications() if e.get('msg') == 'Backup created (2 files)')
    assert json.loads(json.dumps(entry['i18n'])) == msg.spec
    assert _i18n.render(entry['i18n'], UNTRANSLATED) == 'Backup created (2 files)'


def test_the_stale_crowdsec_note_is_a_whole_sentence_with_a_reason():
    note = tm._cs_stale_note(7200, 'HTTP 401')
    assert note == ('CrowdSec has not answered for 2 hours, so these decisions are the last ones '
                    'read and may be out of date. HTTP 401')
    assert note.spec['n'] == 2 and note.spec['params'] == {'reason': 'HTTP 401'}
    assert _i18n.render(json.loads(json.dumps(note.spec)), _i18n.translations_for('')) == str(note)


def test_a_translated_stale_reason_is_nested_in_the_note(client, monkeypatch):
    reason = _i18n.lazy_gettext('Git push failed: %(error)s', error='HTTP 401')
    mode = type('Mode', (str,), {})('stale:7200:' + reason)
    mode.age, mode.reason = 7200, reason
    monkeypatch.setattr(tm._crowd, 'cs_decisions_stream', lambda force_full=False: ([], mode))
    monkeypatch.setattr(tm._crowd, '_cs_stream_cache', {'streamable': True})
    _active, note = tm._cs_active_decisions()
    assert note.spec['params']['reason'] == reason.spec
    assert str(note).endswith('may be out of date. Git push failed: HTTP 401')


def test_an_exception_carrying_a_message_is_nested_not_flattened():
    inner = _i18n.lazy_gettext('acme.json is mounted read only')
    msg = _i18n.lazy_gettext('Git restore failed: %(error)s', error=tm._error_param(RuntimeError(inner)))
    assert msg == 'Git restore failed: acme.json is mounted read only'
    assert msg.spec['params']['error'] == inner.spec
    assert tm._error_param(RuntimeError('boom')) == 'boom'
