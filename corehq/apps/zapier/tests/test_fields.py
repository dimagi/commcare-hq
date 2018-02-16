from __future__ import absolute_import
from django.test.testcases import TestCase, SimpleTestCase
from django.test.client import Client
from tastypie.resources import Resource

from casexml.apps.case.mock import CaseFactory
from corehq.apps.zapier.api.v0_5 import ZapierCustomFieldCaseResource
from corehq.apps.zapier.util import remove_advanced_fields
from six.moves import range


class TestRemoveAdvancedFields(SimpleTestCase):

    def test_form(self):
        form = {
            "build_id": "de9553b384b1ff3acaceaed4a217f277",
            "domain": "test",
            "form": {
                "#type": "data",
                "@name": "Test",
                "@uiVersion": "1",
                "@version": "6",
                "@xmlns": "http://openrosa.org/formdesigner/test",
                "age": "3.052703627652293",
                "case": {
                    "@case_id": "67dfe2a9-9413-4811-b5f5-a7c841085e9e",
                    "@date_modified": "2016-12-20T12:13:23.870000Z",
                    "@user_id": "cff3d2fb45eafd1abbc595ae89f736a6",
                    "@xmlns": "http://commcarehq.org/case/transaction/v2",
                    "update": {
                        "test": ""
                    }
                },
                "dob": "2013-12-01",
                "dose_counter": "0",
                "follow_up_test_date": "",
                "follow_up_test_type": "",
                "grp_archive_person": {
                    "archive_person": {
                        "case": {
                            "@case_id": "d2fcfa48-5286-4623-a209-6a9c30781b3d",
                            "@date_modified": "2016-12-20T12:13:23.870000Z",
                            "@user_id": "cff3d2fb45eafd1abbc595ae89f736a6",
                            "@xmlns": "http://commcarehq.org/case/transaction/v2",
                            "update": {
                                "archive_reason": "not_evaluated",
                                "owner_id": "_archive_"
                            }
                        }
                    },
                    "close_episode": {
                        "case": {
                            "@case_id": "67dfe2a9-9413-4811-b5f5-a7c841085e9e",
                            "@date_modified": "2016-12-20T12:13:23.870000Z",
                            "@user_id": "cff3d2fb45eafd1abbc595ae89f736a6",
                            "@xmlns": "http://commcarehq.org/case/transaction/v2",
                            "close": ""
                        }
                    },
                    "close_occurrence": {
                        "case": {
                            "@case_id": "912d0ec6-709f-4d82-81d8-6a5aa163e2fb",
                            "@date_modified": "2016-12-20T12:13:23.870000Z",
                            "@user_id": "cff3d2fb45eafd1abbc595ae89f736a6",
                            "@xmlns": "http://commcarehq.org/case/transaction/v2",
                            "close": ""
                        }
                    },
                    "close_referrals": {
                        "@count": "0",
                        "@current_index": "0",
                        "@ids": ""
                    }
                },
                "lbl_form_end": "OK",
                "length_of_cp": "",
                "length_of_ip": "",
                "meta": {
                    "@xmlns": "http://openrosa.org/jr/xforms",
                    "appVersion": "CommCare Android, version \"2.31.0\"(423345). "
                                  "App v59. CommCare Version 2.31. Build 423345, built on: 2016-11-02",
                    "app_build_version": 59,
                    "commcare_version": "2.31.0",
                    "deviceID": "359872069029881",
                    "geo_point": None,
                    "instanceID": "2d0e138e-c9b0-4998-a7fb-06b7109e0bf7",
                    "location": {
                        "#text": "54.4930116 18.5387613 0.0 21.56",
                        "@xmlns": "http://commcarehq.org/xforms"
                    },
                    "timeEnd": "2016-12-20T12:13:23.870000Z",
                    "timeStart": "2016-12-20T12:13:08.346000Z",
                    "userID": "cff3d2fb45eafd1abbc595ae89f736a6",
                    "username": "test"
                },
            }
        }
        remove_advanced_fields(form_dict=form)
        self.assertIsNone(form['form']['meta'].get('userID'))
        self.assertIsNone(form.get('xmlns'))
        self.assertIsNone(form['form'].get('@name'))
        self.assertIsNone(form['form']['meta'].get('appVersion'))
        self.assertIsNone(form['form']['meta'].get('deviceID'))
        self.assertIsNone(form['form']['meta'].get('location'))
        self.assertIsNone(form.get('app_id'))
        self.assertIsNone(form.get('build_id'))
        self.assertIsNone(form['form'].get('@version'))
        self.assertIsNone(form.get('doc_type'))
        self.assertIsNone(form.get('last_sync_token'))
        self.assertIsNone(form.get('partial_submission'))

        self.assertIsNotNone(form['domain'])


class TestZapierCustomFields(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestZapierCustomFields, cls).setUpClass()
        cls.test_url = "http://commcarehq.org/?domain=joto&case_type=teddiursa"

    def test_case_fields(self):

        expected_fields = [
            {"help_text": "", "key": "properties__level", "label": "Level", "type": "unicode"},
            {"help_text": "", "key": "properties__mood", "label": "Mood", "type": "unicode"},
            {"help_text": "", "key": "properties__move_type", "label": "Move type", "type": "unicode"},
            {"help_text": "", "key": "properties__name", "label": "Name", "type": "unicode"},
            {"help_text": "", "key": "properties__opened_on", "label": "Opened on", "type": "unicode"},
            {"help_text": "", "key": "properties__owner_id", "label": "Owner id", "type": "unicode"},
            {"help_text": "", "key": "properties__prop1", "label": "Prop1", "type": "unicode"},
            {"help_text": "", "key": "properties__type", "label": "Type", "type": "unicode"},
            {"help_text": "", "key": "date_closed", "label": "Date closed", "type": "unicode"},
            {"help_text": "", "key": "xform_ids", "label": "XForm IDs", "type": "unicode"},
            {"help_text": "", "key": "properties__date_opened", "label": "Date opened", "type": "unicode"},
            {"help_text": "", "key": "properties__external_id", "label": "External ID", "type": "unicode"},
            {"help_text": "", "key": "properties__case_name", "label": "Case name", "type": "unicode"},
            {"help_text": "", "key": "properties__case_type", "label": "Case type", "type": "unicode"},
            {"help_text": "", "key": "user_id", "label": "User ID", "type": "unicode"},
            {"help_text": "", "key": "date_modified", "label": "Date modified", "type": "unicode"},
            {"help_text": "", "key": "case_id", "label": "Case ID", "type": "unicode"},
            {"help_text": "", "key": "properties__owner_id", "label": "Owner ID", "type": "unicode"},
            {"help_text": "", "key": "resource_uri", "label": "Resource URI", "type": "unicode"}
        ]

        request = Client().get(self.test_url).wsgi_request
        bundle = Resource().build_bundle(data={}, request=request)

        factory = CaseFactory(domain="joto")
        factory.create_case(
            case_type='teddiursa',
            owner_id='owner1',
            case_name='dre',
            update={'prop1': 'blah', 'move_type': 'scratch', 'mood': 'happy', 'level': '100'}
        )

        actual_fields = ZapierCustomFieldCaseResource().obj_get_list(bundle)
        for i in range(len(actual_fields)):
            self.assertEqual(expected_fields[i], actual_fields[i].get_content())
