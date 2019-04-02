# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import io
import tempfile
from io import BytesIO

from couchexport.export import export_raw
from couchexport.models import Format
from django.test import SimpleTestCase
from mock import patch
from six.moves import zip

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.translations.app_translations import (
    get_app_translation_workbook,
    get_bulk_app_sheet_headers,
    get_bulk_app_sheet_rows,
    get_bulk_multimedia_sheet_headers,
    get_bulk_multimedia_sheet_rows,
    get_form_question_rows,
    get_form_sheet_name,
    get_menu_row,
    get_module_case_list_form_rows,
    get_module_rows,
    get_module_sheet_name,
    get_modules_and_forms_row,
    get_unicode_dicts,
    process_bulk_app_translation_upload,
    update_form_translations,
    _remove_description_from_case_property
)
from corehq.apps.translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.util.test_utils import flag_enabled
from corehq.util.workbook_json.excel import WorkbookJSONReader


class BulkAppTranslationTestBase(SimpleTestCase, TestXmlMixin):

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

        file = BytesIO()
        export_raw(excel_headers, excel_data, file, format=Format.XLS_2007)

        with tempfile.TemporaryFile(suffix='.xlsx') as f:
            f.write(file.getvalue())
            f.seek(0)
            workbook, messages = get_app_translation_workbook(f)
            assert workbook, messages
            messages = process_bulk_app_translation_upload(self.app, workbook)

        self.assertListEqual(
            [m[1] for m in messages], expected_messages
        )

    def do_upload(self, name, expected_messages=None):
        """
        Upload the bulk app translation file at file_path + upload.xlsx

        Note: Use upload_raw_excel_translations() instead. It allows easy modifications
        and diffs of xlsx data.

        """
        if not expected_messages:
            expected_messages = ["App Translations Updated!"]
        with io.open(self.get_path(name, "xlsx"), 'rb') as f:
            workbook, messages = get_app_translation_workbook(f)
            assert workbook, messages
            messages = process_bulk_app_translation_upload(self.app, workbook)

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
        (MODULES_AND_FORMS_SHEET_NAME, (
            "Type", "sheet_name", "default_en", "default_fra", 'icon_filepath_en', 'icon_filepath_fra', 'audio_filepath_en', 'audio_filepath_fra', "unique_id"
        )),
        ("module1", (
            "case_property", "list_or_detail", "default_en", "default_fra"
        )),
        ("module1_form1", (
            "label", "default_en", "default_fra", "audio_en", "audio_fra", "image_en", "image_fra", "video_en", "video_fra",
        ))
    )

    upload_headers_bad_column = (  # bad column is default-fra
        (MODULES_AND_FORMS_SHEET_NAME, (
            "Type", "sheet_name", "default_en", "default-fra",
            "icon_filepath_en", "icon_filepath_fra", "audio_filepath_en", "audio_filepath_fra", "unique_id"
        )),
        ("module1", (
            "case_property", "list_or_detail", "default_en", "default-fra"
        )),
        ("module1_form1", (
            "label", "default_en", "default-fra", "audio_en", "audio_fra",
            "image_en", "image_fra", "video_en", "video_fra",
        ))
    )

    upload_data = (
        (MODULES_AND_FORMS_SHEET_NAME, (
          ("Module", "module1", "My & awesome module", "", "", "", "", "", "8f4f7085a93506cba4295eab9beae8723c0cee2a"),
          ("Form", "module1_form1", "My more & awesome form", "", "", "", "", "", "", "", "93ea2a40df57d8f33b472f5b2b023882281722d4")
        )),
        ("module1", (
          ("case_list_form_label", "list", "Register Mother", "Inscrivez-Mère"),
          ("name", "list", "Name", "Nom"),
          ("Tab 0", "detail", "Name", "Nom"),
          ("Tab 1", "detail", "Other", "Autre"),
          ("name", "detail", "", "Nom"),
          ("other-prop (ID Mapping Text)", "detail", "Other Prop", ""),
          ("foo (ID Mapping Value)", "detail", "bar", "french bar"),
          ("baz (ID Mapping Value)", "detail", "quz", ""),
          ("mood (ID Mapping Text)", "detail", "Mood", ""),
          (". < 3 (ID Mapping Value)", "detail", ":(", ":--("),
          (". >= 3 (ID Mapping Value)", "detail", ":)", ":--)"),
          ("energy (ID Mapping Text)", "detail", "Energy", ""),
          (". < 3 (ID Mapping Value)", "detail",
              "jr://file/commcare/image/module1_list_icon_energy_high_english.jpg",
              "jr://file/commcare/image/module1_list_icon_energy_high_french.jpg"),
          (". >= 3 (ID Mapping Value)", "detail",
              "jr://file/commcare/image/module1_list_icon_energy_low_english.jpg",
              "jr://file/commcare/image/module1_list_icon_energy_low_french.jpg"),
          ('line_graph (graph)', 'detail', 'Velocity', ''),
          ('x-title (graph config)', 'detail', 'Time', ''),
          ('y-title (graph config)', 'detail', 'Speed', ''),
          ('name 0 (graph series config)', 'detail', 'Bird', ''),
          ('name 1 (graph series config)', 'detail', 'Cheetah', ''),
        )),
        ("module1_form1", (
          ("question1-label", "in english", "it's in french", "", "", "", "", "", ""),
          ("question2-label", "one &lt; two", "un &lt; deux", "", "", "", "", "", ""),
          ("question2-item1-label", "item1", "item1", "", "", "", "", "", ""),
          ("question2-item2-label", "item2", "item2", "", "", "", "", "", ""),
          ("question3-label", "question3", "question3&#39;s label", "", "", "", "", "", ""),
          ("blank_value_node-label", "", "", "en-audio.mp3", "fra-audio.mp3", "", "", "", ""),
          ("question3/question4-label", 'question6: <output value="/data/question6"/>', 'question6: <output value="/data/question6"/>', "", "", "", "", "", ""),
          ("question3/question5-label", "English Label", "English Label", "", "", "", "", "", ""),
          ("question7-label", 'question1: <output value="/data/question1"/> &lt; 5', "question7", "", "", "", "", "", ""),
          ('add_markdown-label', 'add_markdown: ~~new \\u0939\\u093f markdown~~', 'add_markdown: ~~new \\u0939\\u093f markdown~~', '', '', '', '', '', ''),
          ('update_markdown-label', '## smaller_markdown', '## smaller_markdown', '', '', '', '', '', ''),
          ('vetoed_markdown-label', '*i just happen to like stars a lot*', '*i just happen to like stars a lot*', '', '', '', '', '', ''),
        ))
    )

    upload_no_change_headers = (
        (MODULES_AND_FORMS_SHEET_NAME, ('Type', 'sheet_name', 'default_en', 'default_fra',
                                        'icon_filepath_en', 'icon_filepath_fra', 'audio_filepath_en',
                                        'audio_filepath_fra', 'unique_id')),
        ('module1', ('case_property', 'list_or_detail', 'default_en', 'default_fra')),
        ('module1_form1', ('label', 'default_en', 'default_fra', 'audio_en', 'audio_fra', 'image_en', 'image_fra', 'video_en', 'video_fra'))
    )

    upload_no_change_data = (
        (MODULES_AND_FORMS_SHEET_NAME,
         (('Module', 'module1', 'My & awesome module', '', '', '', '', '', '8f4f7085a93506cba4295eab9beae8723c0cee2a'),
          ('Form', 'module1_form1', 'My more & awesome form', '', '', '', '', '', '', '', '93ea2a40df57d8f33b472f5b2b023882281722d4'))),
        ('module1',
         (('name', 'list', 'Name', ''),
          ('name', 'detail', 'Name', ''),
          ('other-prop (ID Mapping Text)', 'detail', 'Other Prop', 'Autre Prop'),
          ('foo (ID Mapping Value)', 'detail', 'bar', ''),
          ('baz (ID Mapping Value)', 'detail', 'quz', ''),
          ('mood (ID Mapping Text)', 'detail', 'Other Prop', ''),
          ('. < 3 (ID Mapping Value)', 'detail', ':(', ':-('),
          ('. >= 3 (ID Mapping Value)', 'detail', ':)', ':-)'),
          ('energy (ID Mapping Text)', 'detail', 'Other Prop', ''),
          ('. < 3 (ID Mapping Value)', 'detail',
              'jr://file/commcare/image/module1_list_icon_energy_high.jpg',
              'jr://file/commcare/image/module1_list_icon_energy_high_french.jpg'),
          ('. >= 3 (ID Mapping Value)', 'detail',
              'jr://file/commcare/image/module1_list_icon_energy_low.jpg',
              'jr://file/commcare/image/module1_list_icon_energy_low_french.jpg'),
          ('line_graph (graph)', 'detail', 'Velocity', ''),
          ('x-title (graph config)', 'detail', 'Time', ''),
          ('y-title (graph config)', 'detail', 'Speed', ''),
          ('name 0 (graph series config)', 'detail', 'Bird', ''),
          ('name 1 (graph series config)', 'detail', 'Cheetah', ''))),
        ('module1_form1',
         (('question1-label', 'question1', 'question1', '', '', '', '', '', ''),
          ('question2-label', 'question2', 'question2', '', '', '', '', '', ''),
          ('question2-item1-label', 'item1', 'item1', '', '', '', '', '', ''),
          ('question2-item2-label', 'item2', 'item2', '', '', '', '', '', ''),
          ('question3-label', 'question3', 'question3', '', '', '', '', '', ''),
          ('question3/question4-label', 'question4', 'question4', '', '', '', '', '', ''),
          ('question3/question5-label', 'question5', 'question5', '', '', '', '', '', ''),
          ('question7-label', 'question7', 'question7', '', '', '', '', '', ''),
          ('add_markdown-label', 'add_markdown', 'add_markdown', '', '', '', '', '', ''),
          ('update_markdown-label', '# update_markdown', '# update_markdown', '', '', '', '', '', ''),
          ('vetoed_markdown-label', '*i just happen to like stars*', '*i just happen to like stars*', '', '', '', '', '', ''),
        ))
    )

    upload_empty_translations = (
        (MODULES_AND_FORMS_SHEET_NAME,
         (('Module', 'module1', 'My & awesome module', '', '', '', '', '',
           '8f4f7085a93506cba4295eab9beae8723c0cee2a'),
          ('Form', 'module1_form1', '', '', '', '', '', '', '', '', '93ea2a40df57d8f33b472f5b2b023882281722d4'))),
        ('module1',
         (('name', 'list', '', ''),
          ('name', 'detail', 'Name', ''),
          ('other-prop (ID Mapping Text)', 'detail', 'Other Prop', 'Autre Prop'),
          ('foo (ID Mapping Value)', 'detail', 'bar', ''),
          ('baz (ID Mapping Value)', 'detail', 'quz', ''),
          ('mood (ID Mapping Text)', 'detail', 'Other Prop', ''),
          ('. < 3 (ID Mapping Value)', 'detail', ':(', ':-('),
          ('. >= 3 (ID Mapping Value)', 'detail', ':)', ':-)'),
          ('energy (ID Mapping Text)', 'detail', 'Other Prop', ''),
          ('. < 3 (ID Mapping Value)', 'detail',
           'jr://file/commcare/image/module1_list_icon_energy_high.jpg',
           'jr://file/commcare/image/module1_list_icon_energy_high_french.jpg'),
          ('. >= 3 (ID Mapping Value)', 'detail',
           'jr://file/commcare/image/module1_list_icon_energy_low.jpg',
           'jr://file/commcare/image/module1_list_icon_energy_low_french.jpg'),
          ('line_graph (graph)', 'detail', 'Velocity', ''),
          ('x-title (graph config)', 'detail', 'Time', ''),
          ('y-title (graph config)', 'detail', 'Speed', ''),
          ('name 0 (graph series config)', 'detail', 'Bird', ''),
          ('name 1 (graph series config)', 'detail', 'Cheetah', ''))),
        ('module1_form1',
         (('question1-label', '', '', '', '', '', '', '', ''),
          ('question2-label', 'question2', 'question2', '', '', '', '', '', ''),
          ('question2-item1-label', 'item1', 'item1', '', '', '', '', '', ''),
          ('question2-item2-label', 'item2', 'item2', '', '', '', '', '', ''),
          ('question3-label', 'question3', 'question3', '', '', '', '', '', ''),
          ('question3/question4-label', 'question4', 'question4', '', '', '', '', '', ''),
          ('question3/question5-label', 'question5', 'question5', '', '', '', '', '', ''),
          ('question7-label', 'question7', 'question7', '', '', '', '', '', ''),
          ('add_markdown-label', 'add_markdown', 'add_markdown', '', '', '', '', '', ''),
          ('update_markdown-label', '# update_markdown', '# update_markdown', '', '', '', '', '', ''),
          ('vetoed_markdown-label', '*i just happen to like stars*', '*i just happen to like stars*', '',
           '', '', '', '', ''),
          ))
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
            module.case_details.long.tabs[0].header['en'],
            'Name'
        )
        self.assertEqual(
            module.case_details.long.tabs[1].header['fra'],
            'Autre'
        )
        self.assertEqual(
            module.case_details.long.columns[1].enum[0].value['fra'],
            'french bar'
        )
        self.assertEqual(
            module.case_details.short.columns[0].header['fra'],
            'Nom'
        )
        self.assertEqual(
            module.case_details.long.columns[2].enum[0].value['fra'],
            ':--('
        )
        self.assertEqual(
            module.case_details.long.columns[3].enum[0].value['en'],
            'jr://file/commcare/image/module1_list_icon_energy_high_english.jpg'
        )

        # Test special characters and output refs
        self.assert_question_label("one < two", 0, 0, "en", "/data/question2")
        self.assert_question_label("un < deux", 0, 0, "fra", "/data/question2")
        self.assert_question_label("question3's label", 0, 0, "fra", "/data/question3")
        self.assert_question_label("question6: ____", 0, 0, "en", "/data/question3/question4")
        self.assert_question_label("question1: ____ < 5", 0, 0, "en", "/data/question7")
        self.assert_question_label("", 0, 0, "en", "/data/blank_value_node")

        # Test markdown
        self.assert_question_label("add_markdown: ~~new \\u0939\\u093f markdown~~", 0, 0, "en", "/data/add_markdown")
        self.assert_question_label("## smaller_markdown", 0, 0, "en", "/data/update_markdown")
        self.assert_question_label("*i just happen to like stars a lot*", 0, 0, "en", "/data/vetoed_markdown")
        form = self.app.get_module(0).get_form(0)
        self.assertXmlEqual(self.get_xml("change_upload_form"), form.render_xform())

    def test_missing_itext(self):
        self.app = Application.wrap(self.get_json("app_no_itext"))
        self.assert_question_label('question1', 0, 0, "en", "/data/question1")
        try:
            self.upload_raw_excel_translations(self.upload_no_change_headers, self.upload_no_change_data)
        except Exception as e:
            self.fail(e)

    def test_bad_column_name(self):
        self.upload_raw_excel_translations(
            self.upload_headers_bad_column,
            self.upload_data,
            expected_messages=[
                'Sheet "{}" has fewer columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra'.format(MODULES_AND_FORMS_SHEET_NAME),

                'Sheet "{}" has unrecognized columns. Sheet will '
                'be processed but ignoring the following columns: default-fra'.format(
                    MODULES_AND_FORMS_SHEET_NAME),

                'Sheet "module1" has fewer columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra',

                'Sheet "module1" has unrecognized columns. Sheet will '
                'be processed but ignoring the following columns: default-fra',
                "You must provide at least one translation of the case property 'name'",

                'Sheet "module1_form1" has fewer columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra',

                'Sheet "module1_form1" has unrecognized columns. Sheet will '
                'be processed but ignoring the following columns: default-fra',

                'App Translations Updated!'
            ]
        )

    def test_remove_description_from_case_property(self):
        row = {'case_property': 'words to keep (remove this)'}
        description = _remove_description_from_case_property(row)
        self.assertEqual(description, 'words to keep')

    def test_remove_description_from_case_property_multiple_parens(self):
        row = {'case_property': '(words (to) keep) (remove this)'}
        description = _remove_description_from_case_property(row)
        self.assertEqual(description, '(words (to) keep)')

    def test_empty_translations(self):
        # make the form a registration form
        self.app.modules[0].forms[0].actions.open_case.condition.type = 'always'
        self.upload_raw_excel_translations(
            self.upload_headers_bad_column,
            self.upload_empty_translations,
            expected_messages=[
                'Sheet "{}" has fewer columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra'.format(MODULES_AND_FORMS_SHEET_NAME),

                'Sheet "{}" has unrecognized columns. Sheet will '
                'be processed but ignoring the following columns: default-fra'.format(
                    MODULES_AND_FORMS_SHEET_NAME),

                'Sheet "module1" has fewer columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra',

                'Sheet "module1" has unrecognized columns. Sheet will '
                'be processed but ignoring the following columns: default-fra',
                "You must provide at least one translation of the case property 'name'",

                'Sheet "module1_form1" has fewer columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra',

                'Sheet "module1_form1" has unrecognized columns. Sheet will '
                'be processed but ignoring the following columns: default-fra',

                "You must provide at least one translation for the label 'question1-label' "
                "in sheet 'module1_form1'",

                'App Translations Updated!'
            ]
        )

    @flag_enabled('ICDS')
    def test_partial_case_list_translation_upload(self):
        # note this isn't a "partial" upload because this app only has one case list property
        module = self.app.get_module(0)
        self.assertEqual(
            module.case_details.short.columns[0].header, {'en': 'Name'}
        )
        translation_data = []
        # filter out the case lists translation from the upload
        for sheet in self.upload_no_change_data:
            if sheet[0] != 'module1':
                translation_data.append(sheet)
                continue

            mod1_sheet = []
            for translation in sheet[1]:
                if translation[1] == 'list':
                    continue
                mod1_sheet.append(translation)

            translation_data.append(['module1', mod1_sheet])
        self.upload_raw_excel_translations(self.upload_no_change_headers, translation_data)
        self.assertEqual(
            module.case_details.short.columns[0].header, {'en': 'Name'}
        )

    @flag_enabled('ICDS')
    def test_partial_case_detail_translation_upload(self):
        module = self.app.get_module(0)
        self.assertEqual(
            module.case_details.long.columns[0].header, {'en': 'Name', 'fra': ''}
        )
        self.assertEqual(
            module.case_details.long.columns[1].header, {'en': 'Other Prop', 'fra': 'Autre Prop'}
        )
        translation_data = []
        for sheet in self.upload_no_change_data:
            if sheet[0] != 'module1':
                translation_data.append(sheet)
                continue

            mod1_sheet = []
            for translation in sheet[1]:
                # translate name, and one prop, remove all other detail translations
                if translation[1] == 'detail':
                    if translation[0] == 'name':
                        new_trans = list(translation)
                        new_trans[2] = 'English Name'
                        new_trans[3] = 'French Name'
                        mod1_sheet.append(new_trans)
                    if translation[0] == 'other-prop (ID Mapping Text)':
                        mod1_sheet.append(
                            ('other-prop (ID Mapping Text)', 'detail', 'New Value!', 'Autre Prop'))
                    continue
                mod1_sheet.append(translation)

            translation_data.append(['module1', mod1_sheet])
        self.upload_raw_excel_translations(self.upload_no_change_headers, translation_data)
        self.assertEqual(
            module.case_details.long.columns[0].header, {'en': 'English Name', 'fra': 'French Name'}
        )
        self.assertEqual(
            module.case_details.long.columns[1].header, {'en': 'New Value!', 'fra': 'Autre Prop'}
        )

    @flag_enabled('ICDS')
    def test_partial_upload_id_mapping(self):
        module = self.app.get_module(0)
        self.assertEqual(
            module.case_details.long.columns[0].header, {'en': 'Name', 'fra': ''}
        )
        self.assertEqual(
            module.case_details.long.columns[1].header, {'en': 'Other Prop', 'fra': 'Autre Prop'}
        )
        translation_data = []
        for sheet in self.upload_no_change_data:
            if sheet[0] != 'module1':
                translation_data.append(sheet)
                continue

            mod1_sheet = []
            for translation in sheet[1]:
                if translation[0] == 'foo (ID Mapping Value)':
                    continue  # remove one of the id mapping values
                if translation[0] == 'baz (ID Mapping Value)':
                    mod1_sheet.append(('baz (ID Mapping Value)', 'detail', 'newbaz', ''))
                    continue  # modify one of the translations
                mod1_sheet.append(translation)

            translation_data.append(['module1', mod1_sheet])

        self.upload_raw_excel_translations(self.upload_no_change_headers, translation_data)
        self.assertEqual(
            module.case_details.long.columns[1].header, {'en': 'Other Prop', 'fra': 'Autre Prop'}
        )
        self.assertEqual(
            [(e.key, e.value) for e in module.case_details.long.columns[1].enum],
            [('foo', {'en': 'bar'}),
             ('baz', {'en': 'newbaz'})]
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


class BulkAppTranslationDownloadTest(SimpleTestCase, TestXmlMixin):

    file_path = ('data', 'bulk_app_translation', 'download')
    maxDiff = None

    excel_headers = (
        (MODULES_AND_FORMS_SHEET_NAME, ('Type', 'sheet_name', 'default_en', 'icon_filepath_en',
                                        'audio_filepath_en', 'unique_id')),
        ('module1', ('case_property', 'list_or_detail', 'default_en')),
        ('module1_form1', ('label', 'default_en', 'image_en', 'audio_en', 'video_en'))
    )

    excel_data = (
        (MODULES_AND_FORMS_SHEET_NAME,
         (('Module', 'module1', 'Stethoscope', 'jr://file/commcare/image/module0.png', '', '58ce5c9cf6eda401526973773ef216e7980bc6cc'),
          ('Form',
           'module1_form1',
           'Stethoscope Form',
           'jr://file/commcare/image/module0_form0.png',
           '',
           'c480ace490edc870ae952765e8dfacec33c69fec'))),
        ('module1', (('name', 'list', 'Name'), ('name', 'detail', 'Name'))),
        ('module1_form1',
         (('What_does_this_look_like-label', 'What does this look like?',
           'jr://file/commcare/image/data/What_does_this_look_like.png', '', ''),
          ('no_media-label', 'No media', '', '', ''),
          ('has_refs-label', 'Here is a ref <output value="/data/no_media"/> with some trailing text and "bad" &lt; xml.', '', '', '')))
    )

    @classmethod
    def setUpClass(cls):
        super(BulkAppTranslationDownloadTest, cls).setUpClass()
        cls.app = Application.wrap(cls.get_json("app"))
        # Todo, refactor this into BulkAppTranslationTestBase.upload_raw_excel_translations
        file = BytesIO()
        export_raw(cls.excel_headers, cls.excel_data, file, format=Format.XLS_2007)

        with tempfile.TemporaryFile(suffix='.xlsx') as f:
            f.write(file.getvalue())
            f.seek(0)
            wb_reader = WorkbookJSONReader(f)
            cls.expected_workbook = [{'name': ws.title, 'rows': list(ws)}
                                     for ws in wb_reader.worksheets]

    def test_sheet_names(self):
        self.assertEqual(get_module_sheet_name(self.app.modules[0]), "module1")
        self.assertEqual(get_form_sheet_name(self.app.modules[0].forms[0]), "module1_form1")

    def test_sheet_headers(self):
        self.assertListEqual(get_bulk_app_sheet_headers(self.app), [
            ['Modules_and_forms', ['Type', 'sheet_name', 'default_en',
             'icon_filepath_en', 'audio_filepath_en', 'unique_id']],
            ['module1', ['case_property', 'list_or_detail', 'default_en']],
            ['module1_form1', ['label', 'default_en', 'image_en', 'audio_en', 'video_en']]
        ])

        self.assertEqual(get_bulk_multimedia_sheet_headers('fra'),
            (('translations', ('menu or form', 'case_property', 'detail or label',
                               'fra', 'image', 'audio', 'video')),))

    def test_module_case_list_form_rows(self):
        app = AppFactory.case_list_form_app_factory().app
        self.assertEqual(get_module_case_list_form_rows(app.langs, app.modules[0]),
                         [('case_list_form_label', 'list', 'New Case')])

    def test_module_rows(self):
        self.assertListEqual(get_module_rows(self.app.langs, self.app.modules[0]), [
            ('name', 'list', 'Name'),
            ('name', 'detail', 'Name'),
        ])

    def test_form_rows(self):
        lang = self.app.langs[0]
        form = self.app.modules[0].forms[0]

        self.assertListEqual(get_menu_row([form.name.get(lang)],
                                          [form.icon_by_language(lang)],
                                          [form.audio_by_language(lang)]),
                             ['Stethoscope Form', 'jr://file/commcare/image/module0_form0.png', None])

        self.assertListEqual(get_form_question_rows([lang], form), [
            ['What_does_this_look_like-label', 'What does this look like?',
             'jr://file/commcare/image/data/What_does_this_look_like.png', '', ''],
            ['no_media-label', 'No media',
             '', '', ''],
            ['has_refs-label',
             'Here is a ref <output value="/data/no_media"/> with some trailing text and "bad" &lt; xml.',
             '', '', ''],
        ])

    def test_bulk_app_sheet_rows(self):
        actual_headers = get_bulk_app_sheet_headers(self.app)
        actual_rows = get_bulk_app_sheet_rows(self.app)

        actual_workbook = [
            {'name': title,
             'rows': [dict(zip(headers, row)) for row in actual_rows[title]]}
            for title, headers in actual_headers
        ]

        for actual_sheet, expected_sheet in zip(actual_workbook,
                                                self.expected_workbook):
            self.assertEqual(actual_sheet, expected_sheet)
        self.assertEqual(actual_workbook, self.expected_workbook)

    def test_bulk_multimedia_sheet_rows(self):
        self.assertListEqual(get_bulk_multimedia_sheet_rows(self.app.langs[0], self.app), [
            ['module1', '', '', 'Stethoscope', 'jr://file/commcare/image/module0.png', None],
            ['module1', 'name', 'list', 'Name'], ['module1', 'name', 'detail', 'Name'],
            ['module1_form1', '', '', 'Stethoscope Form', 'jr://file/commcare/image/module0_form0.png', None],
            ['module1_form1', '', 'What_does_this_look_like-label', 'What does this look like?',
             'jr://file/commcare/image/data/What_does_this_look_like.png', '', ''],
            ['module1_form1', '', 'no_media-label', 'No media', '', '', ''],
            ['module1_form1', '', 'has_refs-label',
             'Here is a ref <output value="/data/no_media"/> with some trailing text and "bad" &lt; xml.',
             '', '', ''],
        ])


class RenameLangTest(SimpleTestCase):

    def test_rename_lang_empty_form(self):
        app = Application.new_app('domain', "Untitled Application")
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


class AggregateMarkdownNodeTests(SimpleTestCase, TestXmlMixin):

    file_path = ('data', 'bulk_app_translation', 'aggregate')

    headers = (
        (MODULES_AND_FORMS_SHEET_NAME, (
            'Type', 'sheet_name',
            'default_en', 'default_afr', 'default_fra',
            'icon_filepath_en', 'icon_filepath_afr', 'icon_filepath_fra',
            'audio_filepath_en', 'audio_filepath_afr', 'audio_filepath_fra',
            'unique_id'
        )),
        ('module1', (
            'case_property', 'list_or_detail', 'default_en', 'default_fra', 'default_fra'
        )),
        ('module1_form1', (
            'label',
            'default_en', 'default_afr', 'default_fra',
            'audio_en', 'audio_afr', 'audio_fra',
            'image_en', 'image_afr', 'image_fra',
            'video_en', 'video_afr', 'video_fra',
        ))
    )
    data = (
        (MODULES_AND_FORMS_SHEET_NAME,
         (('Module', 'module1',
           'Untitled Module', 'Ongetitelde Module', 'Module Sans Titre',
           '', '', '',
           '', '', '',
           'deadbeef'),
          ('Form', 'module1_form1',
           'Untitled Form', 'Ongetitelde Form', 'Formulaire Sans Titre',
           '', '', '',
           '', '', '',
           'c0ffee'))),

        ('module1',
         (('name', 'list', 'Name', 'Naam', 'Nom'),
          ('name', 'detail', 'Name', 'Naam', 'Nom'))),

        ('module1_form1',
         (('with_markdown-label',
           '*With* Markdown', '*Met* Markdown', '*Avec* le Markdown',
           '', '', '', '', '', '', '', '', ''),
          ('markdown_veto-label',
           '*Without* Markdown', '*Sonder* Markdown', '*Sans* le Markdown',
           '', '', '', '', '', '', '', '', ''))))

    def get_worksheet(self, title):
        string_io = BytesIO()
        export_raw(self.headers, self.data, string_io, format=Format.XLS_2007)
        string_io.seek(0)
        workbook = WorkbookJSONReader(string_io)  # __init__ will read string_io
        return workbook.worksheets_by_title[title]

    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application")
        self.app.langs = ['en', 'afr', 'fra']
        module1 = self.app.add_module(Module.new_module('module', None))
        form1 = self.app.new_form(module1.id, "Untitled Form", None)
        form1.source = self.get_xml('initial_xform').decode('utf-8')

        self.form1_worksheet = self.get_worksheet('module1_form1')

    def test_markdown_node(self):
        """
        If one translation has a Markdown node, the label should be a Markdown label
        If Markdown is vetoed for one language, it should be vetoed for the label
        """
        missing_cols = set()
        sheet = self.form1_worksheet
        rows = get_unicode_dicts(sheet)
        with patch('corehq.apps.translations.app_translations.save_xform') as save_xform_patch:
            msgs = update_form_translations(sheet, rows, missing_cols, self.app)
            self.assertEqual(msgs, [])
            expected_xform = self.get_xml('expected_xform').decode('utf-8')
            self.maxDiff = None
            self.assertEqual(save_xform_patch.call_args[0][2].decode('utf-8'), expected_xform)
