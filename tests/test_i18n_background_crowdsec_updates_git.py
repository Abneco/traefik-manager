import json

import pytest

from core import crowdsec as C
from core import git, notifications
from core import i18n as _i18n
from core import updates


def _german(msg):
    return _i18n.render(json.loads(json.dumps(_i18n.to_stored(msg))), _i18n.translations_for('de'))


def _alert(ip, scenario, events, cn=None):
    src = {'value': ip}
    if cn:
        src['cn'] = cn
    return {'id': 1, 'scenario': 'crowdsecurity/' + scenario, 'events_count': events, 'source': src,
            'decisions': [{'origin': 'crowdsec'}]}


def test_the_single_source_summary_is_one_translatable_sentence():
    msg = C.summarise_alerts([_alert('1.2.3.4', 'http-probing', 21)], C._cs_window_label('10m'))
    assert msg == '1.2.3.4 tripped 1 scenario, 21 events in the last 10 minutes: http-probing'
    assert msg.spec['id'] == '%(source)s tripped %(scenarios)s, %(events)s in the last %(window)s: %(list)s'
    assert msg.spec['params']['events']['plural'] == '%(num)d events'
    assert _german(msg) == str(msg)


def test_the_multi_source_summary_is_one_translatable_sentence():
    msg = C.summarise_alerts([_alert('1.2.3.4', 'a', 4), _alert('5.6.7.8', 'b', 1)] +
                             [_alert('1.2.3.4', f's{i}', 1) for i in range(6)], '')
    assert msg.startswith('2 sources tripped 8 scenarios, 11 events. Worst: 1.2.3.4, a, 10 events.')
    assert msg.endswith('Scenarios: a, b, s0, s1 and 4 more')
    assert 'in the last' not in msg.spec['id']
    assert _german(msg) == str(msg)


def test_crowdsec_errors_carry_a_spec():
    with pytest.raises(C.CrowdSecUnavailable) as err:
        C._cs_request_strict('GET', '/v1/decisions', lapi='', key='')
    msg = err.value.args[0]
    assert msg.spec == {'id': 'CrowdSec LAPI URL, bouncer API key or client certificate is not set'}
    assert _i18n.shown_error(err.value) == str(err.value)


def test_the_stale_reason_keeps_its_spec():
    reason = _i18n.lazy_gettext('CrowdSec LAPI unreachable: %(error)s', error='timeout')
    mode = C._cs_stale_mode(C.CS_STALE_AFTER_SECONDS + 5, C.CrowdSecUnavailable(reason))
    _, age, why = mode.split(':', 2)
    assert int(age) == C.CS_STALE_AFTER_SECONDS + 5 and why == 'CrowdSec LAPI unreachable: timeout'
    assert mode.reason.spec == reason.spec
    assert _german(mode.reason) == str(reason)


def test_update_alerts_are_translatable(monkeypatch):
    monkeypatch.setattr(updates.monitor_mod, '_agents', lambda: [{'id': 'a1', 'name': 'proxy'}])
    monkeypatch.setattr(updates.monitor_mod, '_agent_reachable', lambda agent: True)
    monkeypatch.setattr(updates.monitor_mod, '_agent_json', lambda agent, path: {'Version': 'v3.0.0'})
    monkeypatch.setattr(updates, 'latest_release', lambda repo: '3.7.0' if repo == updates.TRAEFIK_REPO else '')
    monkeypatch.setattr(updates, 'running_traefik_version', lambda: '3.1.0')
    msgs = [m for _t, m, _c in updates.check_updates({})]
    assert msgs == ['Traefik v3.7.0 is available - update now',
                    'Traefik on proxy v3.7.0 is available - update now']
    assert msgs[1].spec['params'] == {'agent': 'proxy', 'version': '3.7.0'}
    assert [_german(m) for m in msgs] == msgs


def test_git_results_and_notifications_are_translatable(monkeypatch):
    sent = []
    monkeypatch.setattr(git.settings_mod, 'load_settings', lambda: {
        'git_backup_enabled': True, 'git_backup_auto_push': True, 'git_backup_repo': 'https://x/r.git'})
    monkeypatch.setattr(notifications, 'add_notification', lambda *a, **k: sent.append(a))
    monkeypatch.setattr(git, '_git_push_configs', lambda action: (False, git._failed('push', 'rejected')))
    git._git_push_if_enabled('route save')
    msg = sent[-1][1]
    assert msg == 'Git backup failed (route save): Push failed: rejected'
    assert msg.spec['params']['error']['id'] == 'Push failed: %(error)s'
    monkeypatch.setattr(git, '_git_push_configs', lambda action: (True, ''))
    git._git_push_if_enabled('route save')
    assert sent[-1][1] == 'Git backup pushed (route save)'
    assert _german(sent[-1][1]) == 'Git backup pushed (route save)'


def test_an_unsupported_scheme_survives_the_init_failure():
    msg = git._failed('init', git._init_detail(ValueError(_i18n.lazy_gettext('Unsupported git repository URL scheme')),
                                                lambda text: text))
    assert msg == 'Repo init failed: Unsupported git repository URL scheme'
    assert msg.spec['params']['error'] == {'id': 'Unsupported git repository URL scheme'}
