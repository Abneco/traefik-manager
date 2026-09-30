import json
import time

import pytest


class _Resp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload    = payload

    def json(self):
        return self._payload


class _Fleet:
    def __init__(self):
        self.agents   = []
        self.health   = {}
        self.certs    = {}
        self.traefik  = {}
        self.crowdsec = {}
        self.explode  = set()
        self.calls    = []

    def add(self, agent_id, name):
        self.agents.append({'id': agent_id, 'name': name,
                            'url': f"http://{agent_id}.invalid:8080", 'api_key': 'k'})
        self.health[agent_id]  = True
        self.certs[agent_id]   = []
        self.traefik[agent_id] = True
        return agent_id

    def paths(self, agent_id):
        return [p for a, p in self.calls if a == agent_id]

    def health_get(self, url, **kwargs):
        for agent in self.agents:
            if agent['url'] in url:
                self.calls.append((agent['id'], '/health'))
                return _Resp(200 if self.health[agent['id']] else 502)
        raise AssertionError('unexpected health url %r' % url)

    def request(self, agent, method, path, **kwargs):
        agent_id = str(agent['id'])
        self.calls.append((agent_id, path))
        if agent_id in self.explode:
            raise RuntimeError('agent %s is broken' % agent_id)
        if path == '/api/traefik/certs':
            return _Resp(200, {'certs': self.certs[agent_id]})
        if path == '/api/traefik/overview':
            return _Resp(200, {'ok': True}) if self.traefik[agent_id] else _Resp(502)
        if path == '/api/crowdsec/alerts':
            status, payload = self.crowdsec.get(agent_id, (404, None))
            return _Resp(status, payload)
        raise AssertionError('unexpected agent path %r' % path)


@pytest.fixture
def mon(monkeypatch, tmp_path):
    from core import certs as certs_mod
    from core import geoip as geoip_mod
    from core import monitor
    from core import notifications
    from core import settings as settings_mod
    from core import traefik as traefik_mod

    sent  = []
    fleet = _Fleet()

    def _record(type_, msg, category=None, webhook=True):
        sent.append((type_, msg, category))
        return True

    monkeypatch.setattr(notifications, 'add_notification', _record)
    monkeypatch.setattr(monitor, '_state_path', lambda: str(tmp_path / 'monitor.json'))
    monkeypatch.setattr(monitor, '_lock_path', lambda: str(tmp_path / 'monitor.lock'))
    monkeypatch.setattr(monitor, '_checks', list(monitor._checks))
    monkeypatch.setattr(settings_mod, 'get_acme_json_paths', lambda: [])
    monkeypatch.setattr(certs_mod, '_certs_from_tls_configs', lambda: [])
    monkeypatch.setattr(traefik_mod, 'traefik_api_get', lambda path: {'ok': True})
    monkeypatch.setattr(geoip_mod, '_geoip_enabled', lambda: False)
    monkeypatch.setattr(monitor, '_agents', lambda: fleet.agents)
    monkeypatch.setattr(monitor.requests, 'get', fleet.health_get)
    monkeypatch.setattr(monitor.agents_http_mod, '_agent_request', fleet.request)
    monitor._state.clear()
    yield monitor, sent, fleet
    monitor._state.clear()


def _iso(base, days):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(base + days * 86400))


def _cert(main, not_after, resolver='le'):
    return {'resolver': resolver, 'main': main, 'not_after': not_after}


def _only(sent, category):
    return [s for s in sent if s[2] == category]


def _host_certs(monkeypatch, certs):
    from core import certs as certs_mod
    monkeypatch.setattr(certs_mod, '_certs_from_tls_configs', lambda: certs)


def test_an_agent_cert_names_the_agent_and_the_host_cert_does_not(mon, monkeypatch):
    monitor, sent, fleet = mon

    base = float(int(time.time()))
    monkeypatch.setattr(monitor, '_now', lambda: base)
    _host_certs(monkeypatch, [_cert('host.example.com', _iso(base, 10))])
    fleet.add('vps1', 'VPS One')
    fleet.certs['vps1'] = [_cert('agent.example.com', _iso(base, 10))]

    msgs = sorted(m for _, m, c in monitor.run_checks_once(force=True) if c == 'certs')
    assert msgs == ['Certificate for host.example.com (le) expires in 10 days',
                    'VPS One: Certificate for agent.example.com (le) expires in 10 days'], msgs


def test_the_same_domain_on_two_servers_keeps_two_independent_states(mon, monkeypatch):
    monitor, sent, fleet = mon

    base  = float(int(time.time()))
    stamp = {'host': _iso(base, 10), 'agent': _iso(base, 10)}
    monkeypatch.setattr(monitor, '_now', lambda: base)
    _host_certs(monkeypatch, [_cert('shared.example.com', stamp['host'])])
    fleet.add('vps1', 'VPS One')
    monkeypatch.setattr(monitor, '_agents', lambda: fleet.agents)

    def _agent_certs():
        return [_cert('shared.example.com', stamp['agent'])]

    fleet.certs['vps1'] = _agent_certs()
    raised = _only(monitor.run_checks_once(force=True), 'certs')
    assert len(raised) == 2, raised
    assert sorted(m for _, m, _ in raised) == [
        'Certificate for shared.example.com (le) expires in 10 days',
        'VPS One: Certificate for shared.example.com (le) expires in 10 days'], raised

    assert _only(monitor.run_checks_once(force=True), 'certs') == [], 'the same certs alerted twice'

    stamp['host'] = _iso(base, 90)
    _host_certs(monkeypatch, [_cert('shared.example.com', stamp['host'])])
    assert _only(monitor.run_checks_once(force=True), 'certs') == [], \
        'renewing one server re-alerted the other'

    monkeypatch.setattr(monitor, '_now', lambda: base + 8 * 86400)
    later = _only(monitor.run_checks_once(force=True), 'certs')
    assert [m for _, m, _ in later] == [
        'VPS One: Certificate for shared.example.com (le) expires in 2 days'], later


def test_traefik_down_on_both_servers_recovers_independently(mon, monkeypatch):
    monitor, sent, fleet = mon
    from core import traefik as traefik_mod

    fleet.add('vps1', 'VPS One')
    fleet.traefik['vps1'] = False
    monkeypatch.setattr(traefik_mod, 'traefik_api_get', lambda path: None)

    monitor.run_checks_once(force=True)
    monitor.run_checks_once(force=True)
    assert [m for _, m, _ in _only(sent, 'traefik')] == ['Traefik API is unreachable',
                                                         'VPS One: Traefik API is unreachable'], sent

    monkeypatch.setattr(traefik_mod, 'traefik_api_get', lambda path: {'ok': True})
    monitor.run_checks_once(force=True)
    monitor.run_checks_once(force=True)
    assert [m for _, m, _ in _only(sent, 'traefik')][2:] == ['Traefik API is reachable again'], sent

    fleet.traefik['vps1'] = True
    monitor.run_checks_once(force=True)
    monitor.run_checks_once(force=True)
    assert [m for _, m, _ in _only(sent, 'traefik')] == [
        'Traefik API is unreachable',
        'VPS One: Traefik API is unreachable',
        'Traefik API is reachable again',
        'VPS One: Traefik API is reachable again'], sent


def test_an_unreachable_agent_raises_one_notification_not_one_per_check(mon, monkeypatch):
    monitor, sent, fleet = mon

    base = float(int(time.time()))
    monkeypatch.setattr(monitor, '_now', lambda: base)
    fleet.add('vps1', 'VPS One')
    fleet.health['vps1']   = False
    fleet.certs['vps1']    = [_cert('agent.example.com', _iso(base, 1))]
    fleet.traefik['vps1']  = False
    fleet.crowdsec['vps1'] = (502, None)

    monitor.run_checks_once(force=True)
    monitor.run_checks_once(force=True)

    assert sent == [('error', 'Agent VPS One is unreachable', 'agent')], sent
    assert fleet.paths('vps1') == ['/health', '/health'], fleet.calls


def test_one_broken_agent_does_not_stop_the_next_one(mon, monkeypatch):
    monitor, sent, fleet = mon

    base = float(int(time.time()))
    monkeypatch.setattr(monitor, '_now', lambda: base)
    fleet.add('vps1', 'VPS One')
    fleet.add('vps2', 'VPS Two')
    fleet.explode.add('vps1')
    fleet.certs['vps2'] = [_cert('two.example.com', _iso(base, 2))]

    raised = monitor.run_checks_once(force=True)
    assert [m for _, m, c in raised if c == 'certs'] == [
        'VPS Two: Certificate for two.example.com (le) expires in 2 days'], raised
    assert fleet.paths('vps2') == ['/health', '/api/traefik/version', '/api/traefik/certs',
                                   '/api/traefik/overview', '/api/crowdsec/alerts',
                                   '/api/events?since=0',
                                   '/api/traefik/version'], fleet.calls
    assert [m for _, m, c in raised if c == 'traefik'] == [
        'VPS One: Traefik API is unreachable'], raised


def test_a_legacy_bare_state_key_is_read_as_the_hosts(mon, monkeypatch, tmp_path):
    monitor, sent, fleet = mon
    from core import traefik as traefik_mod

    base   = float(int(time.time()))
    expiry = _iso(base, 5)
    monkeypatch.setattr(monitor, '_now', lambda: base)
    _host_certs(monkeypatch, [_cert('api.example.com', expiry)])
    monkeypatch.setattr(traefik_mod, 'traefik_api_get', lambda path: None)

    with open(str(tmp_path / 'monitor.json'), 'w') as f:
        json.dump({'certs': {'le:api.example.com': {'not_after': expiry, 'fired': [14, 3]}},
                   'traefik': {'up': True}}, f)

    raised = monitor.run_checks_once(force=True)
    assert _only(raised, 'certs') == [], 'an upgrade re-alerted a cert that had already fired'
    assert [m for _, m, _ in _only(raised, 'traefik')] == ['Traefik API is unreachable'], raised

    with open(str(tmp_path / 'monitor.json')) as f:
        saved = json.load(f)
    assert list(saved['certs']) == ['host|le:api.example.com'], saved
    assert list(saved['traefik']) == ['host|up'], saved


def test_agent_crowdsec_alerts_name_the_agent(mon):
    monitor, sent, fleet = mon

    fleet.add('vps1', 'VPS One')
    fleet.crowdsec['vps1'] = (200, [{'id': 1, 'source': {'ip': '1.2.3.4', 'scope': 'Ip'},
                                     'scenario': 'crowdsecurity/http-probing', 'events_count': 5}])
    assert _only(monitor.run_checks_once(force=True), 'crowdsec') == [], 'the first poll alerted'

    fleet.crowdsec['vps1'] = (200, [{'id': 2, 'source': {'ip': '1.2.3.4', 'scope': 'Ip'},
                                     'scenario': 'crowdsecurity/http-probing', 'events_count': 7}])
    raised = _only(monitor.run_checks_once(force=True), 'crowdsec')
    assert len(raised) == 1, raised
    type_, msg, category = raised[0]
    assert (type_, category) == ('warning', 'crowdsec')
    assert msg.startswith('VPS One: '), 'the agent name must lead the message'
    assert '1.2.3.4' in msg and 'http-probing' in msg and '7 events' in msg
    assert _only(monitor.run_checks_once(force=True), 'crowdsec') == [], 'the same alert repeated'


def test_an_agent_lapi_outage_is_edge_triggered(mon):
    monitor, sent, fleet = mon

    fleet.add('vps1', 'VPS One')
    fleet.crowdsec['vps1'] = (502, None)
    monitor.run_checks_once(force=True)
    monitor.run_checks_once(force=True)
    assert [m for _, m, _ in _only(sent, 'crowdsec')] == ['VPS One: CrowdSec LAPI is unreachable'], sent

    fleet.crowdsec['vps1'] = (200, [])
    monitor.run_checks_once(force=True)
    monitor.run_checks_once(force=True)
    assert [m for _, m, _ in _only(sent, 'crowdsec')] == ['VPS One: CrowdSec LAPI is unreachable',
                                                          'VPS One: CrowdSec LAPI is reachable again'], sent


def test_an_agent_without_crowdsec_stays_quiet(mon):
    monitor, sent, fleet = mon

    fleet.add('vps1', 'VPS One')
    monitor.run_checks_once(force=True)
    monitor.run_checks_once(force=True)
    assert _only(sent, 'crowdsec') == [], sent
