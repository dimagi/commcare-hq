import os
import tempfile
from collections import OrderedDict, defaultdict
from io import BytesIO

from django.test import SimpleTestCase

from unittest.mock import patch

from couchexport.export import export_raw
from couchexport.models import Format

from corehq.apps.app_manager.models import Application, Module, ReportAppConfig
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.translations.app_translations.download import (
    get_bulk_app_sheets_by_name,
    get_bulk_app_single_sheet_by_name,
    get_form_question_label_name_media,
    get_module_case_list_form_rows,
    get_module_case_list_menu_item_rows,
    get_module_detail_rows,
    get_module_search_command_rows,
    get_case_search_rows,
)
from corehq.apps.translations.app_translations.upload_app import (
    get_sheet_name_to_unique_id_map,
    process_bulk_app_translation_upload,
)
from corehq.apps.translations.app_translations.upload_form import (
    BulkAppTranslationFormUpdater,
)
from corehq.apps.translations.app_translations.upload_module import (
    BulkAppTranslationModuleUpdater,
)
from corehq.apps.translations.app_translations.utils import (
    get_bulk_app_sheet_headers,
    get_form_sheet_name,
    get_menu_row,
    get_module_sheet_name,
)
from corehq.apps.translations.const import (
    MODULES_AND_FORMS_SHEET_NAME,
    SINGLE_SHEET_NAME,
)
from corehq.apps.translations.generators import EligibleForTransifexChecker
from corehq.util.test_utils import flag_enabled
from corehq.util.workbook_json.excel import WorkbookJSONReader, get_workbook

EXCEL_HEADERS = (
    (MODULES_AND_FORMS_SHEET_NAME, ('Type', 'menu_or_form', 'default_en', 'image_en',
                                    'audio_en', 'unique_id')),
    ('menu1', ('case_property', 'list_or_detail', 'default_en')),
    ('menu1_form1', ('label', 'default_en', 'image_en', 'audio_en', 'video_en')),
    ('menu2', ('case_property', 'list_or_detail', 'default_en')),
    ('menu2_form1', ('label', 'default_en', 'image_en', 'audio_en', 'video_en')),
    ('menu3', ('case_property', 'list_or_detail', 'default_en')),
    ('menu3_form1', ('label', 'default_en', 'image_en', 'audio_en', 'video_en')),
    ('menu4', ('case_property', 'list_or_detail', 'default_en')),
    ('menu4_form1', ('label', 'default_en', 'image_en', 'audio_en', 'video_en')),
    ('menu5', ('case_property', 'list_or_detail', 'default_en')),
    ('menu6', ('case_property', 'list_or_detail', 'default_en')),
    ('menu6_form1', ('label', 'default_en', 'image_en', 'audio_en', 'video_en')),
)


EXCEL_DATA = (
    (MODULES_AND_FORMS_SHEET_NAME,
     (('Menu', 'menu1', 'Stethoscope', 'jr://file/commcare/image/module0.png', '',
       '58ce5c9cf6eda401526973773ef216e7980bc6cc'),
      ('Form',
       'menu1_form1',
       'Stethoscope Form',
       'jr://file/commcare/image/module0_form0.png',
       '',
       'c480ace490edc870ae952765e8dfacec33c69fec'),
      ('Menu', 'menu2', 'Register Series', '', '', 'b9c25abe21054632a3623199debd7cfa'),
      ('Form', 'menu2_form1', 'Registration Form', '', '', '280b1b06d1b442b9bba863453ba30bc3'),
      ('Menu', 'menu3', 'Followup Series', '', '', '217e1c8de3dd46f98c7d2806bc19b580'),
      ('Form', 'menu3_form1', 'Add Point to Series', '', '', 'a01b55fd2c1a483492c1166029946249'),
      ('Menu', 'menu4', 'Remove Point', '', '', '17195132472446ed94bd91ba19a2b379'),
      ('Form', 'menu4_form1', 'Remove Point', '', '', '98458acd899b4d5f87df042a7585e8bb'),
      ('Menu', 'menu5', 'Empty Reports Module', '', '', '703eb807ae584d1ba8bf9457d7ac7590'),
      ('Menu', 'menu6', 'Advanced Module', '', '', '7f75ed4c15be44509591f41b3d80746e'),
      ('Form', 'menu6_form1', 'Advanced Form', '', '', '2b9c856ba2ea4ec1ab8743af299c1627'),
      ('Form', 'menu6_form2', 'Shadow Form', '', '', 'c42e1a50123c43f2bd1e364f5fa61379'),
      )),
    ('menu1',
     (('case_list_menu_item_label', 'list', 'Steth List'),
      ('no_items_text', 'list', 'Empty List'),
      ('select_text', 'list', 'Continue'),
      ('name', 'list', 'Name'),
      ('name', 'detail', 'Name'))),
    ('menu1_form1',
     (('What_does_this_look_like-label', 'What does this look like?',
       'jr://file/commcare/image/data/What_does_this_look_like.png', '', ''),
      ('no_media-label', 'No media', '', '', ''),
      ('has_refs-label', 'Here is a ref <output value="/data/no_media"/> with some trailing text '
                         'and "bad" &lt; xml.', '', '', ''),
      ('submit_label', 'Submit', '', '', ''),
      ('submit_notification_label', '', '', '', ''))),
    ('menu2',
     (('no_items_text', 'list', 'List is empty.'),
      ('select_text', 'list', 'Continue'),
      ('name', 'list', 'Name'),
      ('name', 'detail', 'Name'))),
    ('menu2_form1',
     (('name_of_series-label', 'Name of series', '', '', ''),
      ('submit_label', 'Submit', '', '', ''),
      ('submit_notification_label', '', '', '', ''))),
    ('menu3',
     (('no_items_text', 'list', 'List is empty.'),
      ('select_text', 'list', 'Continue'),
      ('name', 'list', 'Name'),
      ('Tab 0', 'detail', 'Name'),
      ('Tab 1', 'detail', 'Graph'),
      ('name', 'detail', 'Name'),
      ('line_graph (graph)', 'detail', 'Line Graph'),
      ('secondary-y-title (graph config)', 'detail', ''),
      ('x-title (graph config)', 'detail', 'xxx'),
      ('y-title (graph config)', 'detail', 'yyy'),
      ('x-name 0 (graph series config)', 'detail', 'xxx'),
      ('name 0 (graph series config)', 'detail', 'yyy'),
      ('graph annotation 1', 'detail', 'This is (2, 2)'))),
    ('menu3_form1',
     (('x-label', 'x', '', '' ''),
      ('y-label', 'y', '', '', ''),
      ('submit_label', 'Submit', '', '', ''),
      ('submit_notification_label', '', '', '', ''))),
    ('menu4',
     (('no_items_text', 'list', 'List is empty.'),
      ('select_text', 'list', 'Continue'),
      ('x', 'list', 'X'),
      ('y', 'list', 'Y'),
      ('x (ID Mapping Text)', 'detail', 'X Name'),
      ('1 (ID Mapping Value)', 'detail', 'one'),
      ('2 (ID Mapping Value)', 'detail', 'two'),
      ('3 (ID Mapping Value)', 'detail', 'three'))),
    ('menu4_form1',
     (('confirm_remove-label',
       'Swipe to remove the point at (<output value="instance(\'casedb\')/casedb/case[@case_id = '
       'instance(\'commcaresession\')/session/data/case_id]/x"/>  ,<output value="instance(\'casedb\')'
       '/casedb/case[@case_id = instance(\'commcaresession\')/session/data/case_id]/y"/>).', '', '', ''),
      ('submit_label', 'Submit', '', '', ''),
      ('submit_notification_label', '', '', '', ''))),
    ('menu5', ()),
    ('menu6',
     (('no_items_text', 'list', 'List is empty.'),
      ('select_text', 'list', 'Continue with Case(s)'),
      ('name', 'list', 'Name'),
      ('name', 'detail', 'Name'))),
    ('menu6_form1',
     (('this_form_does_nothing-label', 'This form does nothing.', '', '', ''),
      ('submit_label', 'Submit', '', '', ''),
      ('submit_notification_label', '', '', '', ''))),
)


class BulkAppTranslationTestBase(SimpleTestCase, TestXmlMixin):
    root = os.path.dirname(__file__)

    def upload_raw_excel_translations(self, app, excel_headers, excel_data, expected_messages=None, lang=None):
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
            workbook = get_workbook(f)
            assert workbook

            sheet_name_to_unique_id = get_sheet_name_to_unique_id_map(f, lang)
            messages = process_bulk_app_translation_upload(app, workbook, sheet_name_to_unique_id, lang=lang)

        self.assertSetEqual(
            {m[1] for m in messages}, set(expected_messages)
        )


class BulkAppTranslationUploadErrorTest(BulkAppTranslationTestBase):
    def setUp(self):
        """
        Instantiate an app from file_path + app.json
        """
        super(BulkAppTranslationUploadErrorTest, self).setUp()
        self.factory = AppFactory()
        module, form = self.factory.new_basic_module('orange', 'patient')
        self.lang = 'en'

    single_sheet_headers = (
        (SINGLE_SHEET_NAME, (
            "menu_or_form", "case_property", "list_or_detail", "label",
            "default_en", "image_en", "audio_en", "video_en", 'unique_id'
        )),
    )

    single_sheet_data = (
        (SINGLE_SHEET_NAME, (
            ("menu1", "", "", "", "orange module", "", "", "", "orange_module"),
            ("menu1", "name", "list", "", "Name", "", "", ""),
            ("menu1", "name", "detail", "", "Name", "", "", ""),
            ("menu1_form1", "", "", "", "orange form 0", "", "", "", "orange_form_0"),
            ("menu1_form1", "", "", "question1-label", "in english", "", "", "", ""),
            ("menu1_form9", "", "", "", "not a form", "", "", "", "not_a_form"),
            ("menu9", "" "", "", "not a menu", "", "", "", "not_a_menu"),
            ("not_a_form", "", "", "" "i am not a form", "", "", "", "also_not_a_form"),
        )),
    )

    multi_sheet_headers = (
        (MODULES_AND_FORMS_SHEET_NAME, (
            "Type", "menu_or_form", "default_en", "image_en", "audio_en", "unique_id"
        )),
        ("menu1", ("case_property", "list_or_detail", "default_en")),
        ("menu1_form1", ("label-bad", "default_en", "image_en", "audio_en", "video_en")),
        ("bad_sheet_name", ("label", "default_en", "image_en", "audio_en", "video_en")),
    )

    multi_sheet_data = (
        (MODULES_AND_FORMS_SHEET_NAME, (
         ("Menu", "menu1", "orange module", "", "", "orange_module"),
         ("Menu", "menu9", "not a menu", "", "", "not_a_menu"),
         ("Form", "menu1_form1", "orange form 0", "", "", "orange_form_0"),
         ("Form", "menu1_form9", "not a form", "", "", "not_a_form"),
         ("Form", "not_a_form", "i am not a form", "", "", "also_not_a_form"))),
        ("menu1", (
         ("name", "list", "Name"),
         ("name", "detail", "Name"))),
        ("menu1_form1", (
         ("question1-label", "in english", "", "", ""))),
        ("bad_sheet_name", (
         ("question1-label", "in english", "", "", ""))))

    def test_sheet_errors(self):
        expected_messages = [
            'Invalid menu in row "menu9", skipping row.',
            'Invalid form in row "menu1_form9", skipping row.',
            'Did not recognize "not_a_form", skipping row.',
            'App Translations Updated!',
        ]

        self.upload_raw_excel_translations(self.factory.app, self.single_sheet_headers,
                                           self.single_sheet_data,
                                           expected_messages=expected_messages,
                                           lang=self.lang)

        expected_messages += [
            'Skipping sheet menu1_form1: expected first columns to be label',
            'Skipping sheet "bad_sheet_name", could not recognize title',
        ]

        self.upload_raw_excel_translations(self.factory.app, self.multi_sheet_headers,
                                           self.multi_sheet_data,
                                           expected_messages=expected_messages)


class BulkAppTranslationTestBaseWithApp(BulkAppTranslationTestBase):

    def setUp(self):
        """
        Instantiate an app from file_path + app.json
        """
        super(BulkAppTranslationTestBaseWithApp, self).setUp()
        self.app = Application.wrap(self.get_json("app"))

    def upload_raw_excel_translations(self, excel_headers, excel_data, lang=None, expected_messages=None):
        super(BulkAppTranslationTestBaseWithApp, self).upload_raw_excel_translations(self.app,
            excel_headers, excel_data, expected_messages, lang)

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

    def assert_module_name(self, module_id, language, name):
        module = self.app.get_module(module_id)
        self.assertEqual(name, module.name.get(language, None))


class BulkAppTranslationBasicTest(BulkAppTranslationTestBaseWithApp):

    file_path = "data", "bulk_app_translation", "basic"

    multi_sheet_upload_headers = (
        (MODULES_AND_FORMS_SHEET_NAME, (
            "Type", "menu_or_form", "default_en", "default_fra", 'image_en', 'image_fra',
            'audio_en', 'audio_fra', "unique_id",
        )),
        ("menu1", (
            "case_property", "list_or_detail", "default_en", "default_fra"
        )),
        ("menu1_form1", (
            "label", "default_en", "default_fra", "image_en", "image_fra",
            "audio_en", "audio_fra", "video_en", "video_fra",
        ))
    )

    single_sheet_upload_headers = (
        (SINGLE_SHEET_NAME, (
            "menu_or_form", "case_property", "list_or_detail", "label",
            "default_en", "image_en", "audio_en", "video_en", "unique_id",
        )),
    )

    upload_headers_bad_column = (  # bad column is default-fra
        (MODULES_AND_FORMS_SHEET_NAME, (
            "Type", "menu_or_form", "default_en", "default-fra",
            "image_en", "image_fra", "audio_en", "audio_fra", "unique_id"
        )),
        ("menu1", (
            "case_property", "list_or_detail", "default_en", "default-fra"
        )),
        ("menu1_form1", (
            "label", "default_en", "default-fra", "image_en", "image_fra",
            "audio_en", "audio_fra", "video_en", "video_fra",
        ))
    )

    multi_sheet_upload_data = (
        (MODULES_AND_FORMS_SHEET_NAME, (
            ("Menu", "menu1", "My & awesome module", "", "", "", "", "",
             "8f4f7085a93506cba4295eab9beae8723c0cee2a"),
            ("Form", "menu1_form1", "My more & awesome form", "", "", "", "", "", "", "",
             "6c6c6315b3c514c616b6c57d48f7cf7c963f1714")
        )),
        ("menu1", (
            ("case_list_form_label", "list", "Register Mother", "Inscrivez-Mère"),
            ("case_list_menu_item_label", "list", "List Stethoscopes", "French List of Stethoscopes"),
            ("search_label", "list", "Find a Mother", "Mère!"),
            ("search_again_label", "list", "Find Another Mother", "Mère! Encore!"),
            ("title_label", "list", "Find a Mom", "Maman!"),
            ("description", "list", "More information", "Plus d'information"),
            ("select_text", "list", "Continue with case", "Continuer avec le cas"),
            ("no_items_text", "list", "Empty List", "Lista Vacía"),
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
        ("menu1_form1", (
            ("question1-label", "in english", "it's in french", "", "", "", "", "", ""),
            ("question2-label", "one &lt; two", "un &lt; deux", "", "", "", "", "", ""),
            ("question2-item1-label", "item1", "item1", "", "", "", "", "", ""),
            ("question2-item2-label", "item2", "", "", "", "", "", "", ""),
            ("question3-label", "question3", "question3&#39;s label", "", "", "", "", "", ""),
            ("blank_value_node-label", "", "", "", "", "en-audio.mp3", "fra-audio.mp3", "", ""),
            ("question3/question4-label", 'question6: <output value="/data/question6"/>',
             'question6: <output value="/data/question6"/>', "", "", "", "", "", ""),
            ("question3/question5-label", "English Label", "English Label", "", "", "", "", "", ""),
            ("question7-label", 'question1: <output value="/data/question1"/> &lt; 5', "question7", "", "", "", "",
             "", ""),
            ('add_markdown-label', 'add_markdown: ~~new \\u0939\\u093f markdown~~',
             'add_markdown: ~~new \\u0939\\u093f markdown~~', '', '', '', '', '', ''),
            ('update_markdown-label', '## smaller_markdown', '## smaller_markdown', '', '', '', '', '', ''),
            ('remove_markdown-label', 'no longer markdown', 'just plain text', '', '', '', '', '', ''),
            ('vetoed_markdown-label', '*i just happen to like stars a lot*', '*i just happen to like stars a lot*',
             '', '', '', '', '', ''),
            ("submit_label", "new submit", "nouveau", "", "", "", "", "", ""),
            ("submit_notification_label", "new submit notification", "nouveau", "", "", "", "", "", ""),
        ))
    )

    single_sheet_upload_data = (
        (SINGLE_SHEET_NAME, (
            ("menu1", "", "", "", "My & awesome module", "", "", "", "8f4f7085a93506cba4295eab9beae8723c0cee2a"),
            ("menu1", "case_list_form_label", "list", "", "Register Mother", "", "", "", ""),
            ("menu1", "case_list_menu_item_label", "list", "",
             "List Stethoscopes", "French List of Stethoscopes", "", "", ""),
            ("menu1", "search_label", "list", "", "Find a Mother", "", "", "", ""),
            ("menu1", "search_again_label", "list", "", "Find Another Mother", "", "", "", ""),
            ("menu1", "title_label", "list", "Find a Mom", "Maman!", "", "", "", ""),
            ("menu1", "description", "list", "More information", "Plus d'information", "", "", "", ""),
            ("menu1", "select_text", "list", "Continue with case", "Continuer avec le cas", "", "", "", ""),
            ("menu1", "no_items_text", "list", "Empty List", "Lista Vacía", "", "", "", ""),
            ("menu1", "name", "list", "", "Name", "", "", "", ""),
            ("menu1", "Tab 0", "detail", "", "Name", "", "", "", ""),
            ("menu1", "Tab 1", "detail", "", "Other", "", "", "", ""),
            ("menu1", "name", "detail", "", "Name", "", "", "", ""),
            ("menu1", "other-prop (ID Mapping Text)", "detail", "", "Other Prop", "", "", "", ""),
            ("menu1", "foo (ID Mapping Value)", "detail", "", "bar", "", "", "", ""),
            ("menu1", "baz (ID Mapping Value)", "detail", "", "quz", "", "", "", ""),
            ("menu1", "mood (ID Mapping Text)", "detail", "", "Mood", "", "", "", ""),
            ("menu1", ". < 3 (ID Mapping Value)", "detail", "", ":(", "", "", "", ""),
            ("menu1", ". >= 3 (ID Mapping Value)", "detail", "", ":)", "", "", "", ""),
            ("menu1", "energy (ID Mapping Text)", "detail", "", "Energy", "", "", "", ""),
            ("menu1", ". < 3 (ID Mapping Value)", "detail", "",
             "jr://file/commcare/image/module1_list_icon_energy_high_english.jpg", "", "", "", ""),
            ("menu1", ". >= 3 (ID Mapping Value)", "detail", "",
             "jr://file/commcare/image/module1_list_icon_energy_low_english.jpg", "", "", "", ""),
            ("menu1", 'line_graph (graph)', 'detail', "", 'Velocity', "", "", "", ""),
            ("menu1", 'x-title (graph config)', 'detail', "", 'Time', "", "", "", ""),
            ("menu1", 'y-title (graph config)', 'detail', "", 'Speed', "", "", "", ""),
            ("menu1", 'name 0 (graph series config)', 'detail', "", 'Bird', "", "", "", ""),
            ("menu1", 'name 1 (graph series config)', 'detail', "", 'Cheetah', "", "", "", ""),
            ("menu1_form1", "", "", "", "My more & awesome form", "", "", "",
             "6c6c6315b3c514c616b6c57d48f7cf7c963f1714"),
            ("menu1_form1", "", "", "question1-label", "in english", "", "", "", ""),
            ("menu1_form1", "", "", "question2-label", "one &lt; two", "", "", "", ""),
            ("menu1_form1", "", "", "question2-item1-label", "item1", "", "", "", ""),
            ("menu1_form1", "", "", "question2-item2-label", "", "", "", "", ""),
            ("menu1_form1", "", "", "question3-label", "question3", "", "", "", ""),
            ("menu1_form1", "", "", "blank_value_node-label", "", "", "en-audio.mp3", "", ""),
            ("menu1_form1", "", "", "question3/question4-label",
             'question6: <output value="/data/question6"/>', "", "", "", ""),
            ("menu1_form1", "", "", "question3/question5-label", "English Label", "", "", "", ""),
            ("menu1_form1", "", "", "question7-label",
             'question1: <output value="/data/question1"/> &lt; 5', "", "", "", ""),
            ("menu1_form1", "", "", 'add_markdown-label',
             'add_markdown: ~~new \\u0939\\u093f markdown~~', "", "", "", ""),
            ("menu1_form1", "", "", 'update_markdown-label',
             '## smaller_markdown', "", "", "", ""),
            ("menu1_form1", "", "", 'remove_markdown-label',
             'no longer markdown', "", "", "", ""),
            ("menu1_form1", "", "", 'vetoed_markdown-label',
             '*i just happen to like stars a lot*', "", "", "", ""),
        )),
    )

    multi_sheet_upload_no_change_data = (
        (MODULES_AND_FORMS_SHEET_NAME,
         (('Module', 'menu1', 'My & awesome module', '', '', '', '', '',
           '8f4f7085a93506cba4295eab9beae8723c0cee2a'),
          ('Form', 'menu1_form1', 'My more & awesome form', '', '', '', '', '', '', '',
           '6c6c6315b3c514c616b6c57d48f7cf7c963f1714'))),
        ('menu1',
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
        ('menu1_form1',
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
          ('remove_markdown-label', '# remove_markdown', '# remove_markdown', '', '', '', '', '', ''),
          ('vetoed_markdown-label', '*i just happen to like stars*', '*i just happen to like stars*', '', '', '',
           '', '', ''),
          ))
    )

    single_sheet_upload_no_change_data = (
        (SINGLE_SHEET_NAME, (
            ('menu1', '', '', '', 'My & awesome module', '', '', '', "8f4f7085a93506cba4295eab9beae8723c0cee2a"),
            ('menu1', 'name', 'list', '', 'Name', '', '', '', ''),
            ('menu1', 'name', 'detail', '', 'Name', '', '', '', ''),
            ('menu1', 'other-prop (ID Mapping Text)', 'detail', '', 'Other Prop', '', '', '', ''),
            ('menu1', 'foo (ID Mapping Value)', 'detail', '', 'bar', '', '', '', ''),
            ('menu1', 'baz (ID Mapping Value)', 'detail', '', 'quz', '', '', '', ''),
            ('menu1', 'mood (ID Mapping Text)', 'detail', '', 'Other Prop', '', '', '', ''),
            ('menu1', '. < 3 (ID Mapping Value)', 'detail', '', ':(', '', '', '', ''),
            ('menu1', '. >= 3 (ID Mapping Value)', 'detail', '', ':)', '', '', '', ''),
            ('menu1', 'energy (ID Mapping Text)', 'detail', '', 'Other Prop', '', '', '', ''),
            ('menu1', '. < 3 (ID Mapping Value)', 'detail', '',
                'jr://file/commcare/image/module1_list_icon_energy_high.jpg', '', '', '', ''),
            ('menu1', '. >= 3 (ID Mapping Value)', 'detail', '',
                'jr://file/commcare/image/module1_list_icon_energy_low.jpg', '', '', '', ''),
            ('menu1', 'line_graph (graph)', 'detail', '', 'Velocity', '', '', '', ''),
            ('menu1', 'x-title (graph config)', 'detail', '', 'Time', '', '', '', ''),
            ('menu1', 'y-title (graph config)', 'detail', '', 'Speed', '', '', '', ''),
            ('menu1', 'name 0 (graph series config)', 'detail', '', 'Bird', '', '', '', ''),
            ('menu1', 'name 1 (graph series config)', 'detail', '', 'Cheetah', '', '', '', ''),
            ('menu1_form1', '', '', '', 'My more & awesome form', '', '', '',
             '6c6c6315b3c514c616b6c57d48f7cf7c963f1714'),
            ('menu1_form1', '', '', 'question1-label', 'question1', '', '', '', ''),
            ('menu1_form1', '', '', 'question2-label', 'question2', '', '', '', ''),
            ('menu1_form1', '', '', 'question2-item1-label', 'item1', '', '', '', ''),
            ('menu1_form1', '', '', 'question2-item2-label', 'item2', '', '', '', ''),
            ('menu1_form1', '', '', 'question3-label', 'question3', '', '', '', ''),
            ('menu1_form1', '', '', 'question3/question4-label', 'question4', '', '', '', ''),
            ('menu1_form1', '', '', 'question3/question5-label', 'question5', '', '', '', ''),
            ('menu1_form1', '', '', 'question7-label', 'question7', '', '', '', ''),
            ('menu1_form1', '', '', 'add_markdown-label', 'add_markdown', '', '', '', ''),
            ('menu1_form1', '', '', 'update_markdown-label', '# update_markdown', '', '', '', ''),
            ('menu1_form1', '', '', 'remove_markdown-label', '# remove_markdown', '', '', '', ''),
            ('menu1_form1', '', '', 'vetoed_markdown-label', '*i just happen to like stars*', '', '', '', ''),
        )),
    )

    upload_empty_translations = (
        (MODULES_AND_FORMS_SHEET_NAME,
         (('Menu', 'menu1', 'My & awesome module', '', '', '', '', '',
           '8f4f7085a93506cba4295eab9beae8723c0cee2a'),
          ('Form', 'menu1_form1', '', '', '', '', '', '', '', '', '6c6c6315b3c514c616b6c57d48f7cf7c963f1714'))),
        ('menu1',
         (('name', 'list', '', ''),
          ('name', 'detail', '', ''),
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
        ('menu1_form1',
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
          ('remove_markdown-label', '# remove_markdown', '# remove_markdown', '', '', '', '', '', ''),
          ('vetoed_markdown-label', '*i just happen to like stars*', '*i just happen to like stars*', '',
           '', '', '', '', ''),
          ))
    )

    def test_set_up(self):
        self._shared_test_initial_set_up()

    def test_no_change_upload_multi_sheet(self):
        self.upload_raw_excel_translations(self.multi_sheet_upload_headers,
                                           self.multi_sheet_upload_no_change_data)
        self._shared_test_initial_set_up()

        # Languages not in the app should have their content cleared
        self.assert_module_name(0, "en", "My & awesome module")
        self.assert_module_name(0, "es", None)

    def test_no_change_upload_single_sheet(self):
        self.upload_raw_excel_translations(self.single_sheet_upload_headers,
                                           self.single_sheet_upload_no_change_data,
                                           lang='en')
        self._shared_test_initial_set_up()

        # Single sheet upload shouldn't attempt to clear anything
        self.assert_module_name(0, "en", "My & awesome module")
        self.assert_module_name(0, "es", "Mi cosa increíble")

    def _shared_test_initial_set_up(self):
        self.assert_question_label("question1", 0, 0, "en", "/data/question1")
        self.assert_case_property_label("Autre Prop", "other-prop", 0, "long", "fra")

    def _test_change_upload(self, langs):
        en = 'en' in langs
        fra = 'fra' in langs

        if en:
            self.assert_question_label("in english", 0, 0, "en", "/data/question1")
        if fra:
            self.assert_question_label("it's in french", 0, 0, "fra", "/data/question1")

        # Test that translations can be deleted.
        # Can only do this if translation multiple languages.
        if en and fra:
            self.assert_question_label("English Label", 0, 0, "fra", "/data/question3/question5")
            self.assert_case_property_label(None, "other-prop", 0, "long", "fra")
            self.assert_case_property_label(None, "name", 0, "long", "en")

        module = self.app.get_module(0)
        if en:
            self.assertEqual(
                module.case_details.long.tabs[0].header['en'],
                'Name'
            )
            self.assertEqual(
                module.case_list.label['en'],
                'List Stethoscopes'
            )
            self.assertEqual(
                module.case_details.long.columns[3].enum[0].value['en'],
                'jr://file/commcare/image/module1_list_icon_energy_high_english.jpg'
            )
        if fra:
            self.assertEqual(
                module.case_list.label['fra'],
                'French List of Stethoscopes'
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

        # Test special characters and output refs
        if en:
            self.assert_question_label("one < two", 0, 0, "en", "/data/question2")
            self.assert_question_label("question6: ____", 0, 0, "en", "/data/question3/question4")
            self.assert_question_label("question1: ____ < 5", 0, 0, "en", "/data/question7")
            self.assert_question_label("", 0, 0, "en", "/data/blank_value_node")
        if fra:
            self.assert_question_label("un < deux", 0, 0, "fra", "/data/question2")
            self.assert_question_label("question3's label", 0, 0, "fra", "/data/question3")

        # Test markdown
        if en:
            self.assert_question_label("add_markdown: ~~new \\u0939\\u093f markdown~~", 0, 0,
                                       "en", "/data/add_markdown")
            self.assert_question_label("## smaller_markdown", 0, 0,
                                       "en", "/data/update_markdown")
            self.assert_question_label("no longer markdown", 0, 0,
                                       "en", "/data/remove_markdown")
            self.assert_question_label("*i just happen to like stars a lot*", 0, 0,
                                       "en", "/data/vetoed_markdown")

        # Validate entire form
        form = self.app.get_module(0).get_form(0)
        if en:
            if fra:
                self.assertXmlEqual(self.get_xml("change_upload_form"), form.render_xform())
            else:
                self.assertXmlEqual(self.get_xml("change_upload_form_en"), form.render_xform())

    def test_change_upload_multi_sheet(self):
        self.upload_raw_excel_translations(self.multi_sheet_upload_headers, self.multi_sheet_upload_data)
        self._test_change_upload(['en', 'fra'])

    def test_change_upload_single_sheet(self):
        self.upload_raw_excel_translations(self.single_sheet_upload_headers,
                                           self.single_sheet_upload_data, lang='en')
        self._test_change_upload(['en'])

    def test_missing_itext(self):
        self.app = Application.wrap(self.get_json("app_no_itext"))
        self.assert_question_label('question1', 0, 0, "en", "/data/question1")
        try:
            self.upload_raw_excel_translations(self.multi_sheet_upload_headers,
                                               self.multi_sheet_upload_no_change_data)
        except Exception as e:
            self.fail(e)

    def test_bad_column_name(self):
        self.upload_raw_excel_translations(
            self.upload_headers_bad_column,
            self.multi_sheet_upload_data,
            expected_messages=[
                'Sheet "{}" has fewer columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra'.format(MODULES_AND_FORMS_SHEET_NAME),

                'Sheet "{}" has unrecognized columns. Sheet will '
                'be processed but will ignore the following columns: default-fra'.format(
                    MODULES_AND_FORMS_SHEET_NAME),

                'Sheet "menu1" has fewer columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra',

                'Sheet "menu1" has unrecognized columns. Sheet will '
                'be processed but will ignore the following columns: default-fra',
                "You must provide at least one translation of the case property 'name'",

                'Sheet "menu1_form1" has fewer columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra',

                'Sheet "menu1_form1" has unrecognized columns. Sheet will '
                'be processed but will ignore the following columns: default-fra',

                'App Translations Updated!'
            ]
        )

    def test_remove_description_from_case_property(self):
        row = {'case_property': 'words to keep (remove this)'}
        description = BulkAppTranslationModuleUpdater._remove_description_from_case_property(row)
        self.assertEqual(description, 'words to keep')

    def test_remove_description_from_case_property_multiple_parens(self):
        row = {'case_property': '(words (to) keep) (remove this)'}
        description = BulkAppTranslationModuleUpdater._remove_description_from_case_property(row)
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
                'be processed but will ignore the following columns: default-fra'.format(
                    MODULES_AND_FORMS_SHEET_NAME),

                'Sheet "menu1" has fewer columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra',

                'Sheet "menu1" has unrecognized columns. Sheet will '
                'be processed but will ignore the following columns: default-fra',
                "You must provide at least one translation of the case property 'name'",

                'Sheet "menu1_form1" has fewer columns than expected. Sheet '
                'will be processed but the following translations will be '
                'unchanged: default_fra',

                'Sheet "menu1_form1" has unrecognized columns. Sheet will '
                'be processed but will ignore the following columns: default-fra',

                "Error in menu1_form1: You must provide at least one translation for the label 'question1-label'.",

                'App Translations Updated!'
            ]
        )

    def test_form_submit_label_on_upload(self):
        form = self.app.get_module(0).get_form(0)
        form.submit_label = {'en': 'old label', 'fra': 'passé'}
        self.assertEqual(form.submit_label, {'en': 'old label', 'fra': 'passé'})

        # note changes on upload with new value
        self.upload_raw_excel_translations(self.multi_sheet_upload_headers, self.multi_sheet_upload_data)
        self.assertEqual(form.submit_label, {'en': 'new submit', 'fra': 'nouveau'})

    def test_submit_notification_label_on_upload(self):
        form = self.app.get_module(0).get_form(0)
        form.submit_notification_label = {'en': 'old submission label', 'fra': 'passé'}
        self.assertEqual(form.submit_notification_label, {'en': 'old submission label', 'fra': 'passé'})

        # note changes on upload with new value
        self.upload_raw_excel_translations(self.multi_sheet_upload_headers, self.multi_sheet_upload_data)
        self.assertEqual(form.submit_notification_label, {'en': 'new submit notification', 'fra': 'nouveau'})

    def test_case_search_labels_on_upload(self):
        module = self.app.get_module(0)

        # default values
        self.assertEqual(module.search_config.search_label.label, {'en': 'Search All Cases'})
        self.assertEqual(module.search_config.search_again_label.label, {'en': 'Search Again'})
        self.assertEqual(module.search_config.title_label, {})
        self.assertEqual(module.search_config.description, {})

        self.upload_raw_excel_translations(self.multi_sheet_upload_headers, self.multi_sheet_upload_data)

        self.assertEqual(module.search_config.search_label.label, {'en': 'Find a Mother', 'fra': 'Mère!'})
        self.assertEqual(module.search_config.search_again_label.label,
                         {'en': 'Find Another Mother', 'fra': 'Mère! Encore!'})
        self.assertEqual(module.search_config.title_label, {'en': 'Find a Mom', 'fra': 'Maman!'})
        self.assertEqual(module.search_config.description,
                         {'en': 'More information', 'fra': "Plus d'information"})


class BulkAppTranslationPartialsTest(BulkAppTranslationTestBase):

    multi_sheet_headers = (
        (MODULES_AND_FORMS_SHEET_NAME,
         ('Type', 'menu_or_form', 'default_en', 'image_en', 'audio_en', 'unique_id')),
        ('menu1',
         ('case_property', 'list_or_detail', 'default_en')),
        ('menu1_form1',
         ('label', 'default_en', 'image_en', 'audio_en', 'video_en'))
    )
    multi_sheet_upload = (
        (MODULES_AND_FORMS_SHEET_NAME,
         (('Menu', 'menu1', 'update_case module', '', '', 'update_case_module'),
          ('Form', 'menu1_form1', 'update_case form 0', '', '', 'update_case_form_0'))),
        ('menu1',
         (('name', 'list', 'Name'),
          ('yes', 'list', 'Yes'),
          ('yes', 'list', 'Yep'),
          ('no', 'list', 'No'),
          ('no', 'list', 'Nope'),
          ('name', 'detail', 'Name'),
          ('name', 'detail', 'Name'),
          ('name', 'detail', 'Name'))),
        ('menu1_form1', [])
    )

    def setUp(self):
        """
        Instantiate an app with AppFactory
        """
        super(BulkAppTranslationPartialsTest, self).setUp()

        factory = AppFactory(build_version='2.11.0')
        module1, form1 = factory.new_basic_module('update_case', 'person')
        factory.add_module_case_detail_column(module1, 'long', 'name', 'Name')
        factory.add_module_case_detail_column(module1, 'long', 'name', 'Name')
        factory.add_module_case_detail_column(module1, 'short', 'yes', 'Yes')
        factory.add_module_case_detail_column(module1, 'short', 'yes', 'Yep')
        factory.add_module_case_detail_column(module1, 'short', 'no', 'No')
        factory.add_module_case_detail_column(module1, 'short', 'no', 'Nope')
        self.app = factory.app


class MismatchedItextReferenceTest(BulkAppTranslationTestBaseWithApp):
    """
    Test the bulk app translation upload when the itext reference in a question
    in the xform body does not match the question's id/path.

    The upload is an unchanged download.
    """
    file_path = "data", "bulk_app_translation", "mismatched_ref"

    def test_unchanged_upload(self):
        headers = (
            (MODULES_AND_FORMS_SHEET_NAME, ('Type', 'menu_or_form', 'default_en', 'default_fra',
                                            'image_en', 'image_fra', 'audio_en', 'audio_fra', 'unique_id')),
            ('menu1', ('case_property', 'list_or_detail', 'default_en', 'default_fra')),
            ('menu1_form1', ('label', 'default_en', 'default_fra', 'image_en', 'image_fra',
                             'audio_en', 'audio_fra', 'video_en', 'video_fra')),
        )
        data = (
            (MODULES_AND_FORMS_SHEET_NAME,
             (('Menu', 'menu1', 'Untitled Module', '', '', '', '', '', 'ecdcc5bb280f043a23f39eca52369abaa9e49bf9'),
              ('Form', 'menu1_form1', 'Untitled Form', '', '', '', '', '',
               'e1af3f8e947dad9862a4d7c32f5490cfff9edfda'))),
            ('menu1',
             (('name', 'list', 'Name', ''),
              ('name', 'detail', 'Name', ''))),
            ('menu1_form1',
             (('foo-label', 'foo', 'foo', '', '', '', '', '', ''),
              ('question1/question2-label', 'question2', 'question2', '', '', '', '', '', ''),
              ('question1/question2-item1-label', 'item1', 'item1', '', '', '', '', '', ''),
              ('question1/question2-item2-label', 'item2', 'item2', '', '', '', '', '', ''),
              ('question1-label', 'question1', 'question1', '', '', '', '', '', ''),
              ('question1/question2-label2', 'bar', 'bar', '', '', '', '', '', ''))),
        )

        self.upload_raw_excel_translations(headers, data)
        self.assert_question_label("question2", 0, 0, "en", "/data/foo/question2")


class MovedModuleTest(BulkAppTranslationTestBaseWithApp):
    """
    Test the bulk app translation upload when the itext reference in a question
    in the xform body does not match the question's id/path.

    The upload is an unchanged download.
    """
    file_path = "data", "bulk_app_translation", "moved_module"

    def test_moved_module(self):
        self.upload_raw_excel_translations(EXCEL_HEADERS, EXCEL_DATA)
        self.assert_question_label("What does this look like?", 1, 0, "en", "/data/What_does_this_look_like")


class MovedFormTest(BulkAppTranslationTestBaseWithApp):
    """
    Test the bulk app translation upload when a form is moved to a
    different module, resulting in different expected headers.
    """
    file_path = "data", "bulk_app_translation", "moved_module"

    def test_moved_form(self):
        headers = (
            (MODULES_AND_FORMS_SHEET_NAME, ('Type', 'menu_or_form', 'default_en', 'image_en', 'audio_en', 'unique_id')),  # noqa: E501
            ('menu1', ('case_property', 'list_or_detail', 'default_en')),
            ('menu1_form1', ('label', 'default_en', 'image_en', 'audio_en', 'video_en')),
            # was menu6_form1:
            ('menu1_form2', ('label', 'default_en', 'image_en', 'audio_en', 'video_en')),
            ('menu2', ('case_property', 'list_or_detail', 'default_en')),
            ('menu2_form1', ('label', 'default_en', 'image_en', 'audio_en', 'video_en')),
            ('menu3', ('case_property', 'list_or_detail', 'default_en')),
            ('menu3_form1', ('label', 'default_en', 'image_en', 'audio_en', 'video_en')),
            ('menu4', ('case_property', 'list_or_detail', 'default_en')),
            ('menu4_form1', ('label', 'default_en', 'image_en', 'audio_en', 'video_en')),
            ('menu5', ('case_property', 'list_or_detail', 'default_en')),
            ('menu6', ('case_property', 'list_or_detail', 'default_en')),
        )
        data = (
            (MODULES_AND_FORMS_SHEET_NAME, (
                ('Menu', 'menu1', 'Stethoscope', 'jr://file/commcare/image/module0.png', '', '58ce5c9cf6eda401526973773ef216e7980bc6cc'),  # noqa: E501
                ('Form', 'menu1_form1', 'Stethoscope Form', 'jr://file/commcare/image/module0_form0.png', '', 'c480ace490edc870ae952765e8dfacec33c69fec'),  # noqa: E501
                # was menu6_form1:
                ('Form', 'menu1_form2', 'Advanced Form', '', '', '2b9c856ba2ea4ec1ab8743af299c1627'),
                # was menu6_form2:
                ('Form', 'menu1_form3', 'Shadow Form', '', '', 'c42e1a50123c43f2bd1e364f5fa61379'),
                ('Menu', 'menu2', 'Register Series', '', '', 'b9c25abe21054632a3623199debd7cfa'),
                ('Form', 'menu2_form1', 'Registration Form', '', '', '280b1b06d1b442b9bba863453ba30bc3'),
                ('Menu', 'menu3', 'Followup Series', '', '', '217e1c8de3dd46f98c7d2806bc19b580'),
                ('Form', 'menu3_form1', 'Add Point to Series', '', '', 'a01b55fd2c1a483492c1166029946249'),
                ('Menu', 'menu4', 'Remove Point', '', '', '17195132472446ed94bd91ba19a2b379'),
                ('Form', 'menu4_form1', 'Remove Point', '', '', '98458acd899b4d5f87df042a7585e8bb'),
                ('Menu', 'menu5', 'Empty Reports Module', '', '', '703eb807ae584d1ba8bf9457d7ac7590'),
                ('Menu', 'menu6', 'Advanced Module', '', '', '7f75ed4c15be44509591f41b3d80746e'),
            )),
            ('menu1', (
                ('case_list_menu_item_label', 'list', 'Steth List'),
                ('name', 'list', 'Name'),
                ('name', 'detail', 'Name')
            )),
            ('menu1_form1', (
                ('What_does_this_look_like-label', 'What does this look like?', 'jr://file/commcare/image/data/What_does_this_look_like.png', '', ''),  # noqa: E501
                ('no_media-label', 'No media', '', '', ''),
                ('has_refs-label', 'Here is a ref <output value="/data/no_media"/> with some trailing text and "bad" &lt; xml.', '', '', '')  # noqa: E501
            )),
            # was menu6_form1:
            ('menu1_form2', (
                ('this_form_does_nothing-label', 'This form does nothing.', '', '', ''),
            )),
            ('menu2', (
                ('name', 'list', 'Name'), ('name', 'detail', 'Name')
            )),
            ('menu2_form1', (
                ('name_of_series-label', 'Name of series', '', '', '')
            )),
            ('menu3', (
                ('name', 'list', 'Name'),
                ('Tab 0', 'detail', 'Name'),
                ('Tab 1', 'detail', 'Graph'),
                ('name', 'detail', 'Name'),
                ('line_graph (graph)', 'detail', 'Line Graph'),
                ('secondary-y-title (graph config)', 'detail', ''),
                ('x-title (graph config)', 'detail', 'xxx'),
                ('y-title (graph config)', 'detail', 'yyy'),
                ('x-name 0 (graph series config)', 'detail', 'xxx'),
                ('name 0 (graph series config)', 'detail', 'yyy'),
                ('graph annotation 1', 'detail', 'This is (2, 2)')
            )),
            ('menu3_form1', (
                ('x-label', 'x', '', '' ''),
                ('y-label', 'y', '', '', '')
            )),
            ('menu4', (
                ('x', 'list', 'X'),
                ('y', 'list', 'Y'),
                ('x (ID Mapping Text)', 'detail', 'X Name'),
                ('1 (ID Mapping Value)', 'detail', 'one'),
                ('2 (ID Mapping Value)', 'detail', 'two'),
                ('3 (ID Mapping Value)', 'detail', 'three')
            )),
            ('menu4_form1', (
                ('confirm_remove-label', 'Swipe to remove the point at (<output value="instance(\'casedb\')/casedb/case[@case_id = instance(\'commcaresession\')/session/data/case_id]/x"/>  ,<output value="instance(\'casedb\')/casedb/case[@case_id = instance(\'commcaresession\')/session/data/case_id]/y"/>).')  # noqa: E501
            )),
            ('menu5', ()),
            ('menu6', (
                ('name', 'list', 'Name'),
                ('name', 'detail', 'Name'),
            )),
        )
        expected_messages = [
            'App Translations Updated!',
        ]
        self.upload_raw_excel_translations(headers, data, expected_messages=expected_messages)


class BulkAppTranslationFormTest(BulkAppTranslationTestBaseWithApp):

    file_path = "data", "bulk_app_translation", "form_modifications"

    def test_removing_form_translations(self):
        headers = (
            (MODULES_AND_FORMS_SHEET_NAME, ('Type', 'menu_or_form', 'default_en', 'default_fra',
                                            'image_en', 'image_fra', 'audio_en', 'audio_fra', 'unique_id')),
            ('menu1', ('case_property', 'list_or_detail', 'default_en', 'default_fra')),
            ('menu1_form1', ('label', 'default_en', 'default_fra', 'image_en', 'image_fra',
                             'audio_en', 'audio_fra', 'video_en', 'video_fra')),
        )
        data = (
            (MODULES_AND_FORMS_SHEET_NAME,
             (('Menu', 'menu1', 'Untitled Module', '', '', '', '', '', '765f110eb62fd26240a6d8bcdccca91b246b96c9'),
              ('Form', 'menu1_form1', 'Untitled Form', '', '', '', '', '',
               'fffea2c32b7902a3efcb6b84c94e824820d11856'))),
            ('menu1',
             (('name', 'list', 'Name', ''),
              ('name', 'detail', 'Name', ''))),
            ('menu1_form1',
             (('question1-label', '', 'french', '', 'jr://file/commcare/image/data/question1.png', '', '', '', ''),
              ('question2-label', 'english', '', 'jr://file/commcare/image/data/question2.png', '', '', '',
               '', ''),
              ('question3-label', '', '', '', '', '', '', '', ''))),
        )

        self.upload_raw_excel_translations(headers, data)
        form = self.app.get_module(0).get_form(0)
        self.assertXmlEqual(self.get_xml("expected_form"), form.render_xform())


class BulkAppTranslationDownloadTest(SimpleTestCase, TestXmlMixin):
    root = os.path.dirname(__file__)
    file_path = ('data', 'bulk_app_translation', 'download')
    maxDiff = None

    excel_headers = EXCEL_HEADERS
    excel_data = EXCEL_DATA

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
        self.assertEqual(get_module_sheet_name(self.app.modules[0]), "menu1")
        self.assertEqual(get_form_sheet_name(self.app.modules[0].forms[0]), "menu1_form1")

    def test_sheet_headers(self):
        self.assertListEqual(get_bulk_app_sheet_headers(self.app), [
            [MODULES_AND_FORMS_SHEET_NAME, ['Type', 'menu_or_form', 'default_en',
             'image_en', 'audio_en', 'unique_id']],
            ['menu1', ['case_property', 'list_or_detail', 'default_en']],
            ['menu1_form1', ['label', 'default_en', 'image_en', 'audio_en', 'video_en']],
            ['menu2', ['case_property', 'list_or_detail', 'default_en']],
            ['menu2_form1', ['label', 'default_en', 'image_en', 'audio_en', 'video_en']],
            ['menu3', ['case_property', 'list_or_detail', 'default_en']],
            ['menu3_form1', ['label', 'default_en', 'image_en', 'audio_en', 'video_en']],
            ['menu4', ['case_property', 'list_or_detail', 'default_en']],
            ['menu4_form1', ['label', 'default_en', 'image_en', 'audio_en', 'video_en']],
            ['menu5', ['case_property', 'list_or_detail', 'default_en']],
            ['menu6', ['case_property', 'list_or_detail', 'default_en']],
            ['menu6_form1', ['label', 'default_en', 'image_en', 'audio_en', 'video_en']],
        ])

        self.assertEqual(get_bulk_app_sheet_headers(self.app, single_sheet=True, lang='fra'),
            ((SINGLE_SHEET_NAME, ('menu_or_form', 'case_property', 'list_or_detail', 'label',
                                  'default_fra', 'image_fra', 'audio_fra', 'video_fra', 'unique_id')),))

    def test_module_case_list_form_rows(self):
        app = AppFactory.case_list_form_app_factory().app
        self.assertEqual(get_module_case_list_form_rows(app.langs, app.modules[0]),
                         [('case_list_form_label', 'list', 'New Case')])

    def test_module_case_list_menu_item_rows(self):
        self.assertEqual(get_module_case_list_menu_item_rows(self.app.langs, self.app.modules[0]),
                         [('case_list_menu_item_label', 'list', 'Steth List')])

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_module_search_labels_rows(self):
        app = AppFactory.case_claim_app_factory().app
        self.assertEqual(get_module_search_command_rows(app.langs, app.modules[0], app.domain),
                         [('search_label', 'list', 'Find a Mother'),
                          ('title_label', 'list', 'Find a Mom'),
                          ('description', 'list', 'More information'),
                          ('search_again_label', 'list', 'Find Another Mother')])

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    @flag_enabled('SPLIT_SCREEN_CASE_SEARCH')
    def test_module_split_screen_case_search_rows(self):
        app = AppFactory.case_claim_app_factory().app
        self.assertEqual(get_module_search_command_rows(app.langs, app.modules[0], app.domain),
                         [('search_label', 'list', 'Find a Mother'),
                          ('title_label', 'list', 'Find a Mom'),
                          ('description', 'list', 'More information')])

    @flag_enabled('SYNC_SEARCH_CASE_CLAIM')
    def test_module_case_search_rows(self):
        app = AppFactory.case_claim_app_factory().app
        self.assertEqual(get_case_search_rows(app.langs, app.modules[0], self.app.domain),
                         [('name', 'case_search_display', 'Name of Mother'),
                          ('name', 'case_search_hint', '')])

    @patch.object(Application, 'supports_empty_case_list_text', lambda: True)
    def test_module_detail_rows(self):
        self.assertListEqual(get_module_detail_rows(self.app.langs, self.app.modules[0]), [
            ('no_items_text', 'list', 'Empty List'),
            ('select_text', 'list', 'Continue'),
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

        self.assertListEqual(get_form_question_label_name_media([lang], form), [
            ['What_does_this_look_like-label', 'What does this look like?',
             'jr://file/commcare/image/data/What_does_this_look_like.png', '', ''],
            ['no_media-label', 'No media',
             '', '', ''],
            ['has_refs-label',
             'Here is a ref <output value="/data/no_media"/> with some trailing text and "bad" &lt; xml.',
             '', '', ''],
            ['submit_label', 'Submit', '', '', ''],
            ['submit_notification_label', '', '', '', '']
        ])

    @patch.object(Application, 'supports_empty_case_list_text', lambda: True)
    def test_bulk_app_sheet_rows(self):
        actual_headers = get_bulk_app_sheet_headers(self.app)
        actual_sheets = get_bulk_app_sheets_by_name(self.app)

        actual_workbook = [
            {'name': title,
             'rows': [dict(zip(headers, row)) for row in actual_sheets[title]]}
            for title, headers in actual_headers
        ]

        for actual_sheet, expected_sheet in zip(actual_workbook,
                                                self.expected_workbook):
            self.assertEqual(actual_sheet, expected_sheet)
        self.assertEqual(actual_workbook, self.expected_workbook)

    def test_bulk_app_sheet_blacklisted(self):

        def blacklist_without_display_text(self):
            menu1_id = self.app.modules[0].unique_id
            return {self.app.domain: {self.app.id: {menu1_id: {'detail': {'name': {'': True}}}}}}

        with patch.object(EligibleForTransifexChecker, 'is_label_to_skip', lambda foo, bar, baz: False), \
                patch.object(EligibleForTransifexChecker, '_get_blacklist', blacklist_without_display_text):
            menu1_sheet = get_bulk_app_sheets_by_name(self.app, eligible_for_transifex_only=True)['menu1']
        self.assertNotIn(('name', 'detail', 'Name'), menu1_sheet)
        self.assertIn(('name', 'list', 'Name'), menu1_sheet)

    def test_bulk_app_sheet_blacklisted_text(self):

        def blacklist_with_display_text(self):
            menu1_id = self.app.modules[0].unique_id
            return {self.app.domain: {self.app.id: {menu1_id: {'detail': {'name': {'Name': True}}}}}}

        with patch.object(EligibleForTransifexChecker, 'is_label_to_skip', lambda foo, bar, baz: False), \
                patch.object(EligibleForTransifexChecker, '_get_blacklist', blacklist_with_display_text):
            menu1_sheet = get_bulk_app_sheets_by_name(self.app, eligible_for_transifex_only=True)['menu1']
        self.assertNotIn(('name', 'detail', 'Name'), menu1_sheet)
        self.assertIn(('name', 'list', 'Name'), menu1_sheet)

    def test_bulk_app_sheet_skipped_label(self):

        def get_labels_to_skip(self):
            menu1_form1_id = self.app.modules[0].forms[0].unique_id
            return defaultdict(set, {menu1_form1_id: {'What_does_this_look_like-label'}})

        with patch.object(EligibleForTransifexChecker, 'get_labels_to_skip', get_labels_to_skip), \
                patch.object(EligibleForTransifexChecker, '_get_blacklist', lambda self: {}):
            menu1_form1_sheet = get_bulk_app_sheets_by_name(self.app,
                                                            eligible_for_transifex_only=True)['menu1_form1']
        self.assertNotIn(['What_does_this_look_like-label', 'What does this look like?',
                          'jr://file/commcare/image/data/What_does_this_look_like.png', '', ''], menu1_form1_sheet)
        self.assertIn(['no_media-label', 'No media', '', '', ''], menu1_form1_sheet)

    def test_bulk_app_single_sheet_rows(self):
        sheet = get_bulk_app_single_sheet_by_name(self.app, self.app.langs[0])[SINGLE_SHEET_NAME]
        self.assertListEqual(sheet, [
            ['menu1', '', '', '', 'Stethoscope', 'jr://file/commcare/image/module0.png', None, '',
             '58ce5c9cf6eda401526973773ef216e7980bc6cc'],
            ['menu1', 'case_list_menu_item_label', 'list', '', 'Steth List', '', '', '', ''],
            ['menu1', 'select_text', 'list', '', 'Continue', '', '', '', ''],
            ['menu1', 'name', 'list', '', 'Name', '', '', '', ''],
            ['menu1', 'name', 'detail', '', 'Name', '', '', '', ''],

            ['menu1_form1', '', '', '', 'Stethoscope Form', 'jr://file/commcare/image/module0_form0.png', None, '',
             'c480ace490edc870ae952765e8dfacec33c69fec'],
            ['menu1_form1', '', '', 'What_does_this_look_like-label', 'What does this look like?',
             'jr://file/commcare/image/data/What_does_this_look_like.png', '', '', ''],
            ['menu1_form1', '', '', 'no_media-label', 'No media', '', '', '', ''],
            ['menu1_form1', '', '', 'has_refs-label',
             'Here is a ref <output value="/data/no_media"/> with some trailing text and "bad" &lt; xml.', '', '',
             '', ''],
            ['menu1_form1', '', '', 'submit_label', 'Submit', '', '', '', ''],
            ['menu1_form1', '', '', 'submit_notification_label', '', '', '', '', ''],

            ['menu2', '', '', '', 'Register Series', '', '', '', 'b9c25abe21054632a3623199debd7cfa'],
            ['menu2', 'select_text', 'list', '', 'Continue', '', '', '', ''],
            ['menu2', 'name', 'list', '', 'Name', '', '', '', ''],
            ['menu2', 'name', 'detail', '', 'Name', '', '', '', ''],

            ['menu2_form1', '', '', '', 'Registration Form', None, None, '', '280b1b06d1b442b9bba863453ba30bc3'],
            ['menu2_form1', '', '', 'name_of_series-label', 'Name of series', '', '', '', ''],
            ['menu2_form1', '', '', 'submit_label', 'Submit', '', '', '', ''],
            ['menu2_form1', '', '', 'submit_notification_label', '', '', '', '', ''],

            ['menu3', '', '', '', 'Followup Series', '', '', '', '217e1c8de3dd46f98c7d2806bc19b580'],
            ['menu3', 'select_text', 'list', '', 'Continue', '', '', '', ''],
            ['menu3', 'name', 'list', '', 'Name', '', '', '', ''],
            ['menu3', 'Tab 0', 'detail', '', 'Name', '', '', '', ''],
            ['menu3', 'Tab 1', 'detail', '', 'Graph', '', '', '', ''],
            ['menu3', 'name', 'detail', '', 'Name', '', '', '', ''],
            ['menu3', 'line_graph (graph)', 'detail', '', 'Line Graph', '', '', '', ''],
            ['menu3', 'secondary-y-title (graph config)', 'detail', '', '', '', '', '', ''],
            ['menu3', 'x-title (graph config)', 'detail', '', 'xxx', '', '', '', ''],
            ['menu3', 'y-title (graph config)', 'detail', '', 'yyy', '', '', '', ''],
            ['menu3', 'x-name 0 (graph series config)', 'detail', '', 'xxx', '', '', '', ''],
            ['menu3', 'name 0 (graph series config)', 'detail', '', 'yyy', '', '', '', ''],
            ['menu3', 'graph annotation 1', 'detail', '', 'This is (2, 2)', '', '', '', ''],

            ['menu3_form1', '', '', '', 'Add Point to Series', None, None, '', 'a01b55fd2c1a483492c1166029946249'],
            ['menu3_form1', '', '', 'x-label', 'x', '', '', '', ''],
            ['menu3_form1', '', '', 'y-label', 'y', '', '', '', ''],
            ['menu3_form1', '', '', 'submit_label', 'Submit', '', '', '', ''],
            ['menu3_form1', '', '', 'submit_notification_label', '', '', '', '', ''],

            ['menu4', '', '', '', 'Remove Point', '', '', '', '17195132472446ed94bd91ba19a2b379'],
            ['menu4', 'select_text', 'list', '', 'Continue', '', '', '', ''],
            ['menu4', 'x', 'list', '', 'X', '', '', '', ''],
            ['menu4', 'y', 'list', '', 'Y', '', '', '', ''],
            ['menu4', 'x (ID Mapping Text)', 'detail', '', 'X Name', '', '', '', ''],
            ['menu4', '1 (ID Mapping Value)', 'detail', '', 'one', '', '', '', ''],
            ['menu4', '2 (ID Mapping Value)', 'detail', '', 'two', '', '', '', ''],
            ['menu4', '3 (ID Mapping Value)', 'detail', '', 'three', '', '', '', ''],

            ['menu4_form1', '', '', '', 'Remove Point', None, None, '', '98458acd899b4d5f87df042a7585e8bb'],
            ['menu4_form1', '', '', 'confirm_remove-label', 'Swipe to remove the point at '
             '(<output value="instance(\'casedb\')/casedb/case[@case_id = instance(\'commcaresession\')/'
             'session/data/case_id]/x"/>  ,<output value="instance(\'casedb\')/casedb/case[@case_id = '
             'instance(\'commcaresession\')/session/data/case_id]/y"/>).', '', '', '', ''],
            ['menu4_form1', '', '', 'submit_label', 'Submit', '', '', '', ''],
            ['menu4_form1', '', '', 'submit_notification_label', '', '', '', '', ''],

            ['menu5', '', '', '', 'Empty Reports Module', '', '', '', '703eb807ae584d1ba8bf9457d7ac7590'],

            ['menu6', '', '', '', 'Advanced Module', None, None, '', '7f75ed4c15be44509591f41b3d80746e'],
            ['menu6', 'select_text', 'list', '', 'Continue with Case(s)', '', '', '', ''],
            ['menu6', 'name', 'list', '', 'Name', '', '', '', ''],
            ['menu6', 'name', 'detail', '', 'Name', '', '', '', ''],

            ['menu6_form1', '', '', '', 'Advanced Form', None, None, '', '2b9c856ba2ea4ec1ab8743af299c1627'],
            ['menu6_form1', '', '', 'this_form_does_nothing-label', 'This form does nothing.', '', '', '', ''],
            ['menu6_form1', '', '', 'submit_label', 'Submit', '', '', '', ''],
            ['menu6_form1', '', '', 'submit_notification_label', '', '', '', '', ''],
            ['menu6_form2', '', '', '', 'Shadow Form', '', '', '', 'c42e1a50123c43f2bd1e364f5fa61379']])

    def test_bulk_app_single_sheet_blacklisted(self):

        def blacklist_without_display_text(self):
            menu1_id = self.app.modules[0].unique_id
            return {self.app.domain: {self.app.id: {menu1_id: {'detail': {'name': {'': True}}}}}}

        with patch.object(EligibleForTransifexChecker, 'is_label_to_skip', lambda foo, bar, baz: False), \
                patch.object(EligibleForTransifexChecker, '_get_blacklist', blacklist_without_display_text):
            sheet = get_bulk_app_single_sheet_by_name(self.app, self.app.langs[0],
                                                      eligible_for_transifex_only=True)[SINGLE_SHEET_NAME]
        self.assertNotIn(['menu1', 'name', 'detail', '', 'Name', '', '', '', ''], sheet)
        self.assertIn(['menu1', 'name', 'list', '', 'Name', '', '', '', ''], sheet)

    def test_bulk_app_single_sheet_blacklisted_text(self):

        def blacklist_with_display_text(self):
            menu1_id = self.app.modules[0].unique_id
            return {self.app.domain: {self.app.id: {menu1_id: {'detail': {'name': {'Name': True}}}}}}

        with patch.object(EligibleForTransifexChecker, 'is_label_to_skip', lambda foo, bar, baz: False), \
                patch.object(EligibleForTransifexChecker, '_get_blacklist', blacklist_with_display_text):
            sheet = get_bulk_app_single_sheet_by_name(self.app, self.app.langs[0],
                                                      eligible_for_transifex_only=True)[SINGLE_SHEET_NAME]
        self.assertNotIn(['menu1', 'name', 'detail', '', 'Name', '', '', '', ''], sheet)
        self.assertIn(['menu1', 'name', 'list', '', 'Name', '', '', '', ''], sheet)

    def test_bulk_app_single_sheet_skipped_label(self):

        def get_labels_to_skip(self):
            menu1_form1_id = self.app.modules[0].forms[0].unique_id
            return defaultdict(set, {menu1_form1_id: {'What_does_this_look_like-label'}})

        with patch.object(EligibleForTransifexChecker, 'get_labels_to_skip', get_labels_to_skip), \
                patch.object(EligibleForTransifexChecker, '_get_blacklist', lambda self: {}):
            sheet = get_bulk_app_single_sheet_by_name(self.app, self.app.langs[0],
                                                      eligible_for_transifex_only=True)[SINGLE_SHEET_NAME]
        self.assertNotIn(['menu1_form1', '', '', 'What_does_this_look_like-label', 'What does this look like?',
             'jr://file/commcare/image/data/What_does_this_look_like.png', '', '', ''], sheet)
        self.assertIn(['menu1_form1', '', '', 'no_media-label', 'No media', '', '', '', ''], sheet)


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
    root = os.path.dirname(__file__)

    file_path = ('data', 'bulk_app_translation', 'aggregate')

    headers = (
        (MODULES_AND_FORMS_SHEET_NAME, (
            'Type', 'menu_or_form',
            'default_en', 'default_afr', 'default_fra',
            'image_en', 'image_afr', 'image_fra',
            'audio_en', 'audio_afr', 'audio_fra',
            'unique_id'
        )),
        ('menu1', (
            'case_property', 'list_or_detail', 'default_en', 'default_fra', 'default_fra'
        )),
        ('menu1_form1', (
            'label',
            'default_en', 'default_afr', 'default_fra',
            'audio_en', 'audio_afr', 'audio_fra',
            'image_en', 'image_afr', 'image_fra',
            'video_en', 'video_afr', 'video_fra',
        ))
    )
    data = (
        (MODULES_AND_FORMS_SHEET_NAME,
         (('Menu', 'menu1',
           'Untitled Module', 'Ongetitelde Module', 'Module Sans Titre',
           '', '', '',
           '', '', '',
           'deadbeef'),
          ('Form', 'menu1_form1',
           'Untitled Form', 'Ongetitelde Form', 'Formulaire Sans Titre',
           '', '', '',
           '', '', '',
           'c0ffee'))),

        ('menu1',
         (('name', 'list', 'Name', 'Naam', 'Nom'),
          ('name', 'detail', 'Name', 'Naam', 'Nom'))),

        ('menu1_form1',
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

        self.form1_worksheet = self.get_worksheet('menu1_form1')

    def test_markdown_node(self):
        """
        If one translation has a Markdown node, the label should be a Markdown label
        If Markdown is vetoed for one language, it should be vetoed for the label
        """
        sheet = self.form1_worksheet
        with patch('corehq.apps.translations.app_translations.upload_form.save_xform') as save_xform_patch:
            names_map = {}
            updater = BulkAppTranslationFormUpdater(self.app, sheet.worksheet.title, names_map)
            msgs = updater.update(sheet)
            self.assertEqual(msgs, [])
            expected_xform = self.get_xml('expected_xform').decode('utf-8')
            self.maxDiff = None
            self.assertEqual(save_xform_patch.call_args[0][2].decode('utf-8'), expected_xform)


class ReportModuleTest(BulkAppTranslationTestBase):
    headers = [
        ['Menus_and_forms', ['Type', 'menu_or_form', 'default_en', 'image_en', 'audio_en', 'unique_id']],
        ['menu1', ['case_property', 'list_or_detail', 'default_en']],
    ]

    def setUp(self):
        factory = AppFactory(build_version='2.43.0')
        module = factory.new_report_module('reports')
        module.report_configs = [
            ReportAppConfig(
                report_id='123abc',
                header={"en": "My Report"},
                localized_description={"en": "This report has data"},
                use_xpath_description=False,
                uuid='789ghi',
            ),
            ReportAppConfig(
                report_id='123abc',
                header={"en": "My Other Report"},
                localized_description={"en": "do not use this"},
                xpath_description="1 + 2",
                use_xpath_description=True,
                uuid='345cde',
            ),
        ]
        self.app = factory.app

    def test_download(self):
        actual_headers = get_bulk_app_sheet_headers(self.app)
        actual_sheets = get_bulk_app_sheets_by_name(self.app)

        self.assertEqual(actual_headers, self.headers)
        self.assertEqual(actual_sheets, OrderedDict({
            'Menus_and_forms': [['Menu', 'menu1', 'reports module', '', '', 'reports_module']],
            'menu1': [
                ('Report 0 Display Text', 'list', 'My Report'),
                ('Report 0 Description', 'list', 'This report has data'),
                ('Report 1 Display Text', 'list', 'My Other Report'),
            ]
        }))

    def test_upload(self):
        data = (
            ("Menus_and_forms", ('Menu', 'menu1', 'reports module', '', '', 'reports_module')),
            ("menu1", (('Report 0 Display Text', 'list', 'My Report has changed'),
                       ('Report 0 Description', 'list', 'This report still has data'),
                       ('Report 1 Display Text', 'list', 'My Other Report has also changed'),
                       ('Report 1 Description', 'list', 'You cannot update this'))),
        )
        messages = [
            "Found row for Report 1 Description, but this report uses an xpath description, "
            "which is not localizable. Description not updated.",
            "App Translations Updated!",
        ]
        self.upload_raw_excel_translations(self.app, self.headers, data, expected_messages=messages)
        module = self.app.get_module(0)
        self.assertEqual(module.report_configs[0].header, {"en": "My Report has changed"})
        self.assertEqual(module.report_configs[0].localized_description, {"en": "This report still has data"})
        self.assertEqual(module.report_configs[1].header, {"en": "My Other Report has also changed"})

    def test_upload_unexpected_reports(self):
        data = (
            ("Menus_and_forms", ('Menu', 'menu1', 'reports module', '', '', 'reports_module')),
            ("menu1", (('Report 0 Display Text', 'list', 'My Report has changed'),
                       ('Report 3 Display Text', 'list', 'This is not a real report'))),
        )
        messages = [
            "Expected 2 reports for menu 1 but found row for Report 3. No changes were made for menu 1.",
            "App Translations Updated!",
        ]
        self.upload_raw_excel_translations(self.app, self.headers, data, expected_messages=messages)
        module = self.app.get_module(0)
        self.assertEqual(module.report_configs[0].header, {"en": "My Report"})

    def test_upload_unexpected_rows(self):
        data = (
            ("Menus_and_forms", ('Menu', 'menu1', 'reports module', '', '', 'reports_module')),
            ("menu1", (('Report 0 Display Text', 'list', 'My Report has changed'),
                       ('some other thing', 'list', 'this is not report-related'))),
        )
        messages = [
            "Found unexpected row \"some other thing\" for menu 1. No changes were made for menu 1.",
            "App Translations Updated!",
        ]
        self.upload_raw_excel_translations(self.app, self.headers, data, expected_messages=messages)
        module = self.app.get_module(0)
        self.assertEqual(module.report_configs[0].header, {"en": "My Report"})
