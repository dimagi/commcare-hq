from django.test import SimpleTestCase
from StringIO import StringIO
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.views.translations import process_ui_translation_upload,\
    get_default_translations_for_download
from couchexport.export import export_raw


class BulkUiTranslation(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = Application.new_app("test-domain", "Test App")
        cls.app.langs = ["en", "fra"]

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

        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        self.assertEqual(
            dict(translations), dict()
        )
        self.assertTrue(len(error_properties) == 0)

    def test_translation(self):
        headers = (('translations', ('property', 'en', 'fra')),)
        data = (('date.tomorrow', 'wobble', ''),
                ('entity.sort.title', 'wabble', ''),
                ('activity.locationcapture.Longitude', '', 'wibble'),
                ('entity.sort.title', '', 'wubble'),
                ('home.start.demo', 'Ding', 'Dong'),
                ('unknown_string', 'Ding', 'Dong'))

        f = self._build_translation_download_file(headers, data)
        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)

        self.assertEqual(
            dict(translations),
            {
                u'en': {
                    u'date.tomorrow': u'wobble',
                    u'entity.sort.title': u'wabble',
                    u'home.start.demo': u'Ding',
                    u'unknown_string': u'Ding',
                },
                u'fra': {
                    u'activity.locationcapture.Longitude': u'wibble',
                    u'entity.sort.title': u'wubble',
                    u'home.start.demo': u'Dong',
                    u'unknown_string': u'Dong',
                }
            }

        )
        self.assertEqual(len(error_properties), 0)
        # There should be a warning that 'unknown_string' is not a CommCare string
        self.assertEqual(len(warnings), 1)

        # test existing translations get updated correctly
        data = (('home.start.demo', 'change_1', 'change_2'))
        f = self._build_translation_download_file(headers, data)
        translations, error_properties, warnings = process_ui_translation_upload(self.app, f)
        self.assertEqual(translations[u"fra"][u"home.start.demo"], u"change_2")
        self.assertEqual(translations[u"en"][u"home.start.demo"], u"change_1")
