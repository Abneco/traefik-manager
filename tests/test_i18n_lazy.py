import json

from core import i18n as _i18n
from core import notifications as N

DELETED = 'Route %(name)s deleted'
READ_ONLY = 'acme.json is mounted read only'
REMOVED = ('Removed %(num)d certificate, then stopped at %(file)s: %(detail)s',
           'Removed %(num)d certificates, then stopped at %(file)s: %(detail)s')


def test_a_lazy_message_reads_as_english_and_keeps_its_spec():
    msg = _i18n.lazy_gettext(DELETED, name='api')
    assert msg == 'Route api deleted'
    assert msg.spec == {'id': DELETED, 'params': {'name': 'api'}}
    assert json.loads(json.dumps(_i18n.to_stored(msg))) == msg.spec


def test_a_spec_renders_in_another_language():
    msg = _i18n.lazy_gettext(DELETED, name='api')
    assert _i18n.render(msg.spec, _i18n.translations_for('de')) == 'Route api gelöscht'
    assert _i18n.render(msg.spec, _i18n.translations_for('')) == 'Route api deleted'


def test_nested_messages_and_plurals_render_together():
    msg = _i18n.lazy_ngettext(*REMOVED, 3, file='acme.json', detail=_i18n.lazy_gettext(READ_ONLY))
    assert msg == 'Removed 3 certificates, then stopped at acme.json: acme.json is mounted read only'
    german = _i18n.render(msg.spec, _i18n.translations_for('de'))
    assert german.startswith('3 ') and 'acme.json' in german and german != str(msg)
    assert _i18n.render(_i18n.lazy_ngettext(*REMOVED, 1, file='f', detail='d').spec).startswith('Removed 1 certificate,')


def test_a_broken_translation_falls_back_to_english():
    class Broken:
        def ugettext(self, msgid):
            return 'Route %(nom)s supprimée'
    msg = _i18n.lazy_gettext(DELETED, name='api')
    assert _i18n.render(msg.spec, Broken()) == 'Route api deleted'


def test_revive_turns_a_stored_spec_back_into_a_message():
    stored = json.loads(json.dumps(_i18n.to_stored(_i18n.lazy_gettext(DELETED, name='api'))))
    back = _i18n.revive(stored)
    assert isinstance(back, _i18n.Message) and back == 'Route api deleted'
    assert _i18n.revive('plain text') == 'plain text'


def test_json_responses_render_messages_in_the_requester_language(app_module):
    app = app_module.app
    payload = {'items': [_i18n.lazy_gettext(DELETED, name='api')], 'plain': 'x'}
    with app.test_request_context('/', headers={'Accept-Language': 'de'}):
        assert app.json.loads(app.json.dumps(payload)) == {'items': ['Route api gelöscht'], 'plain': 'x'}
    with app.test_request_context('/'):
        assert app.json.loads(app.json.dumps(payload))['items'] == ['Route api deleted']


def test_the_bell_stores_the_spec_and_shows_it_per_viewer(monkeypatch):
    monkeypatch.setattr(N, '_fire_webhook', lambda *a, **k: None)
    assert N.add_notification('info', _i18n.lazy_gettext(DELETED, name='bell-test'), webhook=False)
    entry = next(e for e in N.get_notifications() if e.get('msg') == 'Route bell-test deleted')
    assert entry['i18n'] == {'id': DELETED, 'params': {'name': 'bell-test'}}
    shown = N.shown_entries([entry], _i18n.translations_for('de'))[0]
    assert shown['msg'] == 'Route bell-test gelöscht' and 'i18n' not in shown
    assert entry['i18n']


def test_plain_text_notifications_are_unchanged(monkeypatch):
    monkeypatch.setattr(N, '_fire_webhook', lambda *a, **k: None)
    assert N.add_notification('info', 'plain bell text', webhook=False)
    entry = next(e for e in N.get_notifications() if e.get('msg') == 'plain bell text')
    assert 'i18n' not in entry
    assert N.shown_entries([entry], _i18n.translations_for('de'))[0]['msg'] == 'plain bell text'


def test_webhooks_go_out_in_the_instance_language(monkeypatch):
    sent = []

    class Now:
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            sent.append(self.args[1])

    monkeypatch.setattr(N.threading, 'Thread', Now)
    monkeypatch.setattr(N.settings_mod, 'load_settings', lambda: {'default_language': 'de'})
    N.add_notification('info', _i18n.lazy_gettext(DELETED, name='hook-de'))
    monkeypatch.setattr(N.settings_mod, 'load_settings', lambda: {'default_language': ''})
    N.add_notification('info', _i18n.lazy_gettext(DELETED, name='hook-en'))
    assert sent == ['Route hook-de gelöscht', 'Route hook-en deleted']


def test_the_digest_report_uses_the_given_language():
    items = [{'type': 'warning', 'msg': f'rollup {i}', 'ts': f'0{i}:00:00', 'category': 'crowdsec'}
             for i in range(1, 4)]
    english = N.build_report(items)
    assert english.startswith('Summary 01:00:00 to 03:00:00') and '3 events, latest rollup 3' in english
    assert N.build_report(items, translations=_i18n.translations_for('de')).count('rollup 3') == 1
