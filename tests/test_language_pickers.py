import re

import pytest

import core.settings as settings_mod
from core import i18n
from tests.test_setup_wizard_fields import BASE, _fresh_setup

TAGS = ('en', 'de', 'fr-CA', 'zh-Hans')


@pytest.fixture
def languages(monkeypatch):
    monkeypatch.setattr(i18n, 'available_tags', lambda locale_dir=None: TAGS)


def _links(html):
    return re.findall(r'<a class="lang-link[^"]*" href="([^"]*)"', html)


def test_the_login_page_links_every_language_and_keeps_the_target(anon_client, languages):
    html = anon_client.get('/login?next=/routes&lang=de').get_data(as_text=True)
    assert 'lang-corner' in html
    links = _links(html)
    assert '/fr-CA/login?next=%2Froutes' in links
    assert '/zh-Hans/login?next=%2Froutes' in links
    assert not any('lang=' in link for link in links)
    assert len(links) == len(TAGS)


def test_the_setup_wizard_offers_follow_system_first(client, languages):
    _fresh_setup(client)
    html = client.get('/setup').get_data(as_text=True)
    links = _links(html)
    assert links[0] == '/setup'
    assert '/de/setup' in links
    assert 'name="default_language" value=""' in html


def test_a_language_prefix_carries_into_the_saved_field(client, languages):
    _fresh_setup(client)
    html = client.get('/fr-CA/setup').get_data(as_text=True)
    assert 'name="default_language" value="fr-CA"' in html
    assert 'action="/fr-CA/setup"' in html


def test_setup_saves_the_language_picked_on_the_welcome_step(client, languages):
    _fresh_setup(client)
    client.post('/setup', data={**BASE, 'default_language': 'fr-ca'}, headers={'X-Requested-With': 'fetch'})
    assert settings_mod.load_settings()['default_language'] == 'fr-CA'


def test_setup_ignores_a_language_this_release_does_not_ship(client, languages):
    _fresh_setup(client)
    client.post('/setup', data={**BASE, 'default_language': 'xx'}, headers={'X-Requested-With': 'fetch'})
    assert settings_mod.load_settings()['default_language'] == ''
