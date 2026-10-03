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
