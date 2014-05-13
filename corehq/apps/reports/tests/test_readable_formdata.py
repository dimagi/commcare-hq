from unittest import TestCase
from corehq.apps.reports.formdetails.readable import (
    FormQuestionResponse,
    questions_in_hierarchy,
    strip_form_data,
    zip_form_data_and_questions,
)


class ReadableFormdataTest(TestCase):

    maxDiff = None

    def test(self):

        questions_json = [{
            "tag": "input",
            "repeat": None,
            "group": None,
            "value": "/data/question4",
            "label": "Question 4",
            "type": "Text",
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
        questions = questions_in_hierarchy([FormQuestionResponse(q)
                                            for q in questions_json])
        self.assertEqual(
            [q.to_json()
             for q in zip_form_data_and_questions(strip_form_data(form_data),
                                                  questions,
                                                  path_context='/data/')],
            [{
                "tag": "input",
                "repeat": None,
                "group": None,
                "value": "/data/question4",
                "label": "Question 4",
                "response": "foo",
                "type": "Text",
            }]
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
            'response': 'T'
        }, {
            'tag': 'input',
            'type': 'Int',
            'label': 'How many names?',
            'value': '/data/question18',
            'response': '3',
        }, {
            'tag': 'repeat',
            'type': 'Repeat',
            'label': 'Repeat',
            'value': '/data/question12',
            'response': True,
            'children': [{
                'children': [{
                    'tag': 'input',
                    'type': 'Text',
                    'label': 'Name',
                    'value': '/data/question12/name',
                    'repeat': '/data/question12',
                    'group': '/data/question12',
                    'response': 'Jack',
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
                }],
                'response': True
            }],
        }, {
            'tag': 'trigger',
            'type': 'Trigger',
            'label': 'Label',
            'value': '/data/question2',
            'response': 'OK',
        }, {
            'tag': 'select1',
            'type': 'Select',
            'label': 'Single Answer',
            'value': '/data/question3',
            'options': [{'value': 'item1', 'label': 'Item 1'},
                        {'value': 'item2', 'label': 'Item 2'}],
            'response': 'item2',
        }]
        questions = questions_in_hierarchy([FormQuestionResponse(q)
                                            for q in questions_json])
        self.assertEqual(
            [q.to_json()
             for q in zip_form_data_and_questions(strip_form_data(form_data),
                                                  questions,
                                                  path_context='/data/')],
            [FormQuestionResponse(q).to_json() for q in expected]
        )
