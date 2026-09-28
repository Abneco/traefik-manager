import core.notifications as N
from tests.conftest import post_json


def _reset():
    N.clear_notifications()


def test_two_in_the_same_second_delete_independently(app_module, monkeypatch):
    _reset()
    frozen = int(N.time.time()) + 0.5
    monkeypatch.setattr(N.time, 'time', lambda: frozen)
    N.add_notification('info', 'first in this second', webhook=False)
    N.add_notification('info', 'second in this second', webhook=False)
    rows = N.get_notifications()
    newest, older = rows[0], rows[1]
    assert newest['ts'] == older['ts'], 'the two must share a second for this to test anything'
    assert newest['id'] != older['id']
    assert N.delete_notification_by_id(newest['id']) is True
    left = [r['msg'] for r in N.get_notifications()]
    assert older['msg'] in left
    assert newest['msg'] not in left


def test_deleting_an_unknown_id_reports_a_miss(app_module):
    _reset()
    assert N.delete_notification_by_id(999999) is False
    assert N.delete_notification_by_id('nonsense') is False


def test_ids_are_never_reused_after_a_clear(app_module):
    _reset()
    N.add_notification('info', 'before the clear', webhook=False)
    top = N.highest_id()
    N.clear_notifications()
    N.add_notification('info', 'after the clear', webhook=False)
    assert N.get_notifications()[0]['id'] > top


def test_every_row_carries_an_epoch(app_module):
    _reset()
    N.add_notification('info', 'stamped', webhook=False)
    row = N.get_notifications()[0]
    assert isinstance(row['at'], int) and row['at'] > 0
    assert row['ts']


def test_a_legacy_file_is_backfilled(app_module, tmp_path, monkeypatch):
    import core.env as env
    path = tmp_path / 'notifications.yml'
    path.write_text(
        '- ts: "2026-08-01 10:00:00"\n  type: info\n  msg: old one\n'
        '- ts: "not a date"\n  type: info\n  msg: unparseable\n'
    )
    monkeypatch.setattr(env, 'NOTIFICATIONS_PATH', str(path))
    rows = N.get_notifications()
    assert len(rows) == 2, 'an unparseable row must not be dropped'
    assert all(isinstance(r.get('id'), int) and r['id'] > 0 for r in rows)
    assert all(isinstance(r.get('at'), int) for r in rows)
    bad = [r for r in rows if r['msg'] == 'unparseable'][0]
    assert bad['at'] == 0


def test_the_list_endpoint_is_still_a_plain_array(client, app_module):
    _reset()
    N.add_notification('info', 'shape check', webhook=False)
    body = client.get('/api/notifications').get_json()
    assert isinstance(body, list), 'clients in the wild depend on a bare array'
    assert 'id' in body[0] and 'at' in body[0]


def test_delete_by_ts_still_works(client, app_module):
    _reset()
    N.add_notification('info', 'by ts', webhook=False)
    ts = N.get_notifications()[0]['ts']
    r = post_json(client, '/api/notifications/delete', {'ts': ts})
    assert r.status_code == 200 and r.get_json()['ok'] is True
    assert N.get_notifications() == []


def test_delete_by_id_over_http(client, app_module):
    _reset()
    N.add_notification('info', 'by id', webhook=False)
    nid = N.get_notifications()[0]['id']
    assert post_json(client, '/api/notifications/delete', {'id': nid}).status_code == 200
    assert post_json(client, '/api/notifications/delete', {'id': nid}).status_code == 404


def test_unread_survives_the_cap(client, app_module):
    _reset()
    for i in range(N.MAX_ENTRIES):
        N.add_notification('info', f'filler {i}', webhook=False)
    post_json(client, '/api/notifications/read', {'all': True})
    assert client.get('/api/notifications/state').get_json()['unread'] == 0
    N.add_notification('info', 'the one that used to vanish', webhook=False)
    state = client.get('/api/notifications/state').get_json()
    assert state['count'] == N.MAX_ENTRIES, 'still at the cap'
    assert state['unread'] == 1, 'length based counting reported 0 here'


def test_read_marker_round_trips(client, app_module):
    _reset()
    N.add_notification('info', 'one', webhook=False)
    N.add_notification('info', 'two', webhook=False)
    rows = N.get_notifications()
    post_json(client, '/api/notifications/read', {'id': rows[1]['id']})
    state = client.get('/api/notifications/state').get_json()
    assert state['read_until'] == rows[1]['id']
    assert state['unread'] == 1


def test_the_file_stays_a_plain_list_for_older_builds(app_module):
    from ruamel.yaml import YAML
    import core.env as env
    _reset()
    N.add_notification('info', 'downgrade check', webhook=False)
    with open(env.NOTIFICATIONS_PATH) as f:
        data = YAML(typ='safe').load(f)
    assert isinstance(data, list), 'a 1.11 build reads this file as a list'
    legacy = [e for e in data if isinstance(e, dict)]
    assert len(legacy) == 1, 'the pre-1.12 reader must still see the rows'
    assert legacy[0]['msg'] == 'downgrade check'


def test_the_counter_survives_a_clear_via_the_sidecar(app_module):
    _reset()
    N.add_notification('info', 'before', webhook=False)
    top = N.highest_id()
    N.clear_notifications()
    assert N._read_counter() > top, 'the sidecar must outlive an emptied list'
    N.add_notification('info', 'after', webhook=False)
    assert N.get_notifications()[0]['id'] > top


def test_a_missing_counter_falls_back_to_the_highest_id(app_module, tmp_path, monkeypatch):
    import core.env as env
    path = tmp_path / 'notifications.yml'
    path.write_text('- {id: 40, at: 0, ts: "x", type: info, msg: forty}\n')
    monkeypatch.setattr(env, 'NOTIFICATIONS_PATH', str(path))
    assert N._read_counter() == 0, 'no sidecar present'
    entries, next_id = N._read_state()
    assert next_id == 41, 'derived from the rows when the counter is gone'
