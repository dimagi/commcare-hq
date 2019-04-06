from __future__ import absolute_import
from __future__ import unicode_literals
from distutils.version import StrictVersion
from django.test import SimpleTestCase
from io import BytesIO
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.ui_translations import \
    process_ui_translation_upload, get_default_translations_for_download
from couchexport.export import export_raw
import six


class BulkUiTranslation(SimpleTestCase):

    def setUp(self):
        super(BulkUiTranslation, self).setUp()
        self.app = Application.new_app("test-domain", "Test App")
        self.app.langs = ["en", "fra"]

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

    def test_no_change(self):
        headers = (('translations', ('property', 'en')),)
        f = self._build_translation_download_file(headers)

        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        self.assertEqual(dict(translations), {})
        self.assertEqual(len(error_properties), 0)

    def test_translation(self):
        headers = (('translations', ('property', 'en', 'fra')),)
        # on an update to 2.31.0, the keys date.tomorrow, entity.sort.title,
        # activity.locationcapture.Longitude were no longer present in messages_en-2.txt
        # They were replaced by other randomly selected strings in that file.
        # Leaving this note here in case this issue comes up again. --B
        data = (('key.manage.title', 'wobble', ''),
                ('bulk.send.dialog.progress', 'wabble', ''),
                ('connection.test.access.settings', '', 'wibble'),
                ('bulk.send.dialog.progress', '', 'wubble'),
                ('home.start.demo', 'Ding', 'Dong'),
                ('unknown_string', 'Ding', 'Dong'))

        f = self._build_translation_download_file(headers, data)
        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)

        self.assertEqual(
            dict(translations),
            {
                'en': {
                    'key.manage.title': 'wobble',
                    'bulk.send.dialog.progress': 'wabble',
                    'home.start.demo': 'Ding',
                    'unknown_string': 'Ding',
                },
                'fra': {
                    'connection.test.access.settings': 'wibble',
                    'bulk.send.dialog.progress': 'wubble',
                    'home.start.demo': 'Dong',
                    'unknown_string': 'Dong',
                }
            }

        )
        self.assertEqual(len(error_properties), 0)
        # There should be a warning that 'unknown_string' is not a CommCare string
        self.assertEqual(len(warnings), 1, warnings)

        # test existing translations get updated correctly
        data = (('home.start.demo', 'change_1', 'change_2'))
        f = self._build_translation_download_file(headers, data)
        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        self.assertEqual(translations["fra"]["home.start.demo"], "change_2")
        self.assertEqual(translations["en"]["home.start.demo"], "change_1")
