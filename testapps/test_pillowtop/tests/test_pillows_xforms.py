from __future__ import absolute_import
from __future__ import unicode_literals
import copy
import mock
from django.test import SimpleTestCase
from django.conf import settings
from corehq.apps.api.es import report_term_filter
from corehq.pillows.base import restore_property_dict, VALUE_TAG
from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_MAPPING
from corehq.pillows.reportxform import transform_xform_for_report_forms_index
from corehq.pillows.utils import UNKNOWN_USER_TYPE

CONCEPT_XFORM = {
   "_id": "concept_xform",
   "domain": "test-domain",
   "form": {
       "@xmlns": "http://openrosa.org/formdesigner/test_concepts",
       "@uiVersion": "1",
       "@name": "Visit",
       "last_visit": "2013-09-01",
       "any_other_sick": {
           "#text": "no",
           "@concept_id": "1907"
       },
       "cur_num_fp": "2",
       "#type": "data",
       "cur_counsel_topics": "bednet handwashing",
       "case": {
           "@xmlns": "http://commcarehq.org/case/transaction/v2",
           "@date_modified": "2013-09-01T11:02:34Z",
           "@user_id": "abcde",
           "@case_id": "test_case_123345",
           "update": {
               "location_code": "",
               "last_visit_counsel_topics": "bednet handwashing",
               "last_visit": "2013-10-09",
               "num_ec": "2"
           }
       },
       "member_available": {
           "#text": "yes",
           "@concept_id": "1890"
       },
       "modern_fp": [
           {
               "fp_type": {
                   "#text": "iud",
                   "@concept_id": "374"
               }
           },
           {
               "fp_type": {
                   "#text": "ij",
                   "@concept_id": "374"
               }
           }
       ],
       "meta": {
           "@xmlns": "http://openrosa.org/jr/xforms",
           "username": "airene",
           "instanceID": "some_form",
           "userID": "some_user",
           "timeEnd": "2013-09-09T11:02:34Z",
           "appVersion": {
               "@xmlns": "http://commcarehq.org/xforms",
               "#text": "some version"
           },
           "timeStart": "2013-09-01T11:22:40Z",
           "deviceID": "unittests"
       },
       "num_using_fp": {
           "#text": "2",
           "@concept_id": "1902"
       },
       "location_code_1": "",
       "counseling": {
           "sanitation_counseling": {
               "handwashing_importance": "",
               "handwashing_instructions": "",
               "when_to_wash_hands": ""
           },
           "counsel_type_ec": "bednet handwashing",
           "previous_counseling": "OK",
           "bednet_counseling": {
               "bednets_reduce_risk": "",
               "wash_bednet": "",
               "all_people_bednet": ""
           }
       },
       "prev_location_code": "",
       "@version": "234",
       "num_ec": {
           "#text": "2",
           "@concept_id": "1901"
       },
       "prev_counsel_topics": "handwashing"
   },
   "initial_processing_complete": True,
   "computed_modified_on_": "2013-10-01T23:13:38Z",
   "app_id": "some_app",
   "auth_context": {
       "user_id": None,
       "domain": "some-domain",
       "authenticated": False,
       "doc_type": "AuthContext"
   },
   "doc_type": "XFormInstance",
   "xmlns": "http://openrosa.org/formdesigner/something",
   "partial_submission": False,
   "#export_tag": [
       "domain",
       "xmlns"
   ],
   "received_on": "2013-10-09T14:21:56Z",
   "submit_ip": "105.230.106.73",
   "computed_": {},
   "openrosa_headers": {
       "HTTP_X_OPENROSA_VERSION": "1.0"
   },
   "history": [
   ],
   "__retrieved_case_ids": ["test_case_123345"],
}


@mock.patch('corehq.pillows.xform.get_user_type', new=lambda user_id: UNKNOWN_USER_TYPE)
class TestReportXFormProcessing(SimpleTestCase):

    def testConvertAndRestoreReportXFormDicts(self):
        orig = CONCEPT_XFORM
        orig['domain'] = settings.ES_XFORM_FULL_INDEX_DOMAINS[0]
        for_indexing = transform_xform_for_report_forms_index(orig)

        restored = restore_property_dict(for_indexing)

        #appVersion might be munged in meta, so swapping it out
        orig_appversion = orig['form']['meta']['appVersion']
        restored_appversion = restored['form']['meta']['appVersion']
        if isinstance(orig_appversion, dict):
            self.assertEqual(restored_appversion, orig_appversion['#text'])
        else:
            self.assertEqual(restored_appversion, orig_appversion)

        del(orig['form']['meta']['appVersion'])
        del(restored['form']['meta']['appVersion'])

        # user_type gets added in change_transform
        del(restored['user_type'])
        del(for_indexing['user_type'])

        # inserted during the transform
        del(restored['inserted_at'])
        del(for_indexing['inserted_at'])
        del(restored['form']['meta']['app_build_version'])
        del(restored['form']['meta']['commcare_version'])
        del(restored['form']['meta']['geo_point'])

        self.assertNotEqual(for_indexing, orig)
        self.assertNotEqual(for_indexing, restored)
        del restored['backend_id']
        self.assertEqual(orig, restored)

    def testSubCaseForm(self):
        """
        Ensure that the dict format converter never touches any sub property that has a key of 'case'

        this is our way of handling case blocks. The properties in the case block ought not to be touched

        this current form only captures
        """
        orig = {
            '_id': 'nested_case_blocks',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'case': {
                    "@xmlns": "http://commcarehq.org/case/transaction/v2",
                    "@date_modified": "2013-10-14T10:59:44Z",
                    "@user_id": "someuser",
                    "@case_id": "mycase",
                },
                'subcase_0': {
                    'case': {
                        "@xmlns": "http://commcarehq.org/case/transaction/v2",
                        "index": {
                            "parent": {
                                "@case_type": "household",
                                "#text": "some_parent"
                            }
                        },
                        "@date_modified": "2013-10-12T11:59:41Z",
                        "create": {
                            "case_type": "child",
                            "owner_id": "some_owner",
                            "case_name": "hello there"
                        },
                        "@user_id": "someuser",
                        "update": {
                            "first_name": "asdlfjkasdf",
                            "surname": "askljvlajskdlrwe",
                            "dob": "2011-03-21",
                            "sex": "male",
                            "weight_date": "never",
                            "household_head_health_id": "",
                            "dob_known": "yes",
                            "health_id": "",
                            "length_date": "never",
                            "dob_calc": "2011-03-21"
                        },
                        "@case_id": "subcaseid"
                    }
                },
                'really': {
                    'nested': {
                        'case': {
                        "@xmlns": "http://commcarehq.org/case/transaction/v2",
                        "index": {
                            "parent": {
                                "@case_type": "household",
                                "#text": "some_parent"
                            }
                        },
                        "@date_modified": "2013-10-12T11:59:41Z",
                        "create": {
                            "case_type": "child",
                            "owner_id": "some_owner",
                            "case_name": "hello there"
                        },
                        "@user_id": "someuser",
                        "update": {
                            "first_name": "asdlfjkasdf",
                            "surname": "askljvlajskdlrwe",
                            "dob": "2011-03-21",
                            "sex": "male",
                            "weight_date": "never",
                            "household_head_health_id": "",
                            "dob_known": "yes",
                            "health_id": "",
                            "length_date": "never",
                            "dob_calc": "2011-03-21"
                        },
                        "@case_id": "subcaseid2"
                        }
                    }
                },
                'array_cases': [
                    {'case': {'foo': 'bar'}},
                    {'case': {'boo': 'bar'}},
                    {'case': {'poo': 'bar'}},
                ]
            }
        }
        orig['domain'] = settings.ES_XFORM_FULL_INDEX_DOMAINS[0]
        for_indexing = transform_xform_for_report_forms_index(orig)

        self.assertEqual(orig['form']['case'], for_indexing['form']['case'])
        self.assertEqual(orig['form']['subcase_0']['case'], for_indexing['form']['subcase_0']['case'])
        self.assertEqual(orig['form']['really']['nested']['case'], for_indexing['form']['really']['nested']['case'])

    def testBlanktoNulls(self):
        orig = {
            '_id': 'blank_strings',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'case': {
                    "@xmlns": "http://commcarehq.org/case/transaction/v2",
                    "@date_modified": "2013-10-14T10:59:44Z",
                    "@user_id": "someuser",
                    "@case_id": "mycase",
                    "index": "",
                    "attachment": "",
                    "create": "",
                    "update": "",
                }
            }
        }

        dict_props = ['index', 'attachment', 'create', 'update']

        all_blank = copy.deepcopy(orig)
        all_blank['domain'] = settings.ES_XFORM_FULL_INDEX_DOMAINS[0]
        for_indexing = transform_xform_for_report_forms_index(all_blank)

        for prop in dict_props:
            self.assertIsNone(for_indexing['form']['case'][prop])

        all_dicts = copy.deepcopy(orig)
        all_dicts['domain'] = settings.ES_XFORM_FULL_INDEX_DOMAINS[0]
        for prop in dict_props:
            all_dicts['form']['case'][prop] = {}

        for_index2 = transform_xform_for_report_forms_index(all_dicts)
        for prop in dict_props:
            self.assertIsNotNone(for_index2['form']['case'][prop])

    def testComputedConversion(self):
        """
        Since we set dyanmic=True on reportxforms, need to do conversions on the computed_ properties
        so call conversion on computed_ dict as well, this test ensures that it's converted on change_transform
        :return:
        """
        orig = {
            '_id': 'blank_strings',
            'received_on': '2013-10-12T11:59:41Z',
            'form': {
                'case': {
                    "@xmlns": "http://commcarehq.org/case/transaction/v2",
                    "@date_modified": "2013-10-14T10:59:44Z",
                    "@user_id": "someuser",
                    "@case_id": "mycase",
                    "index": "",
                    "attachment": "",
                    "create": "",
                    "update": "",
                }
            },
            'computed_': {
                "mvp_indicators": {
                    "last_muac": {
                        "updated": "2013-02-04T21:54:28Z",
                        "version": 1,
                        "type": "FormDataAliasIndicatorDefinition",
                        "multi_value": False,
                        "value": None
                    },
                    "muac": {
                        "updated": "2013-02-04T21:54:28Z",
                        "version": 1,
                        "type": "FormDataAliasIndicatorDefinition",
                        "multi_value": False,
                        "value": {
                            "#text": "",
                           "@concept_id": "1343"
                        }
                    },
                    "vaccination_status": {
                        "updated": "2013-02-04T21:54:28Z",
                        "version": 1,
                        "type": "FormDataAliasIndicatorDefinition",
                        "multi_value": False,
                        "value": "yes"

                    },
                }
            }
        }
        orig['domain'] = settings.ES_XFORM_FULL_INDEX_DOMAINS[0]
        for_indexing = transform_xform_for_report_forms_index(orig)
        restored = restore_property_dict(for_indexing)

        self.assertNotEqual(orig['computed_'], for_indexing['computed_'])
        self.assertEqual(orig['computed_'], restored['computed_'])

    def testReporXFormtQuery(self):

        unknown_terms = ['form.num_using_fp.#text', 'form.num_using_fp.@concept_id',
                         'form.counseling.sanitation_counseling.handwashing_importance',
                         'form.counseling.bednet_counseling.wash_bednet',
                         'form.prev_location_code',
                         'member_available.#text',
                         'location_code_1']
        unknown_terms_query = report_term_filter(unknown_terms, REPORT_XFORM_MAPPING)

        manually_set = ['%s.%s' % (x, VALUE_TAG) for x in unknown_terms]
        self.assertEqual(manually_set, unknown_terms_query)

        known_terms = [
            'initial_processing_complete',
            'doc_type',
            'app_id',
            'xmlns',
            '@uiVersion',
            '@version',
            'form.#type',
            'form.@name',
            'form.meta.timeStart',
            'form.meta.timeEnd',
            'form.meta.appVersion',
            ]

        # shoot, TODO, cases are difficult to escape the VALUE_TAG term due to dynamic templates
        known_terms_query = report_term_filter(known_terms, REPORT_XFORM_MAPPING)
        self.assertEqual(known_terms_query, known_terms)

    def testConceptReportConversion(self):
        orig = CONCEPT_XFORM
        orig['domain'] = settings.ES_XFORM_FULL_INDEX_DOMAINS[0]
        for_indexing = transform_xform_for_report_forms_index(orig)

        self.assertTrue(isinstance(for_indexing['form']['last_visit'], dict))
        self.assertTrue('#value' in for_indexing['form']['last_visit'])

        self.assertTrue(isinstance(for_indexing['form']['member_available'], dict))
        self.assertTrue(isinstance(for_indexing['form']['member_available']['#text'], dict))
        self.assertTrue(isinstance(for_indexing['form']['member_available']['@concept_id'], dict))

        self.assertEqual(for_indexing['form']['member_available'],
                         {
                             "#text": {
                                 "#value": "yes"
                             },
                             "@concept_id": {
                                 "#value": "1890"
                             }
                         }
        )
        self.assertEqual(for_indexing['form']['modern_fp'],
                         [
                             {
                                 "fp_type": {
                                     "#text": {
                                         "#value": "iud"
                                     },
                                     "@concept_id": {
                                         "#value": "374"
                                     }
                                 }
                             },
                             {
                                 "fp_type": {
                                     "#text": {
                                         "#value": "ij"
                                     },
                                     "@concept_id": {
                                         "#value": "374"
                                     }
                                 }
                             }
                         ]
        )
