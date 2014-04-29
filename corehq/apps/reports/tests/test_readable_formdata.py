from unittest import TestCase
from corehq.apps.reports.formdetails.readable import FormQuestion, \
    zip_form_data_and_questions


class ReadableFormdataTest(TestCase):

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
        questions = [FormQuestion(q) for q in questions_json]
        self.assertEqual(
            [q.to_json()
             for q in zip_form_data_and_questions(form_data, questions)],
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
