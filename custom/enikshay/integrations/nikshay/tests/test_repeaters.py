# -*- coding: utf-8 -*-

from __future__ import absolute_import
import json
import os

from mock import patch
from collections import namedtuple
from datetime import date, datetime
from django.test import TestCase, override_settings

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.apps.locations.models import SQLLocation
from corehq.apps.domain.models import Domain
from corehq.util.test_utils import flag_enabled, capture_log_output
from custom.enikshay.const import (
    TREATMENT_OUTCOME,
    TREATMENT_OUTCOME_DATE,
    EPISODE_PENDING_REGISTRATION,
    PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION,
    ENROLLED_IN_PRIVATE,
    PERSON_CASE_2B_VERSION,
    REAL_DATASET_PROPERTY_VALUE,
    PRIVATE_HEALTH_ESTABLISHMENT_SECTOR,
    AGENCY_LOCATION_TYPES,
    HEALTH_ESTABLISHMENT_TYPES_TO_FORWARD,
    DUMMY_VALUES,
    NOT_AVAILABLE_VALUE,
)
from custom.enikshay.exceptions import NikshayLocationNotFound, NikshayRequiredValueMissing
from custom.enikshay.integrations.nikshay.field_mappings import (
    health_establishment_sector,
    health_establishment_type,
)
from custom.enikshay.integrations.nikshay.repeaters import (
    NikshayRegisterPatientRepeater,
    NikshayHIVTestRepeater,
    NikshayTreatmentOutcomeRepeater,
    NikshayFollowupRepeater,
    NikshayRegisterPrivatePatientRepeater,
    NikshayHealthEstablishmentRepeater,
)
from custom.enikshay.tests.utils import (
    ENikshayCaseStructureMixin,
    ENikshayLocationStructureMixin,
    setup_enikshay_locations,
)
from custom.enikshay.integrations.nikshay.repeater_generator import (
    NikshayRegisterPatientPayloadGenerator,
    NikshayTreatmentOutcomePayload,
    NikshayHIVTestPayloadGenerator,
    NikshayFollowupPayloadGenerator,
    NikshayRegisterPrivatePatientPayloadGenerator,
    ENIKSHAY_ID,
    NikshayHealthEstablishmentPayloadGenerator,
)
from custom.enikshay.case_utils import update_case

from casexml.apps.case.mock import CaseStructure
from corehq.motech.repeaters.models import RepeatRecord
from corehq.motech.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from casexml.apps.case.tests.util import delete_all_cases
import six
from corehq.apps.locations.tasks import make_location_user

DUMMY_NIKSHAY_ID = "DM-DMO-01-16-0137"

MockNikshayRegisterPrivatePatientRepeater = namedtuple('MockRepeater', 'url operation verify')
MockNikshayRegisterPrivatePatientRepeatRecord = namedtuple('MockRepeatRecord', 'repeater')


WSDL_URL = os.path.join(os.path.dirname(__file__), 'nikshay.wsdl')


class MockResponse(object):
    def __init__(self, status_code, json_data):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


class MockSoapResponse(object):
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content
        self.headers = {'Content-Type': 'text/xml; charset=utf-8'}
        self.reason = "hooray!"

FAILURE_RESPONSE = (
    '<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
    '<soap:Body><InsertHFIDPatient_UATBCResponse xmlns="http://tempuri.org/"><InsertHFIDPatient_UATBCResult>'
    'Invalid data format</InsertHFIDPatient_UATBCResult></InsertHFIDPatient_UATBCResponse></soap:Body>'
    '</soap:Envelope>')

SUCCESSFUL_SOAP_RESPONSE = (
    '<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
    '<soap:Body><InsertHFIDPatient_UATBCResponse xmlns="http://tempuri.org/"><InsertHFIDPatient_UATBCResult>'
    '000001</InsertHFIDPatient_UATBCResult></InsertHFIDPatient_UATBCResponse></soap:Body></soap:Envelope>')

DUMMY_HEALTH_ESTABLISHMENT_ID = '125344'
DUMMY_REGISTERED_HEALTH_ESTABLISHMENT_ID = '987654'

SUCCESSFUL_HEALTH_ESTABLISHMENT_RESPONSE = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
        '<soap:Body>'
            '<HE_RegistrationResponse xmlns="http://tempuri.org/">'
                '<HE_RegistrationResult>'
                    '<diffgr:diffgram xmlns:msdata="urn:schemas-microsoft-com:xml-msdata" '
                            'xmlns:diffgr="urn:schemas-microsoft-com:xml-diffgram-v1">'
                        '<NewDataSet xmlns="">'
                            '<HE_DETAILS diffgr:id="HE_DETAILS1" msdata:rowOrder="0" diffgr:hasChanges="inserted">'
                                '<Message>HE_ID: {dummy_id}</Message>'
                            '</HE_DETAILS>'
                        '</NewDataSet>'
                    '</diffgr:diffgram>'
                '</HE_RegistrationResult>'
            '</HE_RegistrationResponse>'
        '</soap:Body>'
    '</soap:Envelope>'
).format(dummy_id=DUMMY_HEALTH_ESTABLISHMENT_ID)

ALREADY_REGISTERED_ESTABLISHMENT_RESPONSE = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
        '<soap:Body>'
            '<HE_RegistrationResponse xmlns="http://tempuri.org/">'
                '<HE_RegistrationResult>'
                    '<diffgr:diffgram xmlns:msdata="urn:schemas-microsoft-com:xml-msdata" '
                        'xmlns:diffgr="urn:schemas-microsoft-com:xml-diffgram-v1">'
                    '<NewDataSet xmlns="">'
                        '<Table1 diffgr:id="Table11" msdata:rowOrder="0" diffgr:hasChanges="inserted">'
                            '<HE_ID>{dummy_id}</HE_ID>'
                            '<ESTABLISHMENT_TYPE>Laboratory</ESTABLISHMENT_TYPE>'
                            '<SECTOR>Private (including NGOs)</SECTOR>'
                            '<ESTABLISHMENT_NAME>Health Care Diagnostic Centre 700800</ESTABLISHMENT_NAME>'
                            '<MCI_HR_NO>12345</MCI_HR_NO>'
                            '<CONTACT_PNAME>Health Care Diagnostic Centre</CONTACT_PNAME>'
                            '<CONTACT_PESIGNATION>NA</CONTACT_PESIGNATION>'
                            '<TELEPHONE_NO>9999999999</TELEPHONE_NO>'
                            '<MOBILE_NO>9999999999</MOBILE_NO>'
                            '<COMPLETE_ADDRESS>V N Desai Hospital 179 B Jama Masjid Lane </COMPLETE_ADDRESS>'
                            '<PINCODE>400098</PINCODE>'
                            '<EMAILID>abc@xyz.com</EMAILID>'
                            '<STATE>Maharashtra</STATE>'
                            '<DISTRICT>Bandra East</DISTRICT>'
                            '<Status>Already Exists</Status>'
                        '</Table1>'
                    '</NewDataSet>'
                    '</diffgr:diffgram>'
                '</HE_RegistrationResult>'
            '</HE_RegistrationResponse>'
        '</soap:Body>'
    '</soap:Envelope>'
).format(dummy_id=DUMMY_REGISTERED_HEALTH_ESTABLISHMENT_ID)


class NikshayRepeaterTestBase(ENikshayCaseStructureMixin, TestCase):
    def setUp(self):
        super(NikshayRepeaterTestBase, self).setUp()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def tearDown(self):
        super(NikshayRepeaterTestBase, self).tearDown()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.utcnow())

    def _create_nikshay_enabled_case(self, case_id=None, set_property=EPISODE_PENDING_REGISTRATION):
        if case_id is None:
            case_id = self.episode_id

        nikshay_enabled_case_on_update = CaseStructure(
            case_id=case_id,
            attrs={
                "create": False,
                "update": {
                    set_property: 'no',
                }
            }
        )

        return self.create_case(nikshay_enabled_case_on_update)[0]

    def _create_nikshay_registered_case(self):
        nikshay_registered_case = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'create': False,
                "update": dict(
                    nikshay_registered='true',
                    nikshay_id=DUMMY_NIKSHAY_ID,
                )
            }
        )
        self.create_case(nikshay_registered_case)

    def _assert_case_property_equal(self, case, case_property, expected_value):
        self.assertEqual(case.dynamic_case_properties().get(case_property), expected_value)

    def set_up_to_use_2b_version(self):
        update_case(self.domain, self.person_id, {
            'case_version': PERSON_CASE_2B_VERSION,
            'dataset': REAL_DATASET_PROPERTY_VALUE,
        })

        update_case(self.domain, self.occurrence_id, {
            'site_choice': 'pleural_effusion',
            'disease_classification': 'extra_pulmonary',
        })

        update_case(self.domain, self.person_id, {
            'occupation': 'engineer',
        })

        update_case(self.domain, self.episode_id, {
            'occupation': '',
            'site_choice': '',
            'disease_classification': '',
        })
        update_case(self.domain, self.test_id, {
            "rft_general": 'diagnosis_dstb',
            "rft_dstb_followup": 'end_of_ip',
            'purpose_of_testing': '',
            'follow_up_test_reason': '',
        })


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestNikshayRegisterPatientRepeater(ENikshayLocationStructureMixin, NikshayRepeaterTestBase):

    def setUp(self):
        super(TestNikshayRegisterPatientRepeater, self).setUp()

        self.repeater = NikshayRegisterPatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
            username='test-user'
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_not_available_for_domain(self):
        self.assertFalse(NikshayRegisterPatientRepeater.available_for_domain(self.domain))

    @flag_enabled('NIKSHAY_INTEGRATION')
    def test_available_for_domain(self):
        self.assertTrue(NikshayRegisterPatientRepeater.available_for_domain(self.domain))

    def test_trigger(self):
        # nikshay not enabled
        self.create_case(self.episode)
        self.assertEqual(0, len(self.repeat_records().all()))

        person = self.create_case(self.person)[0]
        with capture_log_output('notify') as logoutput:
            self._create_nikshay_enabled_case()
        self.assertIn(NikshayLocationNotFound.__name__, logoutput.get_output())
        expected_message = (
            "Location with id {location_id} not found. "
            "This is the owner for person with id: {person_id}".format(
                location_id=person.owner_id, person_id=self.person_id)
        )
        self.assertIn(expected_message, logoutput.get_output())

        # nikshay enabled, should register a repeat record
        self.assign_person_to_location(self.phi.location_id)
        self._create_nikshay_enabled_case()
        self.assertEqual(1, len(self.repeat_records().all()))

        # set as registered, should not register a new repeat record
        self._create_nikshay_registered_case()
        self.assertEqual(1, len(self.repeat_records().all()))

    def test_trigger_different_case_type(self):
        # different case type
        self.create_case(self.person)
        self._create_nikshay_enabled_case(case_id=self.person_id)
        self.assertEqual(0, len(self.repeat_records().all()))

    def test_trigger_test_submission(self):
        self.phi.metadata['is_test'] = 'yes'
        self.phi.save()
        self.create_case(self.episode)
        self.assign_person_to_location(self.phi.location_id)
        self._create_nikshay_enabled_case()
        self.assertEqual(0, len(self.repeat_records().all()))

        self.set_up_to_use_2b_version()
        self.phi.metadata['is_test'] = 'no'
        self.phi.save()
        update_case(self.domain, self.person_id, {
            'dataset': 'unreal'
        })
        self._create_nikshay_enabled_case()
        self.assertEqual(0, len(self.repeat_records().all()))

    def test_trigger_non_test_submission(self):
        self.phi.metadata['is_test'] = 'no'
        self.phi.save()
        self.create_case(self.episode)
        self.assign_person_to_location(self.phi.location_id)
        self._create_nikshay_enabled_case()
        self.assertEqual(1, len(self.repeat_records().all()))

        self.set_up_to_use_2b_version()
        self.phi.metadata['is_test'] = 'no'
        self.phi.save()
        update_case(self.domain, self.person_id, {
            'dataset': 'real'
        })
        self._create_nikshay_enabled_case()
        self.assertEqual(2, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestNikshayRegisterPatientPayloadGenerator(ENikshayLocationStructureMixin, NikshayRepeaterTestBase):
    def setUp(self):
        super(TestNikshayRegisterPatientPayloadGenerator, self).setUp()
        self.cases = self.create_case_structure()
        self.assign_person_to_location(self.phi.location_id)

    def test_payload_properties(self):
        episode_case = self._create_nikshay_enabled_case()
        payload = (json.loads(
            NikshayRegisterPatientPayloadGenerator(None).get_payload(None, episode_case))
        )
        self.assertEqual(payload['Source'], ENIKSHAY_ID)
        self.assertEqual(payload['Local_ID'], self.person_id)
        self.assertEqual(payload['regBy'], "tbu-dmdmo01")

        # From Person
        self.assertEqual(payload['pname'], u"Peregrine เՇร ค Շгคק")
        self.assertEqual(payload['page'], '20')
        self.assertEqual(payload['pgender'], 'M')
        self.assertEqual(payload['paddress'], 'Mt. Everest')
        self.assertEqual(payload['pmob'], self.primary_phone_number)
        self.assertEqual(payload['cname'], 'Mrs. Everestie')
        self.assertEqual(payload['caddress'], 'Mrs. Everestie')
        self.assertEqual(payload['cmob'], self.secondary_phone_number)
        self.assertEqual(payload['pcategory'], '2')

        # From Episode
        self.assertEqual(payload['sitedetail'], 2)
        self.assertEqual(payload['Ptype'], '4')
        self.assertEqual(payload['poccupation'], 4)
        self.assertEqual(payload['dotname'], u'𝔊𝔞𝔫𝔡𝔞𝔩𝔣 𝔗𝔥𝔢 𝔊𝔯𝔢𝔶')
        self.assertEqual(payload['dotmob'], '066000666')
        self.assertEqual(payload['disease_classification'], 'EP')
        self.assertEqual(payload['pregdate'], '2014-09-09')
        self.assertEqual(payload['ptbyr'], '2014')
        self.assertEqual(payload['dotpType'], '5')
        self.assertEqual(payload['dotdesignation'], 'ngo_volunteer')
        self.assertEqual(payload['dateofInitiation'], '2015-03-03')

        self.set_up_to_use_2b_version()
        payload = (json.loads(
            NikshayRegisterPatientPayloadGenerator(None).get_payload(None, episode_case))
        )
        self.assertEqual(payload['sitedetail'], 2)
        self.assertEqual(payload['disease_classification'], 'EP')
        self.assertEqual(payload['poccupation'], 4)

    def test_age(self):
        self._create_nikshay_enabled_case()
        update_case(self.domain, self.person_id, {'age': '2.6'})
        episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        payload = (json.loads(
            NikshayRegisterPatientPayloadGenerator(None).get_payload(None, episode_case))
        )
        self.assertEqual(payload['page'], '2')

        update_case(self.domain, self.person_id, {'age': '0.6'})
        episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        payload = (json.loads(
            NikshayRegisterPatientPayloadGenerator(None).get_payload(None, episode_case))
        )
        self.assertEqual(payload['page'], '1')

    def test_username_password(self):
        episode_case = self._create_nikshay_enabled_case()
        username = "arwen"
        password = "Hadhafang"

        MockRepeater = namedtuple('MockRepeater', 'username password')
        MockRepeatRecord = namedtuple('MockRepeatRecord', 'repeater')

        repeat_record = MockRepeatRecord(MockRepeater(username=username, password=password))
        payload = (json.loads(
            NikshayRegisterPatientPayloadGenerator(None).get_payload(repeat_record, episode_case))
        )
        self.assertEqual(payload['regBy'], username)
        self.assertEqual(payload['password'], password)

    def test_handle_success(self):
        nikshay_id = "NIKSHAY!"
        self._create_nikshay_enabled_case()
        payload_generator = NikshayRegisterPatientPayloadGenerator(None)
        payload_generator.handle_success(
            MockResponse(
                201,
                {
                    "Nikshay_Message": "Success",
                    "Results": [
                        {
                            "FieldName": "NikshayId",
                            "Fieldvalue": nikshay_id,
                        }
                    ]
                }
            ),
            self.cases[self.episode_id],
            None,
        )
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self._assert_case_property_equal(updated_episode_case, 'nikshay_registered', 'true')
        self._assert_case_property_equal(updated_episode_case, 'nikshay_error', '')
        self._assert_case_property_equal(updated_episode_case, 'nikshay_id', nikshay_id)
        self.assertEqual(updated_episode_case.external_id, nikshay_id)

    def test_handle_bad_nikshay_response(self):
        self._create_nikshay_enabled_case()
        payload_generator = NikshayRegisterPatientPayloadGenerator(None)
        response = {
            "Nikshay_Message": "Success",
            "Results": [
                {
                    "FieldName": "BadResponse",
                    "Fieldvalue": "Borked",
                }
            ]
        }
        payload_generator.handle_success(
            MockResponse(
                201,
                response,
            ),
            self.cases[self.episode_id],
            None,
        )
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self._assert_case_property_equal(updated_episode_case, 'nikshay_registered', 'false')
        self._assert_case_property_equal(
            updated_episode_case,
            'nikshay_error',
            'No Nikshay ID received: {}'.format(response)
        )

    def test_handle_duplicate(self):
        payload_generator = NikshayRegisterPatientPayloadGenerator(None)
        payload_generator.handle_failure(
            MockResponse(
                409,
                {
                    "Nikshay_Message": "Conflict",
                    "Results": [
                        {
                            "FieldName": "NikshayId",
                            "Fieldvalue": "Dublicate Entry"
                        }
                    ]
                }
            ),
            self.cases[self.episode_id],
            None,
        )
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self._assert_case_property_equal(updated_episode_case, 'nikshay_registered', 'true')
        self._assert_case_property_equal(updated_episode_case, 'nikshay_error', 'duplicate')

    def test_handle_failure(self):
        message = {
            "Nikshay_Message": "Success",
            "Results": [
                {
                    "FieldName": "NikshayId",
                    "Fieldvalue": "The INSERT statement conflicted with the FOREIGN KEY constraint \"FK_PatientsDetails_TBUnits\". The conflict occurred in database \"nikshay\", table \"dbo.TBUnits\".\u000d\u000a \u000d\u000aDM-ABC-01-16-0001\u000d\u000aThe statement has been terminated."  # noqa. yes, this is a real response.
                }
            ]
        }
        payload_generator = NikshayRegisterPatientPayloadGenerator(None)
        payload_generator.handle_failure(
            MockResponse(
                400,
                message,
            ),
            self.cases[self.episode_id],
            None,
        )
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self._assert_case_property_equal(updated_episode_case, 'nikshay_registered', 'false')
        self._assert_case_property_equal(updated_episode_case, 'nikshay_error', six.text_type(message))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestNikshayHIVTestRepeater(ENikshayLocationStructureMixin, NikshayRepeaterTestBase):

    def setUp(self):
        super(TestNikshayHIVTestRepeater, self).setUp()

        self.repeater = NikshayHIVTestRepeater(
            domain=self.domain,
            url='case-repeater-url',
            username='test-user'
        )
        self.repeater.white_listed_case_types = ['person']
        self.repeater.save()

    def test_not_available_for_domain(self):
        self.assertFalse(NikshayHIVTestRepeater.available_for_domain(self.domain))

    @flag_enabled('NIKSHAY_INTEGRATION')
    def test_available_for_domain(self):
        self.assertTrue(NikshayHIVTestRepeater.available_for_domain(self.domain))

    def test_trigger(self):
        # nikshay not enabled
        self.create_case(self.episode)
        self._create_nikshay_enabled_case()
        update_case(self.domain, self.person_id, {
            "owner_id": self.phi.location_id,
        })
        self._create_nikshay_registered_case()
        self.assertEqual(0, len(self.repeat_records().all()))

        update_case(self.domain, self.person_id, {
            "hiv_status": "unknown",
            "owner_id": self.phi.location_id,
        })
        self.assertEqual(1, len(self.repeat_records().all()))

        update_case(self.domain, self.person_id, {
            "hiv_status": "reactive",
            "cpt_1_date": "2016-01-01"
        })
        self.assertEqual(2, len(self.repeat_records().all()))

        update_case(self.domain, self.person_id, {
            "art_initiation_date": "2016-02-01"
        })
        self.assertEqual(3, len(self.repeat_records().all()))

    def test_trigger_test_submission(self):
        self.phi.metadata['is_test'] = 'yes'
        self.phi.save()
        self.create_case(self.episode)
        self._create_nikshay_enabled_case()
        self._create_nikshay_registered_case()
        update_case(self.domain, self.person_id, {
            "hiv_status": "unknown",
            "owner_id": self.phi.location_id,
        })
        self.assertEqual(0, len(self.repeat_records().all()))

        self.set_up_to_use_2b_version()
        self.phi.metadata['is_test'] = 'no'
        self.phi.save()
        update_case(self.domain, self.person_id, {
            'dataset': 'unreal'
        })
        update_case(self.domain, self.person_id, {
            "hiv_status": "unknown",
            "owner_id": self.phi.location_id,
        })
        self.assertEqual(0, len(self.repeat_records().all()))

    def test_trigger_non_test_submission(self):
        self.phi.metadata['is_test'] = 'no'
        self.phi.save()
        self.create_case(self.episode)
        self._create_nikshay_enabled_case()
        update_case(self.domain, self.person_id, {
            "owner_id": self.phi.location_id,
        })
        self._create_nikshay_registered_case()
        update_case(self.domain, self.person_id, {
            "hiv_status": "unknown",
            "owner_id": self.phi.location_id,
        })
        self.assertEqual(1, len(self.repeat_records().all()))

        self.set_up_to_use_2b_version()
        self.phi.metadata['is_test'] = 'no'
        self.phi.save()
        update_case(self.domain, self.person_id, {
            'dataset': 'real'
        })
        update_case(self.domain, self.person_id, {
            "hiv_status": "unknown",
            "owner_id": self.phi.location_id,
        })
        self.assertEqual(2, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestNikshayHIVTestPayloadGenerator(ENikshayLocationStructureMixin, NikshayRepeaterTestBase):
    def setUp(self):
        super(TestNikshayHIVTestPayloadGenerator, self).setUp()
        self.cases = self.create_case_structure()
        self.person_case = self.cases['person']
        self.episode_case = self.cases['episode']
        self._create_nikshay_registered_case()

        MockRepeater = namedtuple('MockRepeater', 'username password')
        MockRepeatRecord = namedtuple('MockRepeatRecord', 'repeater')
        self.repeat_record = MockRepeatRecord(MockRepeater(username="arwen", password="Hadhafang"))

    def create_case_structure(self):
        return {case.get_id: case for case in [_f for _f in self.factory.create_or_update_cases(
            [self.person, self.episode]) if _f]}

    def _create_nikshay_registered_case(self):
        update_case(self.domain, self.episode_id, {
            "nikshay_id": DUMMY_NIKSHAY_ID,
        }, external_id=DUMMY_NIKSHAY_ID)

    @patch("socket.gethostbyname", return_value="198.1.1.1")
    def test_payload_properties(self, _):
        update_case(self.domain, self.person_id, {
            "hiv_status": "unknown",
            "hiv_test_date": "2016-01-01",
        })
        self.person_case = CaseAccessors(self.domain).get_case(self.person_id)
        payload = (json.loads(
            NikshayHIVTestPayloadGenerator(None).get_payload(self.repeat_record, self.person_case))
        )
        self.assertEqual(payload['Source'], ENIKSHAY_ID)
        self.assertEqual(payload['regby'], "arwen")
        self.assertEqual(payload['password'], "Hadhafang")
        self.assertEqual(payload['IP_FROM'], "198.1.1.1")
        self.assertEqual(payload["PatientID"], DUMMY_NIKSHAY_ID)

        self.assertEqual(payload["HIVStatus"], "Unknown")
        self.assertEqual(payload["HIVTestDate"], "01/01/2016")

        self.assertEqual(payload["CPTDeliverDate"], "01/01/1900")
        self.assertEqual(payload["InitiatedDate"], "01/01/1900")
        self.assertEqual(payload["ARTCentreDate"], "01/01/1900")

        update_case(self.domain, self.person_id, {
            "cpt_1_date": "2016-01-02",
        })
        self.person_case = CaseAccessors(self.domain).get_case(self.person_id)

        payload = (json.loads(
            NikshayHIVTestPayloadGenerator(None).get_payload(self.repeat_record, self.person_case))
        )

        self.assertEqual(payload["CPTDeliverDate"], "02/01/2016")
        self.assertEqual(payload["InitiatedDate"], "01/01/1900")
        self.assertEqual(payload["ARTCentreDate"], "01/01/1900")

        update_case(self.domain, self.person_id, {
            "art_initiation_date": "2016-04-03",
            "art_initiated": "yes"
        })

        self.person_case = CaseAccessors(self.domain).get_case(self.person_id)
        payload = (json.loads(
            NikshayHIVTestPayloadGenerator(None).get_payload(self.repeat_record, self.person_case))
        )

        self.assertEqual(payload["CPTDeliverDate"], "02/01/2016")
        self.assertEqual(payload["InitiatedDate"], "03/04/2016")
        self.assertEqual(payload["ARTCentreDate"], "03/04/2016")

        update_case(self.domain, self.person_id, {
            "art_initiation_date": "foo",
        })

        self.person_case = CaseAccessors(self.domain).get_case(self.person_id)
        payload = (json.loads(
            NikshayHIVTestPayloadGenerator(None).get_payload(self.repeat_record, self.person_case))
        )

        self.assertEqual(payload["CPTDeliverDate"], "02/01/2016")
        self.assertEqual(payload["InitiatedDate"], "01/01/1900")
        self.assertEqual(payload["ARTCentreDate"], "01/01/1900")


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestNikshayTreatmentOutcomeRepeater(ENikshayLocationStructureMixin, NikshayRepeaterTestBase):

    def setUp(self):
        super(TestNikshayTreatmentOutcomeRepeater, self).setUp()

        self.repeater = NikshayTreatmentOutcomeRepeater(
            domain=self.domain,
            url='case-repeater-url',
            username='test-user'
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_not_available_for_domain(self):
        self.assertFalse(NikshayTreatmentOutcomeRepeater.available_for_domain(self.domain))

    @flag_enabled('NIKSHAY_INTEGRATION')
    def test_available_for_domain(self):
        self.assertTrue(NikshayTreatmentOutcomeRepeater.available_for_domain(self.domain))

    def test_trigger_test_submission(self):
        self.phi.metadata['is_test'] = 'yes'
        self.phi.save()
        self.create_case(self.episode)
        self.assign_person_to_location(self.phi.location_id)
        self._create_nikshay_registered_case()
        self.assertEqual(0, len(self.repeat_records().all()))

        update_case(self.domain, self.episode_id, {
            TREATMENT_OUTCOME: "cured",
        })
        self.assertEqual(0, len(self.repeat_records().all()))

        self.set_up_to_use_2b_version()
        self.phi.metadata['is_test'] = 'no'
        self.phi.save()
        update_case(self.domain, self.person_id, {
            'dataset': 'unreal'
        })
        update_case(self.domain, self.episode_id, {
            TREATMENT_OUTCOME: "cured",
        })
        self.assertEqual(0, len(self.repeat_records().all()))

    def test_trigger_non_test_submission(self):
        self.phi.metadata['is_test'] = 'no'
        self.phi.save()
        self.create_case(self.episode)
        self.assign_person_to_location(self.phi.location_id)
        self._create_nikshay_registered_case()
        self.assertEqual(0, len(self.repeat_records().all()))

        update_case(self.domain, self.episode_id, {
            TREATMENT_OUTCOME: "cured",
        })
        self.assertEqual(1, len(self.repeat_records().all()))

        self.set_up_to_use_2b_version()
        self.phi.metadata['is_test'] = 'no'
        self.phi.save()
        update_case(self.domain, self.person_id, {
            'dataset': 'real'
        })
        update_case(self.domain, self.episode_id, {
            TREATMENT_OUTCOME: "cured",
        })
        self.assertEqual(2, len(self.repeat_records().all()))

    def test_trigger(self):
        # nikshay not enabled
        self.create_case(self.episode)
        self.assign_person_to_location(self.phi.location_id)
        self._create_nikshay_registered_case()
        self.assertEqual(0, len(self.repeat_records().all()))

        # change triggered
        update_case(self.domain, self.episode_id, {
            TREATMENT_OUTCOME: "cured",
        })
        self.assertEqual(1, len(self.repeat_records().all()))

        # treatment outcome updated
        update_case(self.domain, self.episode_id,
        {
            TREATMENT_OUTCOME: "treatment_complete",
        })
        self.assertEqual(2, len(self.repeat_records().all()))

        # dont trigger for unknown outcome values
        update_case(self.domain, self.episode_id, {
            TREATMENT_OUTCOME: "james_bond",
        })
        self.assertEqual(2, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestNikshayTreatmentOutcomePayload(ENikshayLocationStructureMixin, NikshayRepeaterTestBase):
    def setUp(self):
        super(TestNikshayTreatmentOutcomePayload, self).setUp()
        self.cases = self.create_case_structure()
        self.assign_person_to_location(self.phi.location_id)

    @patch("socket.gethostbyname", return_value="198.1.1.1")
    def test_payload_properties(self, _):
        self._create_nikshay_enabled_case()
        update_case(self.domain, self.episode_id, {
            TREATMENT_OUTCOME: "treatment_complete",
            TREATMENT_OUTCOME_DATE: "1990-01-01",
            'nikshay_id': self.person_id,
        })
        episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        payload = (json.loads(
            NikshayTreatmentOutcomePayload(None).get_payload(None, episode_case))
        )
        self.assertEqual(payload['Source'], ENIKSHAY_ID)
        self.assertEqual(payload['IP_From'], "198.1.1.1")
        self.assertEqual(payload['PatientID'], self.person_id)
        self.assertEqual(payload['regBy'], "tbu-dmdmo01")
        self.assertEqual(payload['OutcomeDate'], "1990-01-01")
        self.assertEqual(payload['MO'], u"𝔊𝔞𝔫𝔡𝔞𝔩𝔣 𝔗𝔥𝔢 𝔊𝔯𝔢𝔶")
        self.assertEqual(payload['MORemark'], 'None Collected in eNikshay')
        self.assertEqual(payload['Outcome'], '2')

        update_case(self.domain, self.episode_id, {
            TREATMENT_OUTCOME: "regimen_changed",
        })
        episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        payload = (json.loads(
            NikshayTreatmentOutcomePayload(None).get_payload(None, episode_case))
        )
        self.assertEqual(payload['Outcome'], '7')


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestNikshayFollowupRepeater(ENikshayLocationStructureMixin, NikshayRepeaterTestBase):

    def setUp(self):
        super(TestNikshayFollowupRepeater, self).setUp()

        self.repeater = NikshayFollowupRepeater(
            domain=self.domain,
            url='case-repeater-url',
            username='test-user'
        )
        self.repeater.white_listed_case_types = ['test']
        self.repeater.save()

    def test_not_available_for_domain(self):
        self.assertFalse(NikshayFollowupRepeater.available_for_domain(self.domain))

    @flag_enabled('NIKSHAY_INTEGRATION')
    def test_available_for_domain(self):
        self.assertTrue(NikshayFollowupRepeater.available_for_domain(self.domain))

    def test_followup_for_tests(self):
        self.assertEqual(NikshayFollowupRepeater().followup_for_tests, ['end_of_ip', 'end_of_cp'])

    def test_trigger(self):
        self.repeat_record_count = 0

        def check_repeat_record_added():
            if len(self.repeat_records().all()) > self.repeat_record_count:
                self.repeat_record_count = len(self.repeat_records().all())
                return True
            else:
                return False

        self.assertEqual(0, len(self.repeat_records().all()))

        self.factory.create_or_update_cases([self.lab_referral, self.episode])
        self._create_nikshay_enabled_case()
        update_case(self.domain, self.person_id, {
            "owner_id": self.phi.location_id,
        })
        update_case(self.domain, self.test_id, {"date_reported": datetime.now()})
        self.assertTrue(check_repeat_record_added())

        # skip if test submission
        self.dmc.metadata['is_test'] = 'yes'
        self.dmc.save()
        update_case(self.domain, self.test_id, {"date_reported": datetime.now()})
        self.assertFalse(check_repeat_record_added())
        self.dmc.metadata['is_test'] = 'no'
        self.dmc.save()

        update_case(self.domain, self.test_id, {"date_reported": datetime.now()})
        self.assertTrue(check_repeat_record_added())

        # allow update for diagnostic tests irrespective of the follow up test reason
        update_case(self.domain, self.test_id, {
            "date_reported": datetime.now(),
            "purpose_of_testing": 'diagnostic',
            "follow_up_test_reason": 'end_of_no_p',
        })
        self.assertTrue(check_repeat_record_added())

        # ensure followup test reason is in the allowed ones
        update_case(self.domain, self.test_id, {
            "date_reported": datetime.now(),
            "purpose_of_testing": 'just like that',
            "follow_up_test_reason": 'end_of_no_p'
        })
        self.assertFalse(check_repeat_record_added())

        update_case(self.domain, self.test_id, {
            "date_reported": datetime.now(),
            "purpose_of_testing": 'just like that',
            "follow_up_test_reason": 'end_of_ip',
        })
        self.assertTrue(check_repeat_record_added())

        # ensure date tested is added for the test
        update_case(self.domain, self.test_id, {
            "follow_up_test_reason": 'end_of_ip'
        })
        self.assertFalse(check_repeat_record_added())

        # ensure test type is in the allowed ones
        update_case(self.domain, self.test_id, {
            "date_reported": datetime.now(),
            "follow_up_test_reason": 'end_of_ip',
            "test_type_value": 'irrelevant-test'
        })
        self.assertFalse(check_repeat_record_added())

        self.set_up_to_use_2b_version()
        update_case(self.domain, self.test_id, {
            "test_type_value": "microscopy-zn",
            "date_reported": datetime.now(),
        })
        self.assertTrue(check_repeat_record_added())

    def test_trigger_test_submission(self):
        self.dmc.metadata['is_test'] = 'yes'
        self.dmc.save()
        self.factory.create_or_update_cases([self.lab_referral, self.episode])
        update_case(self.domain, self.person_id, {
            "owner_id": self.phi.location_id,
        })
        self._create_nikshay_enabled_case()
        self._create_nikshay_registered_case()
        self.assertEqual(0, len(self.repeat_records().all()))
        update_case(self.domain, self.test_id, {
            "date_reported": datetime.now()
        })
        self.assertEqual(0, len(self.repeat_records().all()))

    def test_trigger_non_test_submission(self):
        self.dmc.metadata['is_test'] = 'no'
        self.dmc.save()
        self.factory.create_or_update_cases([self.lab_referral, self.episode])
        update_case(self.domain, self.person_id, {
            "owner_id": self.phi.location_id,
        })
        self._create_nikshay_enabled_case()
        self._create_nikshay_registered_case()
        self.assertEqual(0, len(self.repeat_records().all()))
        update_case(self.domain, self.test_id, {
            "date_reported": datetime.now()
        })
        self.assertEqual(1, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestNikshayFollowupPayloadGenerator(ENikshayLocationStructureMixin, NikshayRepeaterTestBase):
    def setUp(self):
        super(TestNikshayFollowupPayloadGenerator, self).setUp()

        self.cases = self.create_case_structure()
        self.test_case = self.cases['test']

        self._create_nikshay_registered_case()

        MockRepeater = namedtuple('MockRepeater', 'username password')
        MockRepeatRecord = namedtuple('MockRepeatRecord', 'repeater')
        self.repeat_record = MockRepeatRecord(MockRepeater(username="arwen", password="Hadhafang"))

    def create_case_structure(self):
        return {case.get_id: case for case in [_f for _f in self.factory.create_or_update_cases(
            [self.lab_referral, self.test, self.episode]) if _f]}

    def _create_nikshay_registered_case(self):
        update_case(self.domain, self.episode_id, {
            "nikshay_id": DUMMY_NIKSHAY_ID,
        }, external_id=DUMMY_NIKSHAY_ID,)

    @patch("socket.gethostbyname", return_value="198.1.1.1")
    def test_payload_properties(self, _):
        payload = (json.loads(
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, self.test_case))
        )
        self.assertEqual(payload['Source'], ENIKSHAY_ID)
        self.assertEqual(payload['Local_ID'], self.person_id)
        self.assertEqual(payload['RegBy'], "arwen")
        self.assertEqual(payload['password'], "Hadhafang")
        self.assertEqual(payload['IP_From'], "198.1.1.1")
        self.assertEqual(payload['TestDate'],
                         datetime.strptime(self.test_case.dynamic_case_properties().get('date_reported'),
                                           '%Y-%m-%d').strftime('%d/%m/%Y'),
                         )
        self.assertEqual(payload['LabNo'], self.test_case.dynamic_case_properties().get('lab_serial_number'))
        self.assertEqual(payload['IntervalId'], 0)
        self.assertEqual(payload['PatientWeight'], 1)
        self.assertEqual(payload["SmearResult"], 11)
        self.assertEqual(payload["DMC"], '123')
        self.assertEqual(payload["PatientID"], DUMMY_NIKSHAY_ID)

        self.set_up_to_use_2b_version()
        self.test_case = CaseAccessors(self.domain).get_case(self.test_id)
        payload = (json.loads(
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, self.test_case))
        )
        self.assertEqual(payload['IntervalId'], 0)

    def test_intervalId(self):
        update_case(self.domain, self.test_id, {
            "purpose_of_testing": "diagnostic",
            "follow_up_test_reason": "not sure"
        })
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        payload = (json.loads(
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case))
        )
        self.assertEqual(payload['IntervalId'], 0)

        update_case(self.domain, self.test_id, {
            "purpose_of_testing": "testing",
            "follow_up_test_reason": "end_of_cp"
        })
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        payload = (json.loads(
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case))
        )
        self.assertEqual(payload['IntervalId'], 4)

        self.set_up_to_use_2b_version()
        update_case(self.domain, self.test_id, {
            "rft_general": "diagnostic",
            "rft_dstb_followup": "not sure"
        })
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        payload = (json.loads(
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case))
        )
        self.assertEqual(payload['IntervalId'], 0)

        update_case(self.domain, self.test_id, {
            "rft_general": "testing",
            "rft_dstb_followup": "end_of_cp"
        })
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        payload = (json.loads(
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case))
        )
        self.assertEqual(payload['IntervalId'], 4)

    def test_result_grade(self):
        update_case(self.domain, self.test_id, {
            "purpose_of_testing": "diagnostic",
            "result_grade": "1plus"
        })
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        payload = (json.loads(
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case))
        )
        self.assertEqual(payload['SmearResult'], 11)

        update_case(self.domain, self.test_id, {
            "purpose_of_testing": "diagnostic",
            "result_grade": "scanty",
            "max_bacilli_count": '1'
        })
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        payload = (json.loads(
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case))
        )
        self.assertEqual(payload['SmearResult'], 1)

        update_case(self.domain, self.test_id, {
            "max_bacilli_count": '10'
        })
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        payload = (json.loads(
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case))
        )
        self.assertEqual(payload['SmearResult'], 9)

    def test_mandatory_field_interval_id(self):
        update_case(self.domain, self.test_id, {
            "purpose_of_testing": "testing",
            "follow_up_test_reason": "unknown_reason"
        })
        test_case = CaseAccessors(self.domain).get_case(self.test_id)

        # raises error when purpose_of_testing is not diagnostic and test reason is not known to system
        with self.assertRaisesMessage(NikshayRequiredValueMissing,
                                      "Value missing for intervalID, purpose_of_testing: {testing_purpose}, "
                                      "follow_up_test_reason: {follow_up_test_reason}".format(
                                          testing_purpose="testing",
                                          follow_up_test_reason="unknown_reason"
                                      )):
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)

        # does not raise error with purpose_of_testing being diagnostic since test reason is not relevant
        update_case(self.domain, self.test_id, {
            "purpose_of_testing": "diagnostic",
            "follow_up_test_reason": "unknown_reason"
        })
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)

        self.set_up_to_use_2b_version()
        update_case(self.domain, self.test_id, {
            "rft_general": "testing",
            "rft_dstb_followup": "unknown_reason"
        })
        test_case = CaseAccessors(self.domain).get_case(self.test_id)

        # raises error when purpose_of_testing is not diagnostic and test reason is not known to system
        with self.assertRaisesMessage(NikshayRequiredValueMissing,
                                      "Value missing for intervalID, purpose_of_testing: {testing_purpose}, "
                                      "follow_up_test_reason: {follow_up_test_reason}".format(
                                          testing_purpose="testing",
                                          follow_up_test_reason="unknown_reason"
                                      )):
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)

        # does not raise error with purpose_of_testing being diagnostic since test reason is not relevant
        update_case(self.domain, self.test_id, {
            "rft_general": "diagnostic",
            "rft_dstb_followup": "unknown_reason"
        })
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)

    def test_mandatory_field_smear_result(self):
        update_case(self.domain, self.test_id, {"result_grade": "scanty"})
        test_case = CaseAccessors(self.domain).get_case(self.test_id)

        with self.assertRaisesMessage(
                NikshayRequiredValueMissing,
                "Mandatory value missing in one of the following LabSerialNo: {lsn}, ResultGrade: {rg}, "
                "Max Bacilli Count: {max_bacilli_count}".format(
                    lsn=test_case.dynamic_case_properties().get('lab_serial_number'), rg="scanty",
                    max_bacilli_count=None
                )
        ):
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)

        update_case(self.domain, self.test_id, {"result_grade": "scanty", "max_bacilli_count": "a"})
        test_case = CaseAccessors(self.domain).get_case(self.test_id)

        with self.assertRaisesMessage(
                NikshayRequiredValueMissing,
                "Mandatory value missing in one of the following LabSerialNo: {lsn}, ResultGrade: {rg}, "
                "Max Bacilli Count: {max_bacilli_count}".format(
                    lsn=test_case.dynamic_case_properties().get('lab_serial_number'), rg="scanty",
                    max_bacilli_count="a"
                )
        ):
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)

        update_case(self.domain, self.test_id, {"result_grade": "5plus"})
        test_case = CaseAccessors(self.domain).get_case(self.test_id)

        with self.assertRaisesMessage(
                NikshayRequiredValueMissing,
                "Mandatory value missing in one of the following LabSerialNo: {lsn}, ResultGrade: {rg}, "
                "Max Bacilli Count: {max_bacilli_count}".format(
                    lsn=test_case.dynamic_case_properties().get('lab_serial_number'), rg="5plus",
                    max_bacilli_count=""
                )
        ):
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)

        update_case(self.domain, self.test_id, {"result_grade": "1plus"})
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)

        update_case(self.domain, self.test_id, {"result_grade": "scanty", "max_bacilli_count": "1"})
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)

        update_case(self.domain, self.test_id, {"result_grade": "scanty", "max_bacilli_count": "10"})
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)

    def test_mandatory_field_dmc_code(self):
        # valid
        NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, self.test_case)

        # invalid since nikshay_code needs to be a code
        self.dmc.metadata['nikshay_code'] = "BARACK-OBAMA"
        self.dmc.save()
        with self.assertRaisesMessage(
                NikshayRequiredValueMissing,
                "Inappropriate value for dmc, got value: BARACK-OBAMA"
        ):
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, self.test_case)

        self.dmc.metadata['nikshay_code'] = "123"
        self.dmc.save()
        # missing location id
        lab_referral_case = CaseAccessors(self.domain).get_case(self.lab_referral_id)
        lab_referral_case.owner_id = ''

        update_case(self.domain, self.test_id, {'testing_facility_id': ''})
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        with self.assertRaisesMessage(
                NikshayRequiredValueMissing,
                "Value missing for dmc_code/testing_facility_id for test case: {test_case_id}"
                .format(test_case_id=self.test_id)
        ):
            with patch("custom.enikshay.integrations.nikshay.repeater_generator.get_lab_referral_from_test",
                       return_value=lab_referral_case):
                NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)

        # missing location
        update_case(self.domain, self.test_id, {'testing_facility_id': '123'})
        test_case = CaseAccessors(self.domain).get_case(self.test_id)
        with self.assertRaisesMessage(
                NikshayLocationNotFound,
                "Location with id: {location_id} not found."
                "This is the testing facility id assigned for test: {test_case_id}"
                .format(location_id=123,
                        test_case_id=self.test_id)
        ):
            NikshayFollowupPayloadGenerator(None).get_payload(self.repeat_record, test_case)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestNikshayRegisterPrivatePatientRepeater(ENikshayLocationStructureMixin, NikshayRepeaterTestBase):

    def setUp(self):
        super(TestNikshayRegisterPrivatePatientRepeater, self).setUp()

        self.repeater = NikshayRegisterPrivatePatientRepeater(
            domain=self.domain,
            url=WSDL_URL,
            username='test-user'
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_not_available_for_domain(self):
        self.assertFalse(NikshayRegisterPrivatePatientRepeater.available_for_domain(self.domain))

    @flag_enabled('NIKSHAY_INTEGRATION')
    def test_available_for_domain(self):
        self.assertTrue(NikshayRegisterPrivatePatientRepeater.available_for_domain(self.domain))

    def test_trigger(self):
        # nikshay not enabled
        self.create_case(self.episode)
        self.assertEqual(0, len(self.repeat_records().all()))
        person = self.create_case(self.person)[0]
        update_case(self.domain, self.person_id, {ENROLLED_IN_PRIVATE: "true"})
        with capture_log_output('notify') as logoutput:
            self._create_nikshay_enabled_case(set_property=PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION)
        self.assertIn(NikshayLocationNotFound.__name__, logoutput.get_output())
        expected_message = (
            "Location with id {location_id} not found. "
            "This is the owner for person with id: {person_id}".format(
                location_id=person.owner_id, person_id=self.person_id)
        )
        self.assertIn(expected_message, logoutput.get_output())

        # nikshay enabled, should register a repeat record
        self.assign_person_to_location(self.pcp.location_id)
        self._create_nikshay_enabled_case(set_property=PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION)
        self.assertEqual(1, len(self.repeat_records().all()))
        #
        # set as registered, should not register a new repeat record
        self._create_nikshay_registered_case()
        self.assertEqual(1, len(self.repeat_records().all()))

    def test_trigger_different_case_type(self):
        # different case type
        self.create_case(self.person)
        self._create_nikshay_enabled_case(
            case_id=self.person_id,
            set_property=PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION
        )
        self.assertEqual(0, len(self.repeat_records().all()))

    def test_trigger_test_submission(self):
        self.pcp.metadata['is_test'] = 'yes'
        self.pcp.save()
        self.create_case(self.episode)
        self.assign_person_to_location(self.pcp.location_id)
        self._create_nikshay_enabled_case(set_property=PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION)
        self.assertEqual(0, len(self.repeat_records().all()))

    def test_trigger_non_test_submission(self):
        self.pcp.metadata['is_test'] = 'no'
        self.pcp.save()
        self.create_case(self.episode)
        self.assign_person_to_location(self.pcp.location_id)
        self._create_nikshay_enabled_case(set_property=PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION)
        self.assertEqual(1, len(self.repeat_records().all()))

    def test_handle_response(self):
        self.repeater.operation = 'InsertHFIDPatient_UATBC'
        self.repeater.save()
        self.person.attrs['update'][ENROLLED_IN_PRIVATE] = 'true'
        self.create_case(self.episode)
        self.assign_person_to_location(self.pcp.location_id)
        self._create_nikshay_enabled_case(set_property=PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION)

        record = list(self.repeat_records())[0]
        with patch.object(NikshayRegisterPrivatePatientPayloadGenerator, 'handle_success') as success:
            self.repeater.handle_response(MockSoapResponse(200, SUCCESSFUL_SOAP_RESPONSE), record)
            assert success.called

        with patch.object(NikshayRegisterPrivatePatientPayloadGenerator, 'handle_failure') as failure:
            self.repeater.handle_response(MockSoapResponse(200, FAILURE_RESPONSE), record)
            assert failure.called


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, ENIKSHAY_PRIVATE_API_PASSWORD="123",
                   ENIKSHAY_PRIVATE_API_USERS={'MH': 'ppia-mh14'})
class TestNikshayRegisterPrivatePatientPayloadGenerator(ENikshayLocationStructureMixin, NikshayRepeaterTestBase):
    def setUp(self):
        super(TestNikshayRegisterPrivatePatientPayloadGenerator, self).setUp()
        self.cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        update_case(self.domain, self.person_id, {ENROLLED_IN_PRIVATE: "true"})

    def test_payload_properties(self):
        episode_case = self._create_nikshay_enabled_case(set_property=PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION)
        payload = NikshayRegisterPrivatePatientPayloadGenerator(None).get_payload(None, episode_case)
        self.assertEqual(payload['tbdiagdate'], '09/09/2014')
        self.assertEqual(payload['HFIDNO'], '1234567')
        self.assertEqual(payload['TBUcode'], '1')
        self.assertEqual(payload['Address'], 'Mt Everest')
        self.assertEqual(payload['pin'], '110088')
        self.assertEqual(payload['fhname'], 'Mr Peregrine Kumar')
        self.assertEqual(payload['age'], '20')
        self.assertEqual(payload['Dtocode'], 'ABD')
        self.assertEqual(payload['Treat_I'], 'F')
        self.assertEqual(payload['B_diagnosis'], 'E')
        self.assertEqual(payload['lno'], '0123456789')
        self.assertEqual(payload['tbstdate'], '03/03/2015')
        self.assertEqual(payload['pname'], 'Peregrine')
        self.assertEqual(payload['D_SUSTest'], 'N')
        self.assertEqual(payload['gender'], 'Male')
        self.assertEqual(payload['Stocode'], 'MH')
        self.assertEqual(payload['Type'], 'EP')
        self.assertEqual(payload['mno'], '0')
        self.assertEqual(payload['password'], "123")
        self.assertEqual(payload['usersid'], "ppia-mh14")
        self.assertEqual(payload['Source'], ENIKSHAY_ID)

    def test_handle_success(self):
        nikshay_response_id = "000001"
        self._create_nikshay_enabled_case(set_property=PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION)
        payload_generator = NikshayRegisterPrivatePatientPayloadGenerator(None)

        repeat_record = MockNikshayRegisterPrivatePatientRepeatRecord(
            MockNikshayRegisterPrivatePatientRepeater(
                url=WSDL_URL,
                operation='InsertHFIDPatient_UATBC',
                verify=False,
            )
        )
        mock_date = date(2016, 9, 8)
        with patch('custom.enikshay.integrations.nikshay.repeater_generator.datetime') as mock_datetime:
            mock_datetime.date.today.return_value = mock_date
            payload_generator.handle_success(
                MockSoapResponse(200, SUCCESSFUL_SOAP_RESPONSE),
                self.cases[self.episode_id],
                repeat_record,
            )
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self._assert_case_property_equal(updated_episode_case, 'private_nikshay_registered', 'true')
        self._assert_case_property_equal(updated_episode_case, 'private_nikshay_error', '')
        self._assert_case_property_equal(updated_episode_case, 'date_private_nikshay_notification', str(mock_date))
        nikshay_id = '-'.join([self.pcp.metadata['nikshay_code'], nikshay_response_id])
        self._assert_case_property_equal(updated_episode_case, 'nikshay_id', nikshay_id)
        self.assertEqual(updated_episode_case.external_id, nikshay_id)

    def test_handle_failure(self):
        self._create_nikshay_enabled_case(set_property=PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION)
        payload_generator = NikshayRegisterPrivatePatientPayloadGenerator(None)

        repeat_record = MockNikshayRegisterPrivatePatientRepeatRecord(
            MockNikshayRegisterPrivatePatientRepeater(
                url=WSDL_URL,
                operation='InsertHFIDPatient_UATBC',
                verify=False,
            )
        )

        payload_generator.handle_failure(
            MockSoapResponse(200, FAILURE_RESPONSE),
            self.cases[self.episode_id],
            repeat_record,
        )
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self._assert_case_property_equal(updated_episode_case, 'private_nikshay_registered', 'false')
        self._assert_case_property_equal(updated_episode_case, 'private_nikshay_error', 'Invalid data format')
        self._assert_case_property_equal(updated_episode_case, 'nikshay_id', None)
        self.assertEqual(updated_episode_case.external_id, None)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestNikshayHealthEstablishmentRepeater(NikshayRepeaterTestBase):

    def setUp(self):
        super(TestNikshayHealthEstablishmentRepeater, self).setUp()
        self.domain = 'domain'
        self.project = Domain(name=self.domain)
        self.project.save()

        self.repeater = NikshayHealthEstablishmentRepeater(
            domain=self.domain,
            url=WSDL_URL,
            username='test-user',
            operation='HE_Registration'
        )
        self.repeater.save()

    def test_not_available_for_domain(self):
        self.assertFalse(NikshayHealthEstablishmentRepeater.available_for_domain(self.domain))

    @flag_enabled('NIKSHAY_INTEGRATION')
    def test_available_for_domain(self):
        self.assertTrue(NikshayHealthEstablishmentRepeater.available_for_domain(self.domain))

    def test_trigger(self):
        self.assertEqual(0, len(self.repeat_records().all()))
        # on create
        _, locations = setup_enikshay_locations(self.domain)
        # all locations have been created with nikshay code
        # and without sector set up as private
        # so nothing should get queued here
        self.assertEqual(0, len(self.repeat_records().all()))

        # save location user for pcp
        self.pcp = locations['PCP']
        location_user = make_location_user(self.pcp)
        location_user.user_data.update({'usertype': self.pcp.location_type.code})
        location_user.is_active = True
        location_user.user_location_id = self.pcp.location_id
        location_user.set_location(self.pcp, commit=False)
        location_user.save()

        # set up pcp location under private sector to make it valid for notification
        self.pcp.metadata.update({
            'sector': PRIVATE_HEALTH_ESTABLISHMENT_SECTOR,
        })
        self.pcp.save()
        # Nikshay code still missing so should be no records
        self.assertEqual(0, len(self.repeat_records().all()))

        # on update
        self.pcp.name = "Nikshay PCP"
        self.pcp.metadata.update({
            'email_address': 'pcp@email.com',
            # clean nikshay code to have trigger
            'nikshay_code': '',
        })
        self.pcp.save()
        self.assertTrue(self.pcp.location_id in [record.payload_id for record in RepeatRecord.all()])

        # update on test location
        delete_all_repeat_records()
        self.pcp.metadata['is_test'] = 'yes'
        self.pcp.save()
        self.assertFalse(self.pcp.location_id in [record.payload_id for record in RepeatRecord.all()])


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, ENIKSHAY_PRIVATE_API_PASSWORD="123",
                   ENIKSHAY_PRIVATE_API_USERS={'nikshay_code': 'test-mh14'})
class TestNikshayHealthEstablishmentPayloadGenerator(NikshayRepeaterTestBase):
    def setUp(self):
        super(TestNikshayHealthEstablishmentPayloadGenerator, self).setUp()
        self.domain = 'domain'
        self.project = Domain(name=self.domain)
        self.project.save()

        self.repeater = NikshayHealthEstablishmentRepeater(
            domain=self.domain,
            url=WSDL_URL,
            username='test-user',
            operation='HE_Registration'
        )
        self.repeater.save()

    def test_trigger(self):
        _, locations = setup_enikshay_locations(self.domain)
        self.assertEqual(RepeatRecord.count(), 0)

        # register a location without a location user
        self.pcp = locations['PCP']
        self.pcp.location_type.name = AGENCY_LOCATION_TYPES['plc']
        self.pcp.location_type.save()
        self.pcp.metadata.update({
            'sector': 'private',
            'nikshay_code': ''
        })
        self.pcp.save()
        self.assertEqual(RepeatRecord.count(), 0)

        location_user = make_location_user(self.pcp)
        location_user.is_active = True
        location_user.user_location_id = self.pcp.location_id
        location_user.set_location(self.pcp, commit=False)
        location_user.user_data.update({
            'usertype': self.pcp.location_type.code,
            'email': "test_user@enikshay.com",
            'landline_no': "09898989898",
            'contact_phone_number': "918888999988",
            'address_line_1': "Address line 1",
            'address_line_2': "Address line 2",
            'pincode': "110088",
            'registration_number': "14321",
            'pcp_qualification': "Doc",
        })
        location_user.first_name = "First"
        location_user.last_name = "Last"
        location_user.save()

        self.pcp.save()
        self.assertEqual(RepeatRecord.count(), 1)

        # test location
        self.pcp.metadata['is_test'] = 'yes'
        self.pcp.save()
        self.assertEqual(RepeatRecord.count(), 1)

        # not private location
        self.pcp.metadata.update({
            'is_test': 'no',
            'sector': 'public',
        })
        self.pcp.save()
        self.assertEqual(RepeatRecord.count(), 1)

        # not one of the location type to be triggered
        self.pcp.location_type.code = "random"
        self.pcp.location_type.save()
        self.pcp.metadata.update({
            'sector': PRIVATE_HEALTH_ESTABLISHMENT_SECTOR,
        })
        self.pcp.save()
        self.assertEqual(RepeatRecord.count(), 1)

        self.pcp.location_type.code = HEALTH_ESTABLISHMENT_TYPES_TO_FORWARD[0]
        self.pcp.location_type.save()
        self.pcp.metadata['nikshay_code'] = "Somecode"
        self.pcp.save()
        self.assertEqual(RepeatRecord.count(), 1)

        self.pcp.metadata['nikshay_code'] = ''
        self.pcp.save()
        self.assertEqual(RepeatRecord.count(), 2)

    def test_payload_properties(self):
        _, locations = setup_enikshay_locations(self.domain)
        self.pcp = locations['PCP']
        self.pcp.location_type.name = AGENCY_LOCATION_TYPES['plc']
        self.pcp.location_type.save()
        self.pcp.metadata.update({
            'sector': 'private'
        })
        self.pcp.save()
        location_user = make_location_user(self.pcp)
        location_user.is_active = True
        location_user.user_location_id = self.pcp.location_id
        location_user.set_location(self.pcp, commit=False)
        location_user.user_data.update({
            'usertype': self.pcp.location_type.code,
        })
        location_user.save()
        # Test dummy values
        payload = NikshayHealthEstablishmentPayloadGenerator(None).get_payload(None, self.pcp)
        self.assertEqual(payload['MCI_HR_NO'], DUMMY_VALUES['registration_number'])
        self.assertEqual(payload['CONTACT_PDESIGNATION'], NOT_AVAILABLE_VALUE)
        self.assertEqual(payload['TELEPHONE_NO'], DUMMY_VALUES['phone_number'])
        self.assertEqual(payload['MOBILE_NO'], DUMMY_VALUES['phone_number'])
        self.assertEqual(payload['PINCODE'], DUMMY_VALUES['pincode'])
        self.assertEqual(payload['EMAILID'], DUMMY_VALUES['email'])
        self.assertEqual(payload['COMPLETE_ADDRESS'], NOT_AVAILABLE_VALUE)

        location_user.user_data.update({
            'email': "test_user@enikshay.com",
            'landline_no': "9898989898",
            'contact_phone_number': "8888999988",
            'address_line_1': "Address line 1",
            'address_line_2': "Address line 2",
            'pincode': "110088",
            'registration_number': "14321",
            'pcp_qualification': "Doc",
        })
        location_user.first_name = "First"
        location_user.last_name = "Last"
        location_user.save()
        self.pcp.name = "Nikshay PCP"
        self.pcp.metadata.update({
            'nikshay_tu_id': '141'
        })
        self.pcp.save()
        payload = NikshayHealthEstablishmentPayloadGenerator(None).get_payload(None, self.pcp)
        self.assertEqual(payload['ESTABLISHMENT_TYPE'], health_establishment_type.get('Lab'))
        self.assertEqual(payload['SECTOR'], health_establishment_sector.get(self.pcp.metadata['sector'], ''))
        self.assertEqual(payload['ESTABLISHMENT_NAME'], self.pcp.name)
        self.assertEqual(payload['MCI_HR_NO'], "14321")
        self.assertEqual(payload['CONTACT_PNAME'], "First Last")
        self.assertEqual(payload['CONTACT_PDESIGNATION'], "Doc")
        self.assertEqual(payload['TELEPHONE_NO'], "9898989898")
        self.assertEqual(payload['MOBILE_NO'], "8888999988")
        self.assertEqual(payload['COMPLETE_ADDRESS'], "Address line 1 Address line 2")
        self.assertEqual(payload['PINCODE'], "110088")
        self.assertEqual(payload['EMAILID'], "test_user@enikshay.com")
        self.assertEqual(payload['STATE_CODE'], locations['STO'].metadata['nikshay_code'])
        self.assertEqual(payload['DISTRICT_CODE'], locations['DTO'].metadata['nikshay_code'])
        self.assertEqual(payload['TBU_CODE'], "141")
        self.assertEqual(payload['MUST_CREATE_NEW'], 'N')
        self.assertEqual(payload['USER_ID'], 'test-mh14')
        self.assertEqual(payload['PASSWORD'], '123')
        self.assertEqual(payload['Source'], ENIKSHAY_ID)

    def test_handle_success(self):
        _, locations = setup_enikshay_locations(self.domain)
        payload_generator = NikshayHealthEstablishmentPayloadGenerator(None)
        self.pcp = locations["PCP"]
        self.pcp.location_type.name = AGENCY_LOCATION_TYPES['plc']
        self.pcp.location_type.save()
        self.pcp.metadata.update({'sector': 'private'})
        self.pcp.save()
        location_user = make_location_user(self.pcp)
        location_user.is_active = True
        location_user.user_location_id = self.pcp.location_id
        location_user.set_location(self.pcp, commit=False)
        location_user.user_data.update({
            'usertype': self.pcp.location_type.code,
        })
        location_user.save()
        self.pcp.metadata['nikshay_code'] = ''
        # save with no nikshay code to add a repeat record
        self.pcp.save()
        repeat_record = [record for record in RepeatRecord.all() if record.payload_id == self.pcp.location_id][0]

        self.pcp.metadata['nikshay_code'] = 'old_id_value'

        payload_generator.handle_success(
            MockSoapResponse(200, SUCCESSFUL_HEALTH_ESTABLISHMENT_RESPONSE),
            self.pcp,
            repeat_record,
        )
        updated_location = SQLLocation.objects.get(location_id=self.pcp.location_id)
        self.assertEqual(updated_location.metadata['nikshay_code'], DUMMY_HEALTH_ESTABLISHMENT_ID)
        self.assertEqual(updated_location.metadata['old_nikshay_code'], 'old_id_value')

        payload_generator.handle_success(
            MockSoapResponse(200, ALREADY_REGISTERED_ESTABLISHMENT_RESPONSE),
            self.pcp,
            repeat_record
        )
        updated_location = SQLLocation.objects.get(location_id=self.pcp.location_id)
        self.assertEqual(updated_location.metadata['nikshay_code'], DUMMY_REGISTERED_HEALTH_ESTABLISHMENT_ID)
        self.assertEqual(updated_location.metadata['old_nikshay_code'], DUMMY_HEALTH_ESTABLISHMENT_ID)
