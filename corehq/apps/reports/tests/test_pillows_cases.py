from django.test import TestCase
from casexml.apps.case.xform import extract_case_blocks
from corehq.apps.api.es import report_term_filter
from corehq.pillows.base import VALUE_TAG
from corehq.pillows.case import CasePillow
from corehq.pillows.reportcase import ReportCasePillow
from corehq.pillows.reportxform import ReportXFormPillow
from corehq.pillows.xform import XFormPillow
from django.conf import settings
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_MAPPING

XFORM_MULTI_CASES = {
    "_id": "multi-case-test",
    "domain": "test_pillows",
    "form": {
        "@xmlns": "http://www.commcarehq.org/wisepill/patient",
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


EXAMPLE_CASE = {
   "_id": "example_case",
   "_rev": "1-ec6a0f64ad7143f1bc49e1b1807a78af",
   "opened_on": "2012-08-01T10:16:07Z",
   "domain": "dmyung",
   "#export_tag": [
       "domain",
       "type"
   ],
   "initial_processing_complete": True,
   "actions": [
       {
           "doc_type": "CommCareCaseAction",
           "xform_id": "86c8019b-3aeb-479c-afb5-59e23779478e",
           "updated_unknown_properties": {
           },
           "sync_log_id": "8018528db773225435c6c5cd76ba8894",
           "server_date": "2012-08-01T04:45:44Z",
           "action_type": "create",
           "updated_known_properties": {
               "type": "babylog",
               "name": "Cute Baby",
               "owner_id": "8606d6a689da7edd91936b0dc8a382b6"
           },
           "date": "2012-08-01T10:16:07Z",
           "indices": [
           ]
       },
       {
           "doc_type": "CommCareCaseAction",
           "xform_id": "86c8019b-3aeb-479c-afb5-59e23779478e",
           "updated_unknown_properties": {
               "dob": "2012-08-01T01:39:00Z",
               "baby_name": "Cute Baby"
           },
           "sync_log_id": "8018528db773225435c6c5cd76ba8894",
           "server_date": "2012-08-01T04:45:44Z",
           "action_type": "update",
           "updated_known_properties": {
           },
           "date": "2012-08-01T10:16:07Z",
           "indices": [
           ]
       },
       {
           "doc_type": "CommCareCaseAction",
           "xform_id": "f50c910c-f23a-4667-93c4-3e1c813a71a0",
           "date": "2012-08-01T10:16:56Z",
           "sync_log_id": "8018528db773225435c6c5cd76ba8894",
           "server_date": "2012-08-01T04:46:33Z",
           "action_type": "update",
           "updated_known_properties": {
           },
           "updated_unknown_properties": {
               "measurement_length": "20.1",
               "measurement_weight": "6.5",
               "measurement_date": "2012-08-01"
           },
           "indices": [
           ]
       },
       {
           "doc_type": "CommCareCaseAction",
           "xform_id": "5eff4ced-ff39-4abd-bd1e-4bac77274e11",
           "updated_unknown_properties": {
               "next_start_side": "right",
               "last_feeding_time": "2012-08-01T03:30:00Z"
           },
           "sync_log_id": "8018528db773225435c6c5cd76ba8894",
           "server_date": "2012-08-01T04:50:20Z",
           "action_type": "update",
           "updated_known_properties": {
           },
           "date": "2012-08-01T10:20:44Z",
           "indices": [
           ]
       },
       {
           "doc_type": "CommCareCaseAction",
           "xform_id": "3dee4630-ecba-4c20-b800-186c25636627",
           "date": "2012-08-01T10:22:00Z",
           "sync_log_id": "8018528db773225435c6c5cd76ba8894",
           "server_date": "2012-08-01T04:51:36Z",
           "action_type": "update",
           "updated_known_properties": {
           },
           "updated_unknown_properties": {
               "diaper_change_time": "2012-08-01T04:34:00Z",
               "diaper_type": "poopy_diaper"
           },
           "indices": [
           ]
       },
       {
           "doc_type": "CommCareCaseAction",
           "xform_id": "48c7ee05-b010-4e63-abee-9bf276a62998",
           "updated_unknown_properties": {
               "next_start_side": "left",
               "last_feeding_time": "2012-08-01T02:00:00Z"
           },
           "sync_log_id": "8018528db773225435c6c5cd76ba8894",
           "server_date": "2012-08-01T04:53:03Z",
           "action_type": "update",
           "updated_known_properties": {
           },
           "date": "2012-08-01T10:23:26Z",
           "indices": [
           ]
       },
   ],
   "measurement_date": "2012-8-02",
   "last_poop": "2012-08-01T05:11:00Z",
   "closed_on": None,
   "user_id": "f72265c0-362a-11e0-9e24-005056aa7fb5",
   "last_pee": "2012-08-03T12:22:00Z",
   "prior_diapers": ['poop', 'pee'],
   "computed_": {
   },
   "version": "2.0",
   "diaper_change_time": "2012-08-20T08:50:00Z",
   "closed": False,
   "baby_name": "Cute Baby",
   "type": "babylog",
   "diaper_type": "pee_diaper",
   "owner_id": "8c20fba6b49940888f1949cf64f53bec",
   "measurement_length": "2",
   "next_start_side": "Right",
   "xform_ids": [
       "86c8019b-3aeb-479c-afb5-59e23779478e",
       "f50c910c-f23a-4667-93c4-3e1c813a71a0",
       "5eff4ced-ff39-4abd-bd1e-4bac77274e11",
       "3dee4630-ecba-4c20-b800-186c25636627",
       "48c7ee05-b010-4e63-abee-9bf276a62998",
      ],
   "server_modified_on": "2012-12-30T03:23:04Z",
   "location_": [
   ],
   "export_tag": [
   ],
   "computed_modified_on_": None,
   "last_feeding_time": "2012-08-03T14:55:00Z",
   "modified_on": "2012-12-30T03:23:03Z",
   "doc_type": "CommCareCase",
   "referrals": [
   ],
   "name": "Cute Baby",
   "dob": "2012-08-01T02:00:00Z",
   "measurement_weight": "1",
   "indices": [
   ],
   "external_id": None
}


class testReportCaseProcessing(TestCase):

    def testXFormPillowSingleCaseProcess(self):
        """
        Test that xform pillow can process and cleanup a single xform with a case submission
        """
        xform = XFORM_SINGLE_CASE
        pillow = XFormPillow(online=False)
        changed = pillow.change_transform(xform)

        self.assertIsNone(changed['form']['case'].get('@date_modified'))
        self.assertIsNotNone(xform['form']['case']['@date_modified'])


    def testXFormPillowListCaseProcess(self):
        """
        Test that xform pillow can process and cleanup a single xform with a list of cases in it
        """
        xform = XFORM_MULTI_CASES
        pillow = XFormPillow(online=False)
        changed = pillow.change_transform(xform)


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

        pillow = CasePillow(online=False)
        changed_with_owner_id = pillow.change_transform(case_owner_id)
        changed_with_no_owner_id = pillow.change_transform(case_no_owner_id)

        self.assertEqual(changed_with_owner_id.get("owner_id"), "testuser")
        self.assertEqual(changed_with_no_owner_id.get("owner_id"), "testuser")

    def testReportXFormTransform(self):
        form = XFORM_SINGLE_CASE
        report_pillow = ReportXFormPillow(online=False)
        form['domain'] = settings.ES_XFORM_FULL_INDEX_DOMAINS[0]
        processed_form = report_pillow.change_transform(form)
        mapping = report_pillow.default_mapping

        #root level
        for k, v in processed_form['form'].items():
            if k in mapping['properties']['form']['properties']:
                if isinstance(v, dict):
                    self.assertFalse('#value' in v, msg="Error, processed dict contains a #value dict for key [%s] when it shouldn't" % k)
                else:
                    #it's not a dict, so that means it's ok
                    if k in form:
                        self.assertEqual(form[k], v)
            else:
                self.assertTrue(isinstance(v, dict))
                if isinstance(form['form'][k], dict):
                    #if the original is a dict, then, make sure the keys are the same
                    self.assertFalse('#value' in v)
                    self.assertEqual(sorted(form['form'][k].keys()), sorted(v.keys()))
                else:
                    self.assertTrue('#value' in v)
                    self.assertEqual(form['form'][k], v['#value'])

    def testReportCaseTransform(self):
        case = EXAMPLE_CASE
        case['domain'] = settings.ES_CASE_FULL_INDEX_DOMAINS[0]
        report_pillow = ReportCasePillow(online=False)
        processed_case = report_pillow.change_transform(case)
        mapping = report_pillow.default_mapping

        #known properties, not #value'd
        self.assertEqual(processed_case['user_id'], case['user_id'])
        self.assertEqual(processed_case['actions'][0]['doc_type'], case['actions'][0]['doc_type'])

        #dynamic case properties #valued
        self.assertEqual(processed_case['last_poop'].get(VALUE_TAG), case['last_poop'])
        self.assertEqual(processed_case['diaper_type'].get(VALUE_TAG), case['diaper_type'])
        self.assertTrue(isinstance(processed_case['prior_diapers'], list))
        for diaper in processed_case['prior_diapers']:
            self.assertTrue(VALUE_TAG in diaper)

        self.assertEqual(case['prior_diapers'], [x[VALUE_TAG] for x in processed_case['prior_diapers']])


    def testReportCaseQuery(self):

        unknown_terms = ['gender', 'notes', 'sms_reminder', 'hamlet_name', 'actions.dob',
                         'actions.dots', 'actions.hp']
        unknown_terms_query = report_term_filter(unknown_terms, REPORT_CASE_MAPPING)

        manually_set = ['%s.%s' % (x, VALUE_TAG) for x in unknown_terms]
        self.assertEqual(manually_set, unknown_terms_query)

        known_terms = ['owner_id', 'domain', 'opened_on', 'actions.action_type', 'actions.date',
                       'actions.indices.doc_type']
        known_terms_query = report_term_filter(known_terms, REPORT_CASE_MAPPING)

        self.assertEqual(known_terms_query, known_terms)



