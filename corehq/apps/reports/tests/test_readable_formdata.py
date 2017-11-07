from __future__ import absolute_import
import json
import os
import uuid

from django.test import SimpleTestCase
import yaml
from django.test.testcases import TestCase

from corehq.apps.app_manager.xform import XForm
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.reports.formdetails.readable import (
    FormQuestionResponse,
    get_questions_from_xform_node,
    get_readable_form_data,
    get_readable_data_for_submission)
from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend
from corehq.form_processor.utils.xform import get_simple_form_xml


class ReadableFormdataTest(SimpleTestCase):

    maxDiff = None

    def test(self):

        questions_json = [{
            "tag": "input",
            "repeat": None,
            "group": None,
            "value": "/data/question4",
            "label": "Question 4",
            "type": "Text",
            'calculate': None,
            'required': False,
            'relevant': None,
        }]
        form_data = {
            "@uiVersion": "1",
            "@xmlns": "http://openrosa.org/formdesigner/D096EE34-DF37-466C-B6D9-950A36D570AD",
            "@name": "Untitled Form",
            "question4": "foo",
            "#type": "data",
            "case": {
                "@xmlns": "http://commcarehq.org/case/transaction/v2",
                "@date_modified": "2013-12-23T16:24:20Z",
                "create": {
                    "case_type": "case",
                    "case_name": "foo",
                    "owner_id": "9ee0367ad4051f0fb33c75eae67d750e"
                },
                "@user_id": "9ee0367ad4051f0fb33c75eae67d750e",
                "update": "",
                "@case_id": "6bc190f6-ddeb-4a42-b445-8fa348b50806"
            },
            "meta": {
                "@xmlns": "http://openrosa.org/jr/xforms",
                "username": "droberts@dimagi.com",
                "instanceID": "0398f186-c35f-4437-8b6b-41800807e485",
                "userID": "9ee0367ad4051f0fb33c75eae67d750e",
                "timeEnd": "2013-12-23T16:24:20Z",
                "appVersion": {
                    "@xmlns": "http://commcarehq.org/xforms",
                    "#text": "2.0"
                },
                "timeStart": "2013-12-23T16:24:10Z",
                "deviceID": "cloudcare"
            },
            "@version": "10"
        }
        questions = [FormQuestionResponse(q) for q in questions_json]
        actual = get_readable_form_data(form_data, questions)
        self.assertJSONEqual(
            json.dumps([q.to_json() for q in actual]),
            json.dumps([{
                "tag": "input",
                "repeat": None,
                "group": None,
                "value": "/data/question4",
                "label": "Question 4",
                "response": "foo",
                "type": "Text",
                'calculate': None,
                'comment': None,
                'required': False,
                'relevant': None,
            }])
        )

    def test_repeat(self):
        questions_json = [{
            'tag': 'input',
            'type': 'Text',
            'label': 'Text',
            'value': '/data/question1',
        }, {
            'tag': 'input',
            'type': 'Int',
            'label': 'How many names?',
            'value': '/data/question18',
        }, {
            'tag': 'repeat',
            'type': 'Repeat',
            'label': 'Repeat',
            'value': '/data/question12',
        }, {
            'tag': 'input',
            'type': 'Text',
            'label': 'Name',
            'value': '/data/question12/name',
            'repeat': '/data/question12',
            'group': '/data/question12',
        }, {
            'tag': 'trigger',
            'type': 'Trigger',
            'label': 'Label',
            'value': '/data/question2',
        }, {
            'tag': 'select1',
            'type': 'Select',
            'label': 'Single Answer',
            'value': '/data/question3',
            'options': [{'value': 'item1', 'label': 'Item 1'},
                        {'value': 'item2', 'label': 'Item 2'}]
        }]
        form_data = {
            "@uiVersion": "1",
            "@xmlns": "http://openrosa.org/formdesigner/432B3A7F-6EEE-4033-8740-ACCB0804C4FC",
            "@name": "Untitled Form",
            "question18": "3",
            "#type": "data",
            "question12": [
                {
                    "name": "Jack"
                },
                {
                    "name": "Jill"
                },
                {
                    "name": "Up the hill"
                }
            ],
            "meta": {
                "@xmlns": "http://openrosa.org/jr/xforms",
                "username": "danny",
                "instanceID": "172981b6-5eeb-4be8-bbc7-ad52f808e803",
                "userID": "a07d4bd967a9c205287f767509600931",
                "timeEnd": "2014-04-28T18:27:05Z",
                "appVersion": {
                    "@xmlns": "http://commcarehq.org/xforms",
                    "#text": "CommCare ODK, version \"2.11.0\"(29272). App v8. CommCare Version 2.11. Build 29272, built on: February-14-2014"
                },
                "timeStart": "2014-04-28T18:26:38Z",
                "deviceID": "990004280784863"
            },
            "question1": "T",
            "question3": "item2",
            "question2": "OK",
            "@version": "8"
        }

        expected = [{
            'tag': 'input',
            'type': 'Text',
            'label': 'Text',
            'value': '/data/question1',
            'response': 'T',
            'calculate': None,
        }, {
            'tag': 'input',
            'type': 'Int',
            'label': 'How many names?',
            'value': '/data/question18',
            'response': '3',
            'calculate': None,
        }, {
            'tag': 'repeat',
            'type': 'Repeat',
            'label': 'Repeat',
            'value': '/data/question12',
            'response': True,
            'calculate': None,
            'children': [{
                'children': [{
                    'tag': 'input',
                    'type': 'Text',
                    'label': 'Name',
                    'value': '/data/question12/name',
                    'repeat': '/data/question12',
                    'group': '/data/question12',
                    'response': 'Jack',
                    'calculate': None,
                }],
                'response': True,
            }, {
                'children': [{
                    'tag': 'input',
                    'type': 'Text',
                    'label': 'Name',
                    'value': '/data/question12/name',
                    'repeat': '/data/question12',
                    'group': '/data/question12',
                    'response': 'Jill',
                    'calculate': None,
                }],
                'response': True
            }, {
                'children': [{
                    'tag': 'input',
                    'type': 'Text',
                    'label': 'Name',
                    'value': '/data/question12/name',
                    'repeat': '/data/question12',
                    'group': '/data/question12',
                    'response': 'Up the hill',
                    'calculate': None,
                }],
                'response': True
            }],
        }, {
            'tag': 'trigger',
            'type': 'Trigger',
            'label': 'Label',
            'value': '/data/question2',
            'response': 'OK',
            'calculate': None,
        }, {
            'tag': 'select1',
            'type': 'Select',
            'label': 'Single Answer',
            'value': '/data/question3',
            'options': [{'value': 'item1', 'label': 'Item 1'},
                        {'value': 'item2', 'label': 'Item 2'}],
            'response': 'item2',
            'calculate': None,
        }]
        actual = get_readable_form_data(
            form_data,
            [FormQuestionResponse(q) for q in questions_json]
        )
        self.assertJSONEqual(
            json.dumps([q.to_json() for q in actual]),
            json.dumps([FormQuestionResponse(q).to_json() for q in expected])
        )

    def _test_corpus(self, slug):
        xform_file = os.path.join(
            os.path.dirname(__file__),
            'readable_forms', '{}.xform.xml'.format(slug))
        submission_file = os.path.join(
            os.path.dirname(__file__),
            'readable_forms', '{}.submission.json'.format(slug))
        result_file = os.path.join(
            os.path.dirname(__file__),
            'readable_forms', '{}.result.yaml'.format(slug))
        with open(xform_file) as f:
            xform = f.read()
        with open(submission_file) as f:
            data = json.load(f)
        with open(result_file) as f:
            result = yaml.load(f)
        questions = get_questions_from_xform_node(XForm(xform), langs=['en'])
        questions = get_readable_form_data(data, questions)

        # Search for 'READABLE FORMS TEST' for more info
        # to bootstrap a test and have it print out your yaml result
        # uncomment this line. Ghetto but it works.
        # print yaml.safe_dump([json.loads(json.dumps(x.to_json()))
        #                       for x in questions])

        self.assertJSONEqual(json.dumps([x.to_json() for x in questions]),
                             json.dumps(result),
                             msg="Search for \"READABLE FORMS TEST\" for more info on fixing this test")

    def test_mismatched_group_hierarchy(self):
        self._test_corpus('mismatched_group_hierarchy')

    def test_top_level_refless_group(self):
        self._test_corpus('top_level_refless_group')


class ReadableFormTest(TestCase):

    def setUp(self):
        super(ReadableFormTest, self).setUp()
        self.domain = uuid.uuid4().hex

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms(self.domain)
        super(ReadableFormTest, self).tearDown()

    def test_get_readable_data_for_submission(self):
        formxml = get_simple_form_xml('123')

        xform = submit_form_locally(formxml, self.domain).xform
        actual, _ = get_readable_data_for_submission(xform)

        expected = [{
            'value': u'/data/dalmation_count',
            'label': u'dalmation_count',
            'response': u'yes'
        }]
        self.assertJSONEqual(
            json.dumps([q.to_json() for q in actual]),
            json.dumps([FormQuestionResponse(q).to_json() for q in expected])
        )


@use_sql_backend
class ReadableFormSQLTest(ReadableFormTest):
    pass
