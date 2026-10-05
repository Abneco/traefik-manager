import os

import pytest

from core import config as cfg
from core import env


def test_app_aliases_point_at_core(app_module):
    assert app_module.load_config is cfg.load_config
    assert app_module.save_config is cfg.save_config
    assert app_module._strip_empty_sections is cfg.strip_empty_sections
    assert app_module.yaml is cfg.yaml


def test_round_trip_preserves_comments_and_formatting(config_path):
    original = (
        "# leading comment\n"
        "http:\n"
        "  routers:\n"
        "    a:\n"
        "      rule: Host(`a.example.com`)  # inline comment\n"
        "      service: a-service\n"
    )
    config_path.write_text(original)

    data = cfg.load_config(str(config_path))
    data['http']['routers']['b'] = {'rule': 'Host(`b.example.com`)', 'service': 'b-service'}
    cfg.save_config(data, str(config_path))

    raw = config_path.read_text()
    assert '# leading comment' in raw
    assert '# inline comment' in raw
    assert 'b.example.com' in raw
    assert 'a.example.com' in raw


def test_go_templates_survive_a_round_trip(config_path):
    original = (
        "http:\n"
        "  middlewares:\n"
        "    oidc:\n"
        "      plugin:\n"
        "        headers:\n"
        "          - name: X-User\n"
        "            value: \"{{`{{ .claims.preferred_username }}`}}\"\n"
    )
    config_path.write_text(original)
    data = cfg.load_config(str(config_path))
    cfg.save_config(data, str(config_path))
    raw = config_path.read_text()
    assert '.claims.preferred_username' in raw, 'a Go template was mangled by the YAML round trip'


def test_load_config_on_missing_file_returns_empty():
    assert cfg.load_config('/nonexistent/nope.yml') == {}


def test_load_config_on_garbage_returns_empty(config_path):
    config_path.write_text("just a string, not a mapping\n")
    assert cfg.load_config(str(config_path)) == {}


@pytest.mark.parametrize('loader', ['load_config', '_load_config_display'])
def test_bare_section_keys_load_as_empty_maps(config_path, loader):
    # discussion #209: deleting every line under `http:` left it null and broke setup
    config_path.write_text("http:\ntcp:\n  routers:\ntls:\n")
    data = getattr(cfg, loader)(str(config_path))
    assert data['http'] == {}
    assert data['tcp'] == {'routers': {}}
    assert data['tls'] == {}
    data.setdefault('http', {}).setdefault('routers', {})['r'] = {'rule': 'Host(`a`)'}
    assert data['http'].get('middlewares', {}) == {}


def test_save_is_atomic_and_leaves_no_temp_files(config_path):
    cfg.save_config({'http': {'routers': {}}}, str(config_path))
    leftovers = [f for f in os.listdir(os.path.dirname(str(config_path)))
                 if '.tmp.' in f]
    assert not leftovers, 'save_config left a temp file behind: %s' % leftovers


def test_strip_empty_sections():
    assert cfg.strip_empty_sections({'http': {'routers': {}, 'services': {}}}) == {}
    kept = cfg.strip_empty_sections({'http': {'routers': {'a': 1}, 'services': {}}})
    assert kept == {'http': {'routers': {'a': 1}}}


@pytest.mark.parametrize('name,expected', [
    ('svc@file', 'svc'), ('svc', 'svc'), ('a@b@c', 'a'), (None, ''), (123, ''),
])
def test_svc_key(name, expected):
    assert cfg.svc_key(name) == expected


def test_as_dict():
    assert cfg.as_dict({'a': 1}) == {'a': 1}
    assert cfg.as_dict(None) == {}
    assert cfg.as_dict([1, 2]) == {}


def test_path_traversal_is_blocked():
    assert cfg.safe_file_path('/etc/passwd') == ''
    assert cfg.safe_file_path('') == ''
    assert cfg.safe_file_path(env.SETTINGS_PATH), 'a legitimate config path was blocked'


def test_resolve_config_path_accepts_known_files_only():
    known = env.CONFIG_PATHS[0]
    assert cfg.resolve_config_path(os.path.basename(known)) == known
    assert cfg.resolve_config_path(known) == known
    assert cfg.resolve_config_path('') == env.CONFIG_PATH
    assert cfg.resolve_config_path('/etc/shadow') == ''


def test_safe_api_url_rejects_non_http_schemes():
    assert cfg.safe_api_url('http://traefik:8080') == 'http://traefik:8080'
    assert cfg.safe_api_url('https://traefik:8080') == 'https://traefik:8080'
    assert cfg.safe_api_url('file:///etc/passwd') == ''
    assert cfg.safe_api_url('gopher://x') == ''
