from dataclasses import dataclass

from corehq.apps.app_manager.views.utils import get_langs


@dataclass
class MockRequest:
    GET: dict[str, str]
    COOKIES: dict[str, str]


@dataclass
class MockApp:
    langs: list[str]
    is_remote_app: bool = False

    def save(self):
        pass


class TestGetLangsLang:
    """Tests for the first return value of ``get_langs()``"""

    def test_get_param(self):
        request = MockRequest(
            GET={'lang': 'tlh'},  # User's first choice
            COOKIES={'lang': 'que'},
        )
        app = MockApp(langs=['ido', 'epo', 'tlh', 'que'])
        lang, __ = get_langs(request, app)
        assert lang == 'tlh'

    def test_cookie(self):
        request = MockRequest(
            GET={},
            COOKIES={'lang': 'que'},  # User's second choice
        )
        app = MockApp(langs=['ido', 'epo', 'tlh', 'que'])
        lang, __ = get_langs(request, app)
        assert lang == 'que'

    def test_app_lang(self):
        request = MockRequest(GET={}, COOKIES={})
        app = MockApp(langs=['ido', 'epo', 'tlh', 'que'])
        lang, __ = get_langs(request, app)
        assert lang == 'ido'  # Fall back to app's first language

    def test_missing_choice(self):
        request = MockRequest(
            GET={'lang': 'tlh'},
            COOKIES={'lang': 'que'},
        )
        app = MockApp(langs=['ido', 'epo', 'que'])  # First choice not available
        lang, __ = get_langs(request, app)
        assert lang == 'ido'  # App's first language, not user's second choice

    def test_langs_empty(self):
        request = MockRequest(GET={}, COOKIES={})
        app = MockApp(langs=[])
        lang, __ = get_langs(request, app)
        assert lang == 'en'  # app.langs falls back to ['en']

    def test_lang_langs_empty(self):
        request = MockRequest(GET={'lang': 'tlh'}, COOKIES={})
        app = MockApp(langs=[])
        lang, __ = get_langs(request, app)
        assert lang == 'en'

    def test_langs_empty_remote(self):
        request = MockRequest(GET={}, COOKIES={})
        app = MockApp(langs=[], is_remote_app=True)
        lang, __ = get_langs(request, app)
        assert lang == 'en'  # lang falls back to 'en'

    def test_no_app(self):
        request = MockRequest(GET={}, COOKIES={})
        lang, __ = get_langs(request, None)
        assert lang == ''  # Empty string default falls through

    def test_lang_no_app(self):
        request = MockRequest(GET={'lang': 'tlh'}, COOKIES={})
        lang, __ = get_langs(request, None)
        assert lang == 'tlh'  # User's choice falls through


class TestGetLangsLangs:
    """Tests for the second return value of ``get_langs()``"""

    def test_no_app(self):
        request = MockRequest(GET={'lang': 'tlh'}, COOKIES={})
        __, langs = get_langs(request, None)
        assert langs is None

    def test_langs_empty(self):
        request = MockRequest(GET={'lang': 'tlh'}, COOKIES={})
        app = MockApp(langs=[])
        __, langs = get_langs(request, app)
        assert langs == ['en', 'en']

    def test_langs_empty_remote(self):
        request = MockRequest(GET={'lang': 'tlh'}, COOKIES={})
        app = MockApp(langs=[], is_remote_app=True)
        __, langs = get_langs(request, app)
        assert langs == ['en']

    def test_lang_not_in_app_langs(self):
        request = MockRequest(GET={'lang': 'tlh'}, COOKIES={})
        app = MockApp(langs=['ido', 'epo'])
        __, langs = get_langs(request, app)
        assert langs == ['ido', 'ido', 'epo']  # Use first app language

    def test_lang_in_app_langs(self):
        request = MockRequest(GET={'lang': 'tlh'}, COOKIES={})
        app = MockApp(langs=['ido', 'epo', 'tlh'])
        __, langs = get_langs(request, app)
        assert langs == ['tlh', 'ido', 'epo', 'tlh']
