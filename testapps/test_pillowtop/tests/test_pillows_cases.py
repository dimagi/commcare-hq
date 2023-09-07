from django.test import TestCase

from casexml.apps.case.xform import extract_case_blocks

from corehq.apps.es.cases import case_adapter
from corehq.apps.es.forms import form_adapter
from corehq.util.test_utils import softer_assert

XFORM_MULTI_CASES = {
    "_id": "multi-case-test",
    "domain": "test_pillows",
    "form": {
        "@xmlns": "http://openrosa.org/formdesigner/0122B6F6-C765-49FB-B367-C6976E9286AB",
        "case": [
            {
                "@xmlns": "http://commcarehq.org/case/transaction/v2",
                "@date_modified": "",
                "create": {
                    "case_type": "patient",
                    "owner_id": "testowner",
                    "case_name": "Jaspertest"
                },
                "@user_id": "testowner",
                "@case_id": "case1",
                "update": {
                    "contact_phone_number": "+6175552214",
                    "sms_reminder": "False",
                    "gender": "M",
                    "notes": "",
                    "time_zone": "Europe/Amsterdam",
                    "start_date": "2012-02-09T23:00:00Z",
                    "contact_backend_id": "MOBILE_BACKEND_YO",
                    "date_of_birth": "01-01-1970",
                    "contact_phone_number_is_verified": "1",
                    "group_id": "5",
                    "identification_code": "Jaspertest"
                },
                "@type": "patient"
            },
            {
                "@xmlns": "http://commcarehq.org/case/transaction/v2",
                "@date_modified": "",
                "create": {
                    "case_type": "patient",
                    "owner_id": "testowner",
                    "case_name": "Test Dispenser"
                },
                "@user_id": "testowner",
                "@case_id": "case2",
                "update": {
                    "contact_phone_number": "+6175552215",
                    "sms_reminder": "False",
                    "gender": "M",
                    "notes": "",
                    "time_zone": "Europe/Amsterdam",
                    "start_date": "2012-02-22T23:00:00Z",
                    "contact_backend_id": "MOBILE_BACKEND_YO",
                    "date_of_birth": "01-01-1970",
                    "contact_phone_number_is_verified": "1",
                    "group_id": "5",
                    "identification_code": "Test Dispenser"
                },
                "@type": "patient"
            },
            {
                "@xmlns": "http://commcarehq.org/case/transaction/v2",
                "@date_modified": "",
                "@user_id": "testowner",
                "@case_id": "case3",
                "update": {
                    "signal_strength": "26",
                    "puffcount": "1970-01-01T00:00:05Z",
                    "battery_strength": "4030",
                    "classification": "NOTRELEVANT",
                    "msisdn": "31612236854",
                    "ussd_response": "N/A",
                    "serial": "357022005455475",
                    "message_type": "02",
                    "rawmessage": "foo_bar",
                    "datetime": "2013-03-07T15:48:28Z"
                },
                "@type": "event"
            },
        ],
        "meta": {
            "timeStart": "2013-03-11T10:26:34Z",
            "instanceID": "multi-case-test",
            "userID": "testowner",
            "timeEnd": "2013-03-11T10:26:34Z"
        },
        "#type": "data"
    },
    "initial_processing_complete": True,
    "computed_modified_on_": None,
    "path": "/a/test_pillows/receiver",
    "last_sync_token": None,
    "location_": [
    ],
    "xmlns": "http://www.commcarehq.org/wisepill/patient",
    "doc_type": "XFormInstance",
    "partial_submission": False,
    "#export_tag": [
        "domain",
        "xmlns"
    ],
    "received_on": "2013-03-11T10:26:35Z",
    "submit_ip": "95.97.32.34",
    "computed_": {
    },
    "openrosa_headers": {
    },
}

XFORM_SINGLE_CASE = {
    "_id": "single_case_form",
    "domain": "single_case",
    "form": {
        "@xmlns": "http://openrosa.org/formdesigner/0122B6F6-C765-49FB-B367-C6976E9286AA",
        "@uiVersion": "1",
        "@name": "Provider Chooser",
        "provider1": "617-555-2214",
        "provider2": "617-555-2215",
        "provider3": "item19",
        "#type": "data",
        "case": {
            "@xmlns": "http://commcarehq.org/case/transaction/v2",
            "@date_modified": "",
            "@user_id": "eb7b3fdd9dba6dd7aa49827f5d64dab4",
            "@case_id": "62ac1cf4-59c7-47e5-83e1-fbeaf3bd6c5c",
            "update": {
                "provider1": "617-555-2214",
                "provider2": "617-555-2215"
            }
        },
        "provider5": "item22",
        "meta": {
            "@xmlns": "http://openrosa.org/jr/xforms",
            "username": "ctsims",
            "instanceID": "34097278-ac41-4589-a100-16052d7912fa",
            "userID": "testuser",
            "timeEnd": "2012-12-21T21:45:19Z",
            "appVersion": {
                "@xmlns": "http://commcarehq.org/xforms",
                "#text": "2.0"
            },
            "timeStart": "2012-12-21T21:45:04Z",
            "deviceID": "cloudcare"
        },
        "provider4": "item21",
        "@version": "65"
    },
    "doc_type": "XFormInstance",
    "computed_modified_on_": None,
    "app_id": "cb5b61d35f31ca36f26f6a3081bd11be",
    "path": "/a/single_case/receiver/cb5b61d35f31ca36f26f6a3081bd11be/",
    "last_sync_token": None,
    "location_": [
    ],
    "xmlns": "http://openrosa.org/formdesigner/0122B6F6-C765-49FB-B367-C6976E9286AA",
    "partial_submission": False,
    "#export_tag": [
        "domain",
        "xmlns"
    ],
    "received_on": "2012-12-18T20:10:46Z",
    "submit_ip": "127.0.0.1",
    "computed_": {
    },
    "openrosa_headers": {
        "HTTP_ACCEPT_LANGUAGE": "en-US,en;q=0.8"
    }
}


CASE_WITH_OWNER_ID = {
   "_id": "case_with_owner_id",
   "opened_on": "2013-05-03T11:26:54Z",
   "location_": [
   ],
   "domain": "owner_case",
   "xform_ids": [
       "98e6b3d7-7c4f-466b-a3f4-0395c1db7f4f"
   ],
   "server_modified_on": "2013-06-11T15:40:10Z",
   "initial_processing_complete": False,
   "export_tag": [
   ],
   "computed_modified_on_": None,
   "actions": [
       {
           "doc_type": "CommCareCaseAction",
           "xform_id": "98e6b3d7-7c4f-466b-a3f4-0395c1db7f4f",
           "user_id": "testuser",
           "xform_name": "New Form",
           "sync_log_id": None,
           "server_date": "2013-05-03T05:57:03Z",
           "action_type": "create",
           "updated_known_properties": {
               "type": "testcase",
               "name": "75",
               "owner_id": "testuser"
           },
           "updated_unknown_properties": {
           },
           "indices": [
           ],
           "xform_xmlns": "http://openrosa.org/formdesigner/150B838E-B49C-44A3-B037-928DC787F17D",
           "date": "2013-05-03T11:26:54Z"
       }
   ],
   "modified_on": "2013-05-03T11:26:54Z",
   "closed_by": None,
   "closed_on": None,
   "referrals": [
   ],
   "user_id": "testuser",
   "name": "75",
   "doc_type": "CommCareCase",
   "external_id": None,
   "#export_tag": [
       "domain",
       "type"
   ],
   "opened_by": "testuser",
   "computed_": {
   },
   "version": "2.0",
   "closed": False,
   "indices": [
   ],
   "type": "testcase",
   "owner_id": "testuser"
}

CASE_NO_OWNER_ID = {
   "_id": "case_no_owner_id",
   "opened_on": "2013-05-03T11:26:54Z",
   "location_": [
   ],
   "domain": "no_owner_case",
   "xform_ids": [
       "98e6b3d7-7c4f-466b-a3f4-0395c1db7f4f"
   ],
   "server_modified_on": "2013-06-11T15:40:10Z",
   "initial_processing_complete": False,
   "export_tag": [
   ],
   "computed_modified_on_": None,
   "actions": [
       {
           "doc_type": "CommCareCaseAction",
           "xform_id": "98e6b3d7-7c4f-466b-a3f4-0395c1db7f4f",
           "user_id": "testuser",
           "xform_name": "New Form",
           "sync_log_id": None,
           "server_date": "2013-05-03T05:57:03Z",
           "action_type": "create",
           "updated_known_properties": {
               "type": "testcase",
               "name": "75",
           },
           "updated_unknown_properties": {
           },
           "indices": [
           ],
           "xform_xmlns": "http://openrosa.org/formdesigner/150B838E-B49C-44A3-B037-928DC787F17D",
           "date": "2013-05-03T11:26:54Z"
       }
   ],
   "modified_on": "2013-05-03T11:26:54Z",
   "closed_by": None,
   "closed_on": None,
   "referrals": [
   ],
   "user_id": "testuser",
   "name": "75",
   "doc_type": "CommCareCase",
   "external_id": None,
   "#export_tag": [
       "domain",
       "type"
   ],
   "opened_by": "testuser",
   "computed_": {
   },
   "version": "2.0",
   "closed": False,
   "indices": [
   ],
   "type": "testcase",
}


class TestPillows(TestCase):

    @softer_assert()
    def testXFormPillowSingleCaseProcess(self):
        """
        Test that xform pillow can process and cleanup a single xform with a case submission
        """
        xform = XFORM_SINGLE_CASE
        changed = form_adapter.to_json(xform)

        self.assertIsNone(changed['form']['case'].get('@date_modified'))
        self.assertIsNotNone(xform['form']['case']['@date_modified'])

    @softer_assert()
    def testXFormPillowListCaseProcess(self):
        """
        Test that xform pillow can process and cleanup a single xform with a list of cases in it
        """
        xform = XFORM_MULTI_CASES
        changed = form_adapter.to_json(xform)

        changed_cases = extract_case_blocks(changed)
        orig_cases = extract_case_blocks(xform)

        [self.assertIsNotNone(x['@date_modified']) for x in orig_cases]
        [self.assertIsNone(x.get('@date_modified')) for x in changed_cases]

    def testOwnerIDSetOnTransform(self):
        """
        Test that the owner_id gets set to the case when the pillow calls change transform
        """
        case_owner_id = CASE_WITH_OWNER_ID
        case_no_owner_id = CASE_NO_OWNER_ID

        changed_with_owner_id = case_adapter.to_json(case_owner_id)
        changed_with_no_owner_id = case_adapter.to_json(case_no_owner_id)

        self.assertEqual(changed_with_owner_id.get("owner_id"), "testuser")
        self.assertEqual(changed_with_no_owner_id.get("owner_id"), "testuser")
