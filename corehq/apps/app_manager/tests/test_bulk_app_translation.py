import codecs
import tempfile

from django.test import SimpleTestCase
from StringIO import StringIO
from corehq.util.spreadsheets.excel import WorkbookJSONReader

from couchexport.export import export_raw
from couchexport.models import Format
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.app_manager.translations import \
    process_bulk_app_translation_upload, expected_bulk_app_sheet_rows, \
    expected_bulk_app_sheet_headers


class BulkAppTranslationTestBase(SimpleTestCase, TestFileMixin):

    def setUp(self):
        """
        Instantiate an app from file_path + app.json
        """
        super(BulkAppTranslationTestBase, self).setUp()
        self.app = Application.wrap(self.get_json("app"))

    def upload_raw_excel_translations(self, excel_headers, excel_data, expected_messages=None):
        """
        Prepares bulk app translation excel file and uploads it

        Structure of the xlsx file can be specified as following

        excel_headers:
         (("employee", ("id", "name", "gender")),
          ("building", ("id", "name", "address")))

        excel_data:
         (("employee", (("1", "cory", "m"),
                        ("2", "christian", "m"),
                        ("3", "amelia", "f"))),
          ("building", (("1", "dimagi", "585 mass ave."),
                        ("2", "old dimagi", "529 main st."))))
        """
        if not expected_messages:
            expected_messages = ["App Translations Updated!"]

        file = StringIO()
        export_raw(excel_headers, excel_data, file, format=Format.XLS_2007)

        with tempfile.TemporaryFile(suffix='.xlsx') as f:
            f.write(file.getvalue())
            messages = process_bulk_app_translation_upload(self.app, f)

        self.assertListEqual(
            [m[1] for m in messages], expected_messages
        )

    def do_upload(self, name, expected_messages=None):
        """
        Upload the bulk app translation file at file_path + upload.xlsx

        Note: Use upload_raw_excel_translations() instead. It allows easy modifications
        and diffs of xlsx data.

        ToDo: Refactor tests using do_upload to use upload_raw_excel_translations(), use
        WorkbookJSONReader.work_book_headers_as_tuples(), and
        WorkbookJSONReader.work_book_data_as_tuples(), for making tuples from excel files
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

    upload_headers = (
        ("Modules_and_forms", (
            "Type", "sheet_name", "default_en", "default_fra", "label_for_cases_en", "label_for_cases_fra", 'icon_filepath_en', 'icon_filepath_fra', 'audio_filepath_en', 'audio_filepath_fra', "unique_id"
        )),
        ("module1", (
            "case_property", "list_or_detail", "default_en", "default_fra"
        )),
        ("module1_form1", (
            "label", "default_en", "default_fra", "audio_en", "audio_fra", "image_en", "image_fra", "video_en", "video_fra",
        ))
    )

    upload_headers_bad_column = (  # bad column is default-fra
        ("Modules_and_forms", (
            "Type", "sheet_name", "default_en", "default_fra",
            "label_for_cases_en", "label_for_cases_fra", "icon_filepath_en", "icon_filepath_fra",
            "audio_filepath_en", "audio_filepath_fra" , "unique_id"
        )),
        ("module1", (
            "case_property", "list_or_detail", "default_en", "default_fra"
        )),
        ("module1_form1", (
            "label", "default_en", "default-fra", "audio_en", "audio_fra",
            "image_en", "image_fra", "video_en", "video_fra",
        ))
    )

    upload_data = (
        ("Modules_and_forms", (
          ("Module", "module1", "My & awesome module", "", "Cases", "Cases", "", "", "", "", "8f4f7085a93506cba4295eab9beae8723c0cee2a"),
          ("Form", "module1_form1", "My more & awesome form", "", "", "", "", "", "", "", "93ea2a40df57d8f33b472f5b2b023882281722d4")
        )),
        ("module1", (
          ("name", "list", "Name", "Nom"),
          ("name", "detail", "", "Nom"),
          ("other-prop (ID Mapping Text)", "detail", "Other Prop", ""),
          ("foo (ID Mapping Value)", "detail", "bar", "french bar"),
          ("baz (ID Mapping Value)", "detail", "quz", ""),
        )),
        ("module1_form1", (
          ("question1-label", "in english", "it's in french", "", "", "", "", "", ""),
          ("question2-label", "one &lt; two", "un &lt; deux", "", "", "", "", "", ""),
          ("question2-item1-label", "item1", "item1", "", "", "", "", "", ""),
          ("question2-item2-label", "item2", "item2", "", "", "", "", "", ""),
          ("question3-label", "question3", "question3&#39;s label", "", "", "", "", "", ""),
          ("question3/question4-label", 'question6: <output value="/data/question6"/>', 'question6: <output value="/data/question6"/>', "", "", "", "", "", ""),
          ("question3/question5-label", "English Label", "English Label", "", "", "", "", "", ""),
          ("question7-label", 'question1: <output value="/data/question1"/> &lt; 5', "question7", "", "", "", "", "", "")
        ))
    )

    upload_no_change_headers = (
        ('Modules_and_forms', ('Type', 'sheet_name', 'default_en', 'default_fra', 'label_for_cases_en', 'label_for_cases_fra', 'icon_filepath_en', 'icon_filepath_fra', 'audio_filepath_en', 'audio_filepath_fra', 'unique_id')),
        ('module1', ('case_property', 'list_or_detail', 'default_en', 'default_fra')),
        ('module1_form1', ('label', 'default_en', 'default_fra', 'audio_en', 'audio_fra', 'image_en', 'image_fra', 'video_en', 'video_fra'))
    )

    upload_no_change_data = (
        ('Modules_and_forms',
         (('Module', 'module1', 'My & awesome module', '', 'Cases', 'Cases', '', '', '', '', '8f4f7085a93506cba4295eab9beae8723c0cee2a'),
          ('Form', 'module1_form1', 'My more & awesome form', '', '', '', '', '', '', '', '93ea2a40df57d8f33b472f5b2b023882281722d4'))),
        ('module1',
         (('name', 'list', 'Name', ''),
          ('name', 'detail', 'Name', ''),
          ('other-prop (ID Mapping Text)', 'detail', 'Other Prop', 'Autre Prop'),
          ('foo (ID Mapping Value)', 'detail', 'bar', ''),
          ('baz (ID Mapping Value)', 'detail', 'quz', ''))),
        ('module1_form1',
         (('question1-label', 'question1', 'question1', '', '', '', '', '', ''),
          ('question2-label', 'question2', 'question2', '', '', '', '', '', ''),
          ('question2-item1-label', 'item1', 'item1', '', '', '', '', '', ''),
          ('question2-item2-label', 'item2', 'item2', '', '', '', '', '', ''),
          ('question3-label', 'question3', 'question3', '', '', '', '', '', ''),
          ('question3/question4-label', 'question4', 'question4', '', '', '', '', '', ''),
          ('question3/question5-label', 'question5', 'question5', '', '', '', '', '', ''),
          ('question7-label', 'question7', 'question7', '', '', '', '', '', '')))
     )
    def test_set_up(self):
        self._shared_test_initial_set_up()

    def test_no_change_upload(self):
        self.upload_raw_excel_translations(self.upload_no_change_headers, self.upload_no_change_data)
        self._shared_test_initial_set_up()

    def _shared_test_initial_set_up(self):
        self.assert_question_label("question1", 0, 0, "en", "/data/question1")
        self.assert_case_property_label("Autre Prop", "other-prop", 0, "long", "fra")

    def test_change_upload(self):
        self.upload_raw_excel_translations(self.upload_headers, self.upload_data)

        self.assert_question_label("in english", 0, 0, "en", "/data/question1")
        self.assert_question_label("it's in french", 0, 0, "fra", "/data/question1")

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

        # Test special characters and output refs
        self.assert_question_label("one < two", 0, 0, "en", "/data/question2")
        self.assert_question_label("un < deux", 0, 0, "fra", "/data/question2")
        self.assert_question_label("question3's label", 0, 0, "fra", "/data/question3")
        self.assert_question_label("question6: ____", 0, 0, "en", "/data/question3/question4")
        self.assert_question_label("question1: ____ < 5", 0, 0, "en", "/data/question7")

    def test_missing_itext(self):
        self.app = Application.wrap(self.get_json("app_no_itext"))
        self.assert_question_label('question1', 0, 0, "en", "/data/question1")
        try:
            self.upload_raw_excel_translations(self.upload_no_change_headers, self.upload_no_change_data)
        except Exception as e:
            self.fail(e)

    def test_bad_column_name(self):
        self.upload_raw_excel_translations(self.upload_headers_bad_column,
            self.upload_data,
            expected_messages=[
                u'Sheet "module1_form1" has less columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra',
                u'Sheet "module1_form1" has unrecognized columns. Sheet will '
                'be processed but ignoring the following columns: default-fra',
                u'App Translations Updated!'
            ]
        )



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

    excel_headers = (
        ('Modules_and_forms', ('Type', 'sheet_name', 'default_en', 'label_for_cases_en', 'icon_filepath_en', 'audio_filepath_en', 'unique_id')),
        ('module1', ('case_property', 'list_or_detail', 'default_en')),
        ('module1_form1', ('label', 'default_en', 'audio_en', 'image_en', 'video_en'))
    )

    excel_data = (
        ('Modules_and_forms',
         (('Module', 'module1', 'Stethoscope', 'Cases', 'jr://file/commcare/image/module0.png', '', '58ce5c9cf6eda401526973773ef216e7980bc6cc'),
          ('Form',
           'module1_form1',
           'Stethoscope Form',
           '',
           'jr://file/commcare/image/module0_form0.png',
           '',
           'c480ace490edc870ae952765e8dfacec33c69fec'))),
        ('module1', (('name', 'list', 'Name'), ('name', 'detail', 'Name'))),
        ('module1_form1',
         (('What_does_this_look_like-label', 'What does this look like?', '', 'jr://file/commcare/image/data/What_does_this_look_like.png', ''),
          ('no_media-label', 'No media', '', '', ''),
          ('has_refs-label', 'Here is a ref <output value="/data/no_media"/> with some trailing text and bad &lt; xml.', '', '', '')))
    )


    @classmethod
    def setUpClass(cls):
        cls.app = Application.wrap(cls.get_json("app"))
        # Todo, refactor this into BulkAppTranslationTestBase.upload_raw_excel_translations
        file = StringIO()
        export_raw(cls.excel_headers, cls.excel_data, file, format=Format.XLS_2007)

        with tempfile.TemporaryFile(suffix='.xlsx') as f:
            f.write(file.getvalue())
            wb_reader = WorkbookJSONReader(f)
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
