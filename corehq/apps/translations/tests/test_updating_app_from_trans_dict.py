from __future__ import absolute_import
from __future__ import unicode_literals

from io import BytesIO

import six
from django.test import SimpleTestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.ui_translations import (
    get_default_translations_for_download,
    process_ui_translation_upload,
)
from corehq.apps.translations.utils import update_app_translations_from_trans_dict
from corehq.util.test_utils import flag_enabled
from couchexport.export import export_raw

INITIAL_TRANSLATIONS = {
    'en': {
        'translation.always.upload': 'Taylor',
        'translation.sometimes.upload': 'Kanye',
    },
    'fra': {
        'translation.always.upload': 'Swift',
        'translation.sometimes.upload': 'West',
    }
}
EXPECTED_TRANSLATIONS = {
    'en': {
        'translation.always.upload': 'Miley',
        'translation.sometimes.upload': 'Kanye',
    },
    'fra': {
        'translation.always.upload': 'Cyrus',
        'translation.sometimes.upload': 'West',
    }
}


class TestBulkUiTranslation(SimpleTestCase):

    def setUp(self):
        super(TestBulkUiTranslation, self).setUp()
        self.app = Application.new_app("test-domain", "Test App")
        self.app.langs = ["en", "fra"]
        self.app.translations = INITIAL_TRANSLATIONS

    def _build_translation_download_file(self, headers, data=None):
        if data is None:
            data = []
            translations = get_default_translations_for_download(self.app, 'latest')
            for translation_key, translation_value in six.iteritems(translations):
                data.append((translation_key, translation_value))

        data = (('translations', tuple(data)),)
        temp = BytesIO()
        export_raw(headers, data, temp)
        temp.seek(0)            # .read() is used somewhere so this needs to be at the begininng
        return temp

    def test_not_upload_all_properties(self):
        headers = (('translations', ('property', 'en', 'fra')),)
        data = (('translation.always.upload', 'Miley', 'Cyrus'),)
        f = self._build_translation_download_file(headers, data)

        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        update_app_translations_from_trans_dict(self.app, translations)

        self.assertDictEqual(self.app.translations['en'], {'translation.always.upload': 'Miley'})
        self.assertDictEqual(self.app.translations['fra'], {'translation.always.upload': 'Cyrus'})

    @flag_enabled('PARTIAL_UI_TRANSLATIONS')
    def test_not_upload_all_properties_with_parital_ui_translations(self):
        headers = (('translations', ('property', 'en', 'fra')),)
        data = (('translation.always.upload', 'Miley', 'Cyrus'),)
        f = self._build_translation_download_file(headers, data)

        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        update_app_translations_from_trans_dict(self.app, translations)

        self.assertDictEqual(self.app.translations, EXPECTED_TRANSLATIONS)

    def test_not_upload_all_languages(self):
        headers = (('translations', ('property', 'en')),)
        data = (
            ('translation.always.upload', 'Miley'),
            ('translation.sometimes.upload', 'Kanye'),
        )
        f = self._build_translation_download_file(headers, data)

        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        update_app_translations_from_trans_dict(self.app, translations)
        self.assertDictEqual(self.app.translations['en'], EXPECTED_TRANSLATIONS['en'])
        self.assertDictEqual(self.app.translations['fra'], INITIAL_TRANSLATIONS['fra'])

    def test_partial_property_and_language(self):
        headers = (('translations', ('property', 'en')),)
        data = (('translation.always.upload', 'Miley'),)
        f = self._build_translation_download_file(headers, data)

        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        update_app_translations_from_trans_dict(self.app, translations)

        self.assertDictEqual(self.app.translations['en'], {'translation.always.upload': 'Miley'})
        self.assertDictEqual(self.app.translations['fra'], INITIAL_TRANSLATIONS['fra'])

    @flag_enabled('PARTIAL_UI_TRANSLATIONS')
    def test_partial_property_and_language_with_partial_ui_translations(self):
        headers = (('translations', ('property', 'en')),)
        data = (('translation.always.upload', 'Miley'),)
        f = self._build_translation_download_file(headers, data)

        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        update_app_translations_from_trans_dict(self.app, translations)

        self.assertDictEqual(self.app.translations['en'], EXPECTED_TRANSLATIONS['en'])
        self.assertDictEqual(self.app.translations['fra'], INITIAL_TRANSLATIONS['fra'])
