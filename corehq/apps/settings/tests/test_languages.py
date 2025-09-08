from unittest.mock import patch

from django.test import TestCase, override_settings

from corehq.apps.domain.models import Domain
from corehq.apps.es.apps import app_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.settings.languages import get_languages_for_user
from corehq.apps.users.models import WebUser


@override_settings(
    LANGUAGES=[
        ('en', 'English'),
        ('es', 'Spanish'),
        ('fra', 'French')
    ]
)
@es_test(requires=[app_adapter])
class GetLanguagesForUserTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = Domain.get_or_create_with_name('test-langs', is_active=True)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = WebUser.create(cls.domain_obj.name, 'lang-user', 'abc123', None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain_obj.name, None)

    def test_no_domain_translations(self):
        langs = get_languages_for_user(self.user)
        assert langs == [
            ('en', 'en (English)'),
            ('es', 'es (Spanish)'),
            ('fra', 'fra (French)'),
        ]

    def test_with_overlapping_domain_translations(self):
        with patch('corehq.apps.settings.languages.get_domain_languages', return_value=[('es', 'es (Espanol)')]):
            langs = get_languages_for_user(self.user)
            assert langs == [
                ('en', 'en (English)'),
                ('es', 'es (Spanish)'),  # uses name specified in settings.LANGUAGES, not domain
                ('fra', 'fra (French)'),
            ]

    def test_with_unique_domain_translations(self):
        with patch('corehq.apps.settings.languages.get_domain_languages', return_value=[('hin', 'hin (Hindi)')]):
            langs = get_languages_for_user(self.user)
            assert langs == [
                ('en', 'en (English)'),
                ('es', 'es (Spanish)'),
                ('fra', 'fra (French)'),
                ('hin', 'hin (Hindi)'),
            ]
