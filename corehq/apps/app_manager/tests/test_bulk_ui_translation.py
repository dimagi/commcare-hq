import codecs
from django.test import SimpleTestCase
import os
from StringIO import StringIO
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.views.translations import process_ui_translation_upload,\
    get_default_translations_for_download
from couchexport.export import export_raw


class BulkUiTranslation(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = Application.new_app("test-domain", "Test App", application_version=APP_V2)
        cls.app.langs = ["en", "fra"]
        cls.app.build_langs = ["en", "fra"]

    def _build_translation_download_file(self, headers, data=None):
        if data is None:
            data = []
            translations = get_default_translations_for_download(self.app)
            for translation_key, translation_value in translations.iteritems():
                data.append((translation_key, translation_value))

        data = (('translations', tuple(data)),)
        temp = StringIO()
        export_raw(headers, data, temp)
        temp.seek(0)            # .read() is used somewhere so this needs to be at the begininng
        return temp

    def test_no_change(self):
        headers = (('translations', ('property', 'en')),)
        f = self._build_translation_download_file(headers)

        translations, error_properties = process_ui_translation_upload(self.app, f)
        self.assertEqual(
            dict(translations), dict()
        )
        self.assertTrue(len(error_properties) == 0)

    def test_translation(self):
        headers = (('translations', ('property', 'en', 'fra')),)
        data = (('date.tomorrow', 'wobble', ''),
                ('entity.sort.title', 'wabble', ''),
                ('activity.locationcapture.Longitude', '', 'wibble'),
                ('entity.sort.title', '', 'wubble'))

        f = self._build_translation_download_file(headers, data)

        translations, error_properties = process_ui_translation_upload(self.app, f)

        self.assertEqual(
            dict(translations),
            {
                u'en': {
                    u'date.tomorrow': u'wobble',
                    u'entity.sort.title': u'wabble'
                },
                u'fra': {
                    u'activity.locationcapture.Longitude': u'wibble',
                    u'entity.sort.title': u'wubble'}
            }

        )
        self.assertTrue(len(error_properties) == 0)
