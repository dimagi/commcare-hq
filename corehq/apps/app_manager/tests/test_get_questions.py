import os
import unittest

from django.template.loader import render_to_string
from django.test.testcases import SimpleTestCase

from lxml import etree

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
        'constraint': "1 + instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]/child_property_1",
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


class GetFormQuestionsTest(SimpleTestCase, TestFileMixin):
    domain = 'test-domain'

    file_path = ('data',)
    root = os.path.dirname(__file__)

    maxDiff = None

    def setUp(self):
        self.app = Application.new_app(self.domain, "Test")
        self.app.add_module(Module.new_module("Module", 'en'))
        module = self.app.get_module(0)
        module.case_type = 'test'

        form = self.app.new_form(
            module.id,
            name="Form",
            lang='en',
            attachment=self.get_xml('case_in_form').decode('utf-8')
        )

        form_with_repeats = self.app.new_form(
            module.id,
            name="Form with repeats",
            lang='en',
            attachment=self.get_xml('form_with_repeats').decode('utf-8')
        )

        self.form_unique_id = form.unique_id
        self.form_with_repeats_unique_id = form_with_repeats.unique_id

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


class TestXFormGetQuestions(unittest.TestCase):
    # Added by GitHub Copilot using DeepSeek V3

    def test_text_question(self):
        xml_content = """
        <xf:input label="Name" ref="/data/name">
            <xf:bind nodeset="." type="xsd:string"/>
        </xf:input>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'text', 'label': 'Name', 'ref': '/data/name'}]
        self.assertEqual(questions, expected)

    def test_select_question(self):
        xml_content = """
        <xf:select label="Gender" ref="/data/gender">
            <xf:item>
                <xf:label>Male</xf:label>
                <xf:value>M</xf:value>
            </xf:item>
            <xf:item>
                <xf:label>Female</xf:label>
                <xf:value>F</xf:value>
            </xf:item>
        </xf:select>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{
            'type': 'select',
            'label': 'Gender',
            'ref': '/data/gender',
            'options': [
                {'label': 'Male', 'value': 'M'},
                {'label': 'Female', 'value': 'F'}
            ]
        }]
        self.assertEqual(questions, expected)

    def test_multi_select_question(self):
        xml_content = """
        <xf:select1 label="Interests" ref="/data/interests">
            <xf:item>
                <xf:label>Sports</xf:label>
                <xf:value>sports</xf:value>
            </xf:item>
            <xf:item>
                <xf:label>Music</xf:label>
                <xf:value>music</xf:value>
            </xf:item>
        </xf:select1>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{
            'type': 'multi-select',
            'label': 'Interests',
            'ref': '/data/interests',
            'options': [
                {'label': 'Sports', 'value': 'sports'},
                {'label': 'Music', 'value': 'music'}
            ]
        }]
        self.assertEqual(questions, expected)

    def test_group_question(self):
        xml_content = """
        <xf:group label="Personal Details" ref="/data/personal">
        </xf:group>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'group', 'label': 'Personal Details', 'ref': '/data/personal'}]
        self.assertEqual(questions, expected)

    def test_repeat_question(self):
        xml_content = """
        <xf:repeat label="Children" ref="/data/children">
        </xf:repeat>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'repeat', 'label': 'Children', 'ref': '/data/children'}]
        self.assertEqual(questions, expected)

    def test_date_question(self):
        xml_content = """
        <xf:input label="Birthdate" ref="/data/birthdate">
            <xf:bind nodeset="." type="xsd:date"/>
        </xf:input>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'date', 'label': 'Birthdate', 'ref': '/data/birthdate'}]
        self.assertEqual(questions, expected)

    def test_time_question(self):
        xml_content = """
        <xf:input label="Wakeup Time" ref="/data/wakeup_time">
            <xf:bind nodeset="." type="xsd:time"/>
        </xf:input>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'time', 'label': 'Wakeup Time', 'ref': '/data/wakeup_time'}]
        self.assertEqual(questions, expected)

    def test_datetime_question(self):
        xml_content = """
        <xf:input label="Event Time" ref="/data/event_time">
            <xf:bind nodeset="." type="xsd:dateTime"/>
        </xf:input>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'datetime', 'label': 'Event Time', 'ref': '/data/event_time'}]
        self.assertEqual(questions, expected)

    def test_geopoint_question(self):
        xml_content = """
        <xf:input label="Location" ref="/data/location">
            <xf:bind nodeset="." type="geopoint"/>
        </xf:input>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'geopoint', 'label': 'Location', 'ref': '/data/location'}]
        self.assertEqual(questions, expected)

    def test_image_question(self):
        xml_content = """
        <xf:upload label="Profile Picture" ref="/data/profile_picture" mediatype="image/*">
        </xf:upload>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'image', 'label': 'Profile Picture', 'ref': '/data/profile_picture'}]
        self.assertEqual(questions, expected)

    def test_audio_question(self):
        xml_content = """
        <xf:upload label="Voice Note" ref="/data/voice_note" mediatype="audio/*">
        </xf:upload>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'audio', 'label': 'Voice Note', 'ref': '/data/voice_note'}]
        self.assertEqual(questions, expected)

    def test_video_question(self):
        xml_content = """
        <xf:upload label="Intro Video" ref="/data/intro_video" mediatype="video/*">
        </xf:upload>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'video', 'label': 'Intro Video', 'ref': '/data/intro_video'}]
        self.assertEqual(questions, expected)

    def test_barcode_question(self):
        xml_content = """
        <xf:upload label="Barcode Scan" ref="/data/barcode_scan" mediatype="barcode/*">
        </xf:upload>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'barcode', 'label': 'Barcode Scan', 'ref': '/data/barcode_scan'}]
        self.assertEqual(questions, expected)

    def test_secret_question(self):
        xml_content = """
        <xf:input label="Password" ref="/data/password" secret="true">
        </xf:input>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'secret', 'label': 'Password', 'ref': '/data/password'}]
        self.assertEqual(questions, expected)

    def test_android_app_question(self):
        xml_content = """
        <xf:input label="App Version" ref="/data/app_version" appearance="android-app">
        </xf:input>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'android-app', 'label': 'App Version', 'ref': '/data/app_version'}]
        self.assertEqual(questions, expected)

    def test_phone_number_question(self):
        xml_content = """
        <xf:input label="Phone Number" ref="/data/phone_number" appearance="phone-number">
        </xf:input>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'phone-number', 'label': 'Phone Number', 'ref': '/data/phone_number'}]
        self.assertEqual(questions, expected)

    def test_int_question(self):
        xml_content = """
        <xf:input label="Age" ref="/data/age">
            <xf:bind nodeset="." type="xsd:int"/>
        </xf:input>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'int', 'label': 'Age', 'ref': '/data/age'}]
        self.assertEqual(questions, expected)

    def test_decimal_question(self):
        xml_content = """
        <xf:input label="Weight" ref="/data/weight">
            <xf:bind nodeset="." type="xsd:decimal"/>
        </xf:input>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'decimal', 'label': 'Weight', 'ref': '/data/weight'}]
        self.assertEqual(questions, expected)

    def test_note_question(self):
        xml_content = """
        <xf:input label="Comments" ref="/data/comments" appearance="note">
        </xf:input>
        """
        xform = XForm(xml_content)
        questions = xform.get_questions()
        expected = [{'type': 'note', 'label': 'Comments', 'ref': '/data/comments'}]
        self.assertEqual(questions, expected)
