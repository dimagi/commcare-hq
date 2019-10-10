from distutils.version import StrictVersion
from io import BytesIO

from django.test import SimpleTestCase

from couchexport.export import export_raw

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.ui_translations import (
    get_default_translations_for_download,
    process_ui_translation_upload,
)


class BulkUiTranslation(SimpleTestCase):

    def setUp(self):
        super(BulkUiTranslation, self).setUp()
        self.app = Application.new_app("test-domain", "Test App")
        self.app.langs = ["en", "fra"]

    def _build_translation_download_file(self, headers, data=None):
        if data is None:
            data = []
            translations = get_default_translations_for_download(self.app, 'latest')
            for translation_key, translation_value in translations.items():
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
                ('bulk.send.dialog.progress', 'wabble ${0}', ''),
                ('connection.test.access.settings', '', 'wibble'),
                ('bulk.send.dialog.progress', '', 'wubble ${0}'),
                ('home.start.demo', 'Ding', 'Dong'),
                ('unknown_string', 'Ding', 'Dong'),
                ('updates.found', 'I am missing a parameter', 'I have ${0} an ${1} extra ${2} parameter'),
                ('sync.progress', 'It is fine to ${1} reorder ${0} params', 'But use ${x0} correct syntax $ {1}'))

        f = self._build_translation_download_file(headers, data)
        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)

        self.assertEqual(
            dict(translations),
            {
                'en': {
                    'key.manage.title': 'wobble',
                    'bulk.send.dialog.progress': 'wabble ${0}',
                    'home.start.demo': 'Ding',
                    'unknown_string': 'Ding',
                    'updates.found': 'I am missing a parameter',
                    'sync.progress': 'It is fine to ${1} reorder ${0} params',
                },
                'fra': {
                    'connection.test.access.settings': 'wibble',
                    'bulk.send.dialog.progress': 'wubble ${0}',
                    'home.start.demo': 'Dong',
                    'unknown_string': 'Dong',
                    'updates.found': 'I have ${0} an ${1} extra ${2} parameter',
                    'sync.progress': 'But use ${x0} correct syntax $ {1}',
                }
            }

        )
        self.assertEqual(len(error_properties), 2)
        self.assertEqual([e.strip() for e in error_properties], [
            "Could not understand '${x0}' in fra value of sync.progress.",
            "Could not understand '$ {1}' in fra value of sync.progress.",
        ])
        self.assertEqual(len(warnings), 3)
        self.assertEqual([e.strip() for e in warnings], [
            "unknown_string is not a known CommCare UI string, but we added it anyway",
            "Property updates.found should contain ${0}, ${1} but en value contains no parameters.",
            "Property updates.found should contain ${0}, ${1} but fra value contains ${0}, ${1}, ${2}.",
        ])

        # test existing translations get updated correctly
        data = (('home.start.demo', 'change_1', 'change_2'))
        f = self._build_translation_download_file(headers, data)
        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        self.assertEqual(translations["fra"]["home.start.demo"], "change_2")
        self.assertEqual(translations["en"]["home.start.demo"], "change_1")
