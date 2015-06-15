import codecs

from django.test import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.app_manager.translations import \
    process_bulk_app_translation_upload, expected_bulk_app_sheet_rows, \
    expected_bulk_app_sheet_headers
from dimagi.utils.excel import WorkbookJSONReader


class BulkAppTranslationTestBase(SimpleTestCase, TestFileMixin):

    def setUp(self):
        """
        Instantiate an app from file_path + app.json
        """
        super(BulkAppTranslationTestBase, self).setUp()
        self.app = Application.wrap(self.get_json("app"))

    def do_upload(self, name, expected_messages=None):
        """
        Upload the bulk app translation file at file_path + upload.xlsx
        """
        if not expected_messages:
            expected_messages = ["App Translations Updated!"]

        with codecs.open(self.get_path(name, "xlsx")) as f:
            messages = process_bulk_app_translation_upload(self.app, f)

        self.assertListEqual(
            [m[1] for m in messages], expected_messages
        )

    def assert_question_label(self, text, module_id, form_id, language, question_path):
        """
        assert that the given text is equal to the label of the given question.
        Return the label of the given question
        :param text:
        :param module_id: module index
        :param form_id: form index
        :param question_path: path to question (including "/data/")
        :return: the label of the question
        """
        form = self.app.get_module(module_id).get_form(form_id)
        labels = {}
        for lang in self.app.langs:
            for question in form.get_questions(
                    [lang], include_triggers=True, include_groups=True):
                labels[(question['value'], lang)] = question['label']

        self.assertEqual(
            labels[(question_path, language)],
            text
        )

    def assert_case_property_label(self, text, field, module_id, short_or_long, language):
        module = self.app.get_module(module_id)
        cols = module.case_details[short_or_long].columns
        col = next(col for col in cols if col.field == field)
        self.assertEqual(text, col.header.get(language, None))


class BulkAppTranslationBasicTest(BulkAppTranslationTestBase):

    file_path = "data", "bulk_app_translation", "basic"

    def test_set_up(self):
        self._shared_test_initial_set_up()

    def test_no_change_upload(self):
        self.do_upload("upload_no_change")
        self._shared_test_initial_set_up()

    def _shared_test_initial_set_up(self):
        self.assert_question_label("question1", 0, 0, "en", "/data/question1")
        self.assert_case_property_label("Autre Prop", "other-prop", 0, "long", "fra")

    def test_change_upload(self):
        self.do_upload("upload")

        self.assert_question_label("in english", 0, 0, "en", "/data/question1")
        self.assert_question_label("in french", 0, 0, "fra", "/data/question1")

        # Test that translations can be deleted.
        self.assert_question_label("English Label", 0, 0, "fra", "/data/question3/question5")
        self.assert_case_property_label(None, "other-prop", 0, "long", "fra")
        self.assert_case_property_label(None, "name", 0, "long", "en")

        module = self.app.get_module(0)
        self.assertEqual(
            module.case_details.long.columns[1].enum[0].value['fra'],
            'french bar'
        )
        self.assertEqual(
            module.case_details.short.columns[0].header['fra'],
            'Nom'
        )

    def test_missing_itext(self):
        self.app = Application.wrap(self.get_json("app_no_itext"))
        self.assert_question_label('question1', 0, 0, "en", "/data/question1")
        try:
            self.do_upload("upload_no_change")
        except Exception as e:
            self.fail(e)


class MismatchedItextReferenceTest(BulkAppTranslationTestBase):
    """
    Test the bulk app translation upload when the itext reference in a question
    in the xform body does not match the question's id/path.

    The upload is an unchanged download.
    """
    file_path = "data", "bulk_app_translation", "mismatched_ref"

    def test_unchanged_upload(self):
        self.do_upload("upload")
        self.assert_question_label("question2", 0, 0, "en", "/data/foo/question2")


class BulkAppTranslationFormTest(BulkAppTranslationTestBase):

    file_path = "data", "bulk_app_translation", "form_modifications"

    def test_removing_form_translations(self):
        self.do_upload("modifications")
        form = self.app.get_module(0).get_form(0)
        self.assertXmlEqual(self.get_xml("expected_form"), form.render_xform())


class BulkAppTranslationDownloadTest(SimpleTestCase, TestFileMixin):

    file_path = ('data', 'bulk_app_translation', 'download')
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.app = Application.wrap(cls.get_json("app"))
        wb_reader = WorkbookJSONReader(cls.get_path('bulk_app_translations', 'xlsx'))
        cls.expected_workbook = [{'name': ws.title, 'rows': list(ws)}
                                 for ws in wb_reader.worksheets]

    def test_download(self):
        actual_headers = expected_bulk_app_sheet_headers(self.app)
        actual_rows = expected_bulk_app_sheet_rows(self.app)

        actual_workbook = [
            {'name': title,
             'rows': [dict(zip(headers, row)) for row in actual_rows[title]]}
            for title, headers in actual_headers
        ]

        for actual_sheet, expected_sheet in zip(actual_workbook,
                                                self.expected_workbook):
            self.assertEqual(actual_sheet, expected_sheet)
        self.assertEqual(actual_workbook, self.expected_workbook)


class RenameLangTest(SimpleTestCase):

    def test_rename_lang_empty_form(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        module = app.add_module(Module.new_module('module', None))
        form1 = app.new_form(module.id, "Untitled Form", None)
        form1.source = '<source>'

        # form with no source
        form2 = app.new_form(module.id, "Empty form", None)

        app.rename_lang('en', 'fra')

        self.assertNotIn('en', module.name)
        self.assertIn('fra', module.name)

        self.assertNotIn('en', form1.name)
        self.assertIn('fra', form1.name)

        self.assertNotIn('en', form2.name)
        self.assertIn('fra', form2.name)
