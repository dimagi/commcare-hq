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
from couchexport.export import export_raw

EXPECTED_TRANSLATIONS = {
    'en': {
        'key.manage.title': 'Taylor',
        'bulk.send.dialog.progress': 'Kanye',
        'specific.item.to.translate': 'Miley',
    },
    'fra': {
        'key.manage.title': 'Swift',
        'bulk.send.dialog.progress': 'West',
        'specific.item.to.translate': 'Cyrus',
    }
}


class TestBulkUiTranslation(SimpleTestCase):

    def setUp(self):
        super(TestBulkUiTranslation, self).setUp()
        self.app = Application.new_app("test-domain", "Test App")
        self.app.langs = ["en", "fra"]
        self.app.translations = EXPECTED_TRANSLATIONS

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
        data = (('key.manage.title', 'Taylor', 'Swift'),)
        f = self._build_translation_download_file(headers, data)

        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        update_app_translations_from_trans_dict(self.app, translations)

        self.assertDictEqual(self.app.translations, EXPECTED_TRANSLATIONS)

    def test_not_upload_all_languages(self):
        headers = (('translations', ('property', 'en')),)
        data = (
            ('key.manage.title', 'Taylor'),
            ('bulk.send.dialog.progress', 'Kanye'),
            ('specific.item.to.translate', 'Miley'),
        )
        f = self._build_translation_download_file(headers, data)

        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        update_app_translations_from_trans_dict(self.app, translations)
        self.assertDictEqual(self.app.translations, EXPECTED_TRANSLATIONS)

    def test_partial_property_and_language(self):
        headers = (('translations', ('property', 'en')),)
        data = (('key.manage.title', 'Taylor'),)
        f = self._build_translation_download_file(headers, data)

        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        update_app_translations_from_trans_dict(self.app, translations)

        self.assertDictEqual(self.app.translations, EXPECTED_TRANSLATIONS)
