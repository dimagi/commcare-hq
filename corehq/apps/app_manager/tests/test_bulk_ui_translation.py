import codecs
from django.test import SimpleTestCase
import os
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.views.translations import process_ui_translation_upload


class BulkUiTranslation(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = Application.new_app("test-domain", "Test App", application_version=APP_V2)
        cls.app.langs = ["en", "fra"]
        cls.app.build_langs = ["en", "fra"]

    def test_no_change(self):

        with codecs.open(os.path.join(
                os.path.dirname(__file__), "data",
                "bulk_ui_translations_no_change.xlsx")) as f:
            translations, error_properties = process_ui_translation_upload(self.app, f)

        self.assertEqual(
            dict(translations), dict()
        )
        self.assertTrue(len(error_properties) == 0)

    def test_translation(self):
        with codecs.open(os.path.join(
                os.path.dirname(__file__), "data",
                "bulk_ui_translations.xlsx")) as f:
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
