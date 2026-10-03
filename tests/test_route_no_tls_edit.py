import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_an_http_route_without_tls_reports_tls_as_false():
    src = _read('core', 'routes_build.py')
    assert "tls_on   = 'tls' in rdata and rdata.get('tls') is not False" in src


def test_editing_or_cloning_a_route_without_tls_keeps_no_tls():
    js = _read('static', 'js', 'routes.js')
    assert "app.tls !== false" not in js, \
        'tls is false for an http-only route, so the form fell through to __none__ and saved tls: {}'
    assert js.count("if (!app.tls) crHttp.value = '__disabled__';") == 2, 'both edit and clone'


def test_the_form_warns_when_tls_is_on_for_a_plain_http_entry_point():
    html = _read('templates', 'modals', 'route_modal.html')
    assert 'id="tlsPlainEpNote"' in html
    js = _read('static', 'js', 'routes.js')
    body = js[js.index('function _isPlainHttpEp('):js.index('function _showWildcardFields(')]
    assert 'http.tls || http.redirections' in body, 'an entry point with its own TLS or a redirect is fine'
    assert "cr.value !== '__disabled__'" in body
    assert 'tmList(plain)' in body


def test_the_warning_follows_both_the_resolver_and_the_entry_points():
    js = _read('static', 'js', 'routes.js')
    toggle = js[js.index('function toggleWildcardSection('):js.index('function _isPlainHttpEp(')]
    assert '_updateTlsEpNote();' in toggle
    chips = js[js.index('async function _initEntrypointChips('):js.index('function _toggleEpChip(')]
    assert chips.count("if (proto === 'http') _updateTlsEpNote();") == 2
