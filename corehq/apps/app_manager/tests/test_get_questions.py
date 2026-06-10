import os

from django.template.loader import render_to_string
from django.test.testcases import SimpleTestCase

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.util import generate_xmlns
from corehq.apps.app_manager.xform import XForm
from corehq.util.test_utils import TestFileMixin

QUESTIONS = [
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'constraintMsg_ref': 'question1-constraintMsg',
        'value': '/data/question1',
        'hashtagValue': '#form/question1',
        'label': 'label en ____ label en',
        'label_ref': 'question1-label',
        'translations': {
            'en': 'label en ____ label en',
            'es': 'label es ____\n____\n____',
        },
        'type': 'Text',
        'required': False,
        'relevant': ("instance('casedb')/casedb/case[@case_id=instance('casedb')/casedb/case["
                     "@case_id=instance('commcaresession')/session/data/case_id]/index/parent"
                     "]/parent_property_1 + 1 + "
                     "instance('casedb')/casedb/case[@case_id=instance('casedb')/casedb/case["
                     "@case_id=instance('commcaresession')/session/data/case_id]/index/parent"
                     "]/parent_property_1"),
        'constraint': (
            "1 + instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]"
            "/child_property_1"
        ),
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/question2',
        'hashtagValue': '#form/question2',
        'label': 'label en ____ label en',
        'label_ref': 'question2-label',
        'translations': {'en': 'label en ____ label en'},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': "This is a comment",
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/question3',
        'hashtagValue': '#form/question3',
        'label': 'no references here!',
        'label_ref': 'question3-label',
        'translations': {'en': 'no references here!'},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'trigger',
        'repeat': None,
        'group': None,
        'value': '/data/hi',
        'hashtagValue': '#form/hi',
        'label': 'woo',
        'label_ref': 'hi-label',
        'translations': {'en': 'woo'},
        'type': 'Trigger',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'input',
        'repeat': '/data/question15',
        'group': '/data/question15',
        'value': '/data/question15/question16',
        'hashtagValue': '#form/question15/question16',
        'label': None,
        'label_ref': 'question16-label',
        'translations': {},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': '1',
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'select1',
        'repeat': '/data/question15',
        'group': '/data/question15',
        'options': [
            {
                'value': 'item22',
                'label': None,
                'label_ref': 'question21-item22-label',
                'translations': {},
            }
        ],
        'value': '/data/question15/question21',
        'hashtagValue': '#form/question15/question21',
        'label': None,
        'label_ref': 'question21-label',
        'translations': {},
        'type': 'Select',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'input',
        'repeat': '/data/question15',
        'group': '/data/question15',
        'value': '/data/question15/question25',
        'hashtagValue': '#form/question15/question25',
        'label': None,
        'label_ref': 'question25-label',
        'translations': {},
        'type': 'Int',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/thing',
        'hashtagValue': '#form/thing',
        'label': None,
        'label_ref': 'thing-label',
        'translations': {},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'hidden',
        'repeat': None,
        'group': None,
        'value': '/data/datanode',
        'hashtagValue': '#form/datanode',
        'label': '#form/datanode',
        'translations': {},
        'type': 'DataBindOnly',
        'relevant': None,
        'calculate': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
    },
]


class AppFormTestCase(SimpleTestCase, TestFileMixin):
    """Base for tests that build an app with one module and add forms to it
    from XML data files."""

    domain = 'test-domain'

    file_path = ('data',)
    root = os.path.dirname(__file__)

    maxDiff = None

    def setUp(self):
        self.app = Application.new_app(self.domain, "Test")
        self.app.add_module(Module.new_module("Module", 'en'))
        self.module = self.app.get_module(0)
        self.module.case_type = 'test'

    def add_form(self, data_file, name=None):
        return self.app.new_form(
            self.module.id,
            name=name or data_file,
            lang='en',
            attachment=self.get_xml(data_file).decode('utf-8'),
        )


class GetFormQuestionsTest(AppFormTestCase):

    def setUp(self):
        super().setUp()
        self.form_unique_id = self.add_form('case_in_form', "Form").unique_id
        self.form_with_repeats_unique_id = self.add_form(
            'form_with_repeats', "Form with repeats").unique_id

    def test_get_questions(self):
        form = self.app.get_form(self.form_unique_id)
        questions = form.wrapped_xform().get_questions(['en', 'es'], include_translations=True)

        non_label_questions = [
            q for q in QUESTIONS if q['tag'] not in ('label', 'trigger')]

        self.assertEqual(questions, non_label_questions)

    def test_get_questions_with_triggers(self):
        form = self.app.get_form(self.form_unique_id)
        questions = form.wrapped_xform().get_questions(
            ['en', 'es'], include_triggers=True, include_translations=True)

        self.assertEqual(questions, QUESTIONS)

    def test_get_questions_with_locked_status(self):
        form = self.app.get_form(self.form_unique_id)
        questions = form.wrapped_xform().get_questions(['en'], include_locked_status=True)

        locked_question = [q for q in questions if q['value'] == '/data/question2'][0]
        unlocked_question = [q for q in questions if q['value'] == '/data/question1'][0]
        self.assertTrue(locked_question['locked'])
        self.assertFalse(unlocked_question['locked'])

    def test_get_questions_with_repeats(self):
        """
        This test ensures that questions that start with the repeat group id
        do not get marked as repeats. For example:

            /data/repeat_name <-- repeat group path
            /data/repeat_name_count <-- question path

        Before /data/repeat_name_count would be tagged as a repeat incorrectly.
        See http://manage.dimagi.com/default.asp?234108 for context
        """
        form = self.app.get_form(self.form_with_repeats_unique_id)
        questions = form.wrapped_xform().get_questions(
            ['en'],
            include_groups=True,
        )

        repeat_name_count = list(filter(
            lambda question: question['value'] == '/data/repeat_name_count',
            questions,
        ))[0]
        self.assertIsNone(repeat_name_count['repeat'])

        repeat_question = list(filter(
            lambda question: question['value'] == '/data/repeat_name/question5',
            questions,
        ))[0]
        self.assertEqual(repeat_question['repeat'], '/data/repeat_name')

    def test_blank_form(self):
        blank_form = render_to_string("app_manager/blank_form.xml", context={
            'xmlns': generate_xmlns(),
        })
        form = self.app.new_form(self.app.get_module(0).id, 'blank', 'en')
        form.source = blank_form

        questions = form.get_questions(['en'])
        self.assertEqual([], questions)

    def test_save_to_case_in_groups(self):
        """Ensure that save to case questions have the correct group and repeat context
        when there are no other questions in that group

        """
        save_to_case_with_groups = self.app.new_form(
            self.app.get_module(0).id,
            name="Save to case in groups",
            lang='en',
            attachment=self.get_xml('save_to_case_in_groups').decode('utf-8')
        )
        questions = save_to_case_with_groups.get_questions(['en'], include_groups=True, include_triggers=True)
        group_question = [q for q in questions if q['value'] == '/data/a_group/save_to_case_in_group/case'][0]
        repeat_question = [q for q in questions if q['value'] == '/data/a_repeat/save_to_case_in_repeat/case'][0]

        self.assertEqual(group_question['group'], '/data/a_group')
        self.assertIsNone(group_question['repeat'])

        self.assertEqual(repeat_question['repeat'], '/data/a_repeat')
        self.assertEqual(repeat_question['group'], '/data/a_repeat')

    def test_fixture_references(self):
        form_with_fixtures = self.app.new_form(
            self.app.get_module(0).id,
            name="Form with Fixtures",
            lang='en',
            attachment=self.get_xml('form_with_fixtures').decode('utf-8')
        )
        questions = form_with_fixtures.get_questions(['en'], include_fixtures=True)
        self.assertEqual(questions[0], {
            "comment": None,
            "constraint": None,
            "data_source": {
                "instance_id": "country",
                "instance_ref": "jr://fixture/item-list:country",
                "nodeset": "instance('country')/country_list/country",
                "label_ref": "name",
                "value_ref": "id",
            },
            "group": None,
            "hashtagValue": "#form/lookup-table",
            "is_group": False,
            "label": "I'm a lookup table!",
            "label_ref": "lookup-table-label",
            "options": [],
            "relevant": None,
            "repeat": None,
            "required": False,
            "setvalue": None,
            "tag": "select1",
            "type": "Select",
            "value": "/data/lookup-table"
        })


class LockedQuestionsTest(AppFormTestCase):

    def setUp(self):
        super().setUp()
        self.form_unique_id = self.add_form('case_in_form', "Form").unique_id
        self.form_with_repeats_unique_id = self.add_form(
            'form_with_repeats', "Form with repeats").unique_id

    def test_has_locked_questions_true(self):
        form = self.app.get_form(self.form_unique_id)
        assert form.wrapped_xform().has_locked_questions

    def test_has_locked_questions_false(self):
        form = self.app.get_form(self.form_with_repeats_unique_id)
        assert not form.wrapped_xform().has_locked_questions

    def test_locked_question_paths(self):
        form = self.app.get_form(self.form_unique_id)
        assert form.wrapped_xform().locked_question_paths == {'/data/question2'}

    def test_locked_question_paths_empty_when_none_locked(self):
        form = self.app.get_form(self.form_with_repeats_unique_id)
        assert form.wrapped_xform().locked_question_paths == set()

    def test_locked_question_paths_includes_locked_data_node(self):
        # A lock declared directly on a data-instance node is found alongside
        # binds locked via ``nodeset``.
        form = self.app.get_form(self.form_unique_id)
        modified_source = form.source.replace(
            '<question3 />', '<question3 vellum:lock="all" />')
        assert modified_source != form.source
        paths = XForm(modified_source).locked_question_paths
        assert paths == {'/data/question2', '/data/question3'}

    def test_locked_question_paths_includes_nested_locked_data_node(self):
        # A locked data node can be nested inside a group; the lock is found at
        # any depth, with a full path.
        form = self.app.get_form(self.form_unique_id)
        modified_source = form.source.replace(
            '<question16 />', '<question16 vellum:lock="all" />')
        assert modified_source != form.source
        paths = XForm(modified_source).locked_question_paths
        assert '/data/question15/question16' in paths

    def test_has_locked_questions_true_for_data_node_lock_only(self):
        # The lock lives on a data node, not on any bind.
        form = self.app.get_form(self.form_unique_id)
        modified_source = form.source.replace(
            '<bind nodeset="/data/question2" type="xsd:string" vellum:lock="all" />',
            '<bind nodeset="/data/question2" type="xsd:string" />',
        ).replace('<question3 />', '<question3 vellum:lock="all" />')
        xform = XForm(modified_source)
        assert xform.has_locked_questions
        assert xform.locked_question_paths == {'/data/question3'}


class QuestionSignatureTest(AppFormTestCase):

    def setUp(self):
        super().setUp()
        self.form_unique_id = self.add_form('case_in_form', "Form").unique_id

    def test_question_signature_stable_for_unchanged_form(self):
        form_a = self.app.get_form(self.form_unique_id)
        form_b = self.app.get_form(self.form_unique_id)
        sig_a = form_a.wrapped_xform().get_question_signature('/data/question2')
        sig_b = form_b.wrapped_xform().get_question_signature('/data/question2')
        assert sig_a == sig_b
        assert sig_a  # non-empty for an existing question

    def test_question_signature_empty_for_unknown_path(self):
        form = self.app.get_form(self.form_unique_id)
        assert form.wrapped_xform().get_question_signature('/data/does_not_exist') == frozenset()

    def test_question_signature_changes_when_bind_changes(self):
        # Mutate the bind type for /data/question2 and confirm signature differs.
        form = self.app.get_form(self.form_unique_id)
        original = form.wrapped_xform().get_question_signature('/data/question2')
        modified_source = form.source.replace(
            '<bind nodeset="/data/question2" type="xsd:string" vellum:lock="all" />',
            '<bind nodeset="/data/question2" type="xsd:int" vellum:lock="all" />',
        )
        assert modified_source != form.source  # sanity: replacement happened
        modified = XForm(modified_source).get_question_signature('/data/question2')
        assert original != modified

    def test_question_signature_changes_when_label_changes(self):
        # Modifying the itext entry for /data/question2 should change the signature.
        form = self.app.get_form(self.form_unique_id)
        original = form.wrapped_xform().get_question_signature('/data/question2')
        modified_source = form.source.replace(
            '<text id="question2-label">',
            '<text id="question2-label" data-changed="true">',
        )
        assert modified_source != form.source
        modified = XForm(modified_source).get_question_signature('/data/question2')
        assert original != modified

    def test_question_signature_changes_when_constraint_added(self):
        # Adding a constraint attribute to the bind should change the signature.
        form = self.app.get_form(self.form_unique_id)
        original = form.wrapped_xform().get_question_signature('/data/question2')
        modified_source = form.source.replace(
            '<bind nodeset="/data/question2" type="xsd:string" vellum:lock="all" />',
            '<bind nodeset="/data/question2" type="xsd:string" '
            'constraint=". &gt; 0" vellum:lock="all" />',
        )
        assert modified_source != form.source
        modified = XForm(modified_source).get_question_signature('/data/question2')
        assert original != modified

    def test_question_signature_changes_when_hint_text_changes(self):
        # Hint label refs are pulled in via itext; changing the hint text
        # should flow through the signature.
        form = self.app.get_form(self.form_unique_id)
        original = form.wrapped_xform().get_question_signature('/data/question1')
        modified_source = form.source.replace(
            '<text id="question1-hint">',
            '<text id="question1-hint" data-changed="true">',
        )
        assert modified_source != form.source
        modified = XForm(modified_source).get_question_signature('/data/question1')
        assert original != modified

    def test_question_signature_changes_when_select_option_value_changes(self):
        # Item value changes inside a select1 are part of the control subtree.
        form = self.app.get_form(self.form_unique_id)
        original = form.wrapped_xform().get_question_signature('/data/question15/question21')
        modified_source = form.source.replace('<value>item22</value>', '<value>item99</value>')
        assert modified_source != form.source
        modified = XForm(modified_source).get_question_signature('/data/question15/question21')
        assert original != modified

    def test_question_signature_changes_when_data_instance_attr_changes(self):
        # The data-instance node is part of the signature; the vellum:comment
        # on /data/question2 lives there.
        form = self.app.get_form(self.form_unique_id)
        original = form.wrapped_xform().get_question_signature('/data/question2')
        modified_source = form.source.replace(
            '<question2 vellum:comment="This is a comment" />',
            '<question2 vellum:comment="Edited comment" />',
        )
        assert modified_source != form.source
        modified = XForm(modified_source).get_question_signature('/data/question2')
        assert original != modified
