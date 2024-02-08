import doctest
import inspect
import os
import re
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

import attr
from dateutil.tz import tzoffset, tzutc
from lxml import etree
from nose.tools import assert_equal, assert_is_none, assert_raises
from corehq.motech.models import ConnectionSettings

import corehq.motech.openmrs.atom_feed
from corehq.motech.openmrs.atom_feed import (
    get_case_block_kwargs_from_bahmni_diagnoses,
    get_case_block_kwargs_from_observations,
    get_diagnosis_mappings,
    get_encounter_uuid,
    get_feed_updates,
    get_feed_xml,
    get_observation_mappings,
    get_patient_uuid,
    get_timestamp,
    import_encounter,
)
from corehq.motech.openmrs.const import ATOM_FEED_NAME_PATIENT
from corehq.motech.openmrs.exceptions import (
    OpenmrsException,
    OpenmrsFeedRuntimeException,
    OpenmrsFeedSyntaxError,
)
from corehq.motech.openmrs.repeaters import AtomFeedStatus, OpenmrsRepeater
from corehq.motech.openmrs.tasks import poll_openmrs_atom_feeds
from ...repeaters.tests.data.repeaters import ENCOUNTER_FEED_XML, PATIENT_FEED_XML
from corehq.motech.requests import Requests
from corehq.util.test_utils import TestFileMixin


@attr.s
class CaseMock:
    case_id = attr.ib()
    name = attr.ib()
    type = attr.ib()
    owner_id = attr.ib()


class GetTimestampTests(SimpleTestCase):

    def setUp(self):
        self.feed_xml = inspect.cleandoc("""<?xml version="1.0" encoding="UTF-8"?>
            <feed xmlns="http://www.w3.org/2005/Atom">
              <title>Patient AOP</title>
              <updated>2018-05-15T14:02:08Z</updated>
              <entry>
                <title>Patient</title>
                <updated>2018-04-26T10:56:10Z</updated>
              </entry>
            </feed>""")

    def test_no_node(self):
        xml = re.sub(r'<updated.*</updated>', '', self.feed_xml)
        feed_elem = etree.XML(xml.encode('utf-8'))
        with self.assertRaisesRegex(ValueError, r'^XPath "./atom:updated" not found$'):
            get_timestamp(feed_elem)

    def test_xpath(self):
        feed_elem = etree.XML(self.feed_xml.encode('utf-8'))
        # "*[local-name()='foo']" ignores namespaces and matches all nodes with tag "foo":
        timestamp = get_timestamp(feed_elem, "./*[local-name()='entry']/*[local-name()='updated']")
        self.assertEqual(timestamp, datetime(2018, 4, 26, 10, 56, 10, tzinfo=tzutc()))

    def test_bad_date(self):
        xml = re.sub(r'2018-05-15T14:02:08Z', 'Nevermore', self.feed_xml)
        feed_elem = etree.XML(xml.encode('utf-8'))
        with self.assertRaisesRegex(ValueError, r'Unknown string format'):
            get_timestamp(feed_elem)

    def test_timezone(self):
        xml = re.sub(r'2018-05-15T14:02:08Z', '2018-05-15T14:02:08+0500', self.feed_xml)
        feed_elem = etree.XML(xml.encode('utf-8'))
        timestamp = get_timestamp(feed_elem)
        self.assertEqual(timestamp, datetime(2018, 5, 15, 14, 2, 8, tzinfo=tzoffset(None, 5 * 60 * 60)))


class GetPatientUuidTests(SimpleTestCase):

    def setUp(self):
        self.feed_xml = inspect.cleandoc("""<?xml version="1.0" encoding="UTF-8"?>
            <feed xmlns="http://www.w3.org/2005/Atom">
              <title>Patient AOP</title>
              <entry>
                <title>Patient</title>
                <content type="application/vnd.atomfeed+xml">
                  <![CDATA[/openmrs/ws/rest/v1/patient/e8aa08f6-86cd-42f9-8924-1b3ea021aeb4?v=full]]>
                </content>
              </entry>
            </feed>""")

    def test_no_content_node(self):
        xml = re.sub(r'<content.*</content>', '', self.feed_xml, flags=re.DOTALL)
        feed_elem = etree.XML(xml.encode('utf-8'))
        entry_elem = next(e for e in feed_elem if e.tag.endswith('entry'))
        with self.assertRaisesRegex(ValueError, r'^Patient UUID not found$'):
            get_patient_uuid(entry_elem)

    def test_bad_cdata(self):
        xml = re.sub(r'e8aa08f6-86cd-42f9-8924-1b3ea021aeb4', 'mary-mallon', self.feed_xml)
        feed_elem = etree.XML(xml.encode('utf-8'))
        entry_elem = next(e for e in feed_elem if e.tag.endswith('entry'))
        with self.assertRaisesRegex(ValueError, r'^Patient UUID not found$'):
            get_patient_uuid(entry_elem)

    def test_success(self):
        feed_elem = etree.XML(self.feed_xml.encode('utf-8'))
        entry_elem = next(e for e in feed_elem if e.tag.endswith('entry'))
        patient_uuid = get_patient_uuid(entry_elem)
        self.assertEqual(patient_uuid, 'e8aa08f6-86cd-42f9-8924-1b3ea021aeb4')


class GetEncounterUuidTests(SimpleTestCase):

    def test_bed_assignment(self):
        element = etree.XML("""<entry>
          <title>Bed-Assignment</title>
          <content type="application/vnd.atomfeed+xml">
            <![CDATA[/openmrs/ws/rest/v1/bedPatientAssignment/fed0d6f9-e76c-4a8e-a10d-c8e98c7d258f?v=custom:(uuid,startDatetime,endDatetime,bed,patient,encounter:(uuid,encounterDatetime,encounterType:(uuid,name),visit:(uuid,startDatetime,visitType)))]]>
          </content>
        </entry>""")
        encounter_uuid = get_encounter_uuid(element)
        self.assertIsNone(encounter_uuid)

    def test_unknown_entry(self):
        element = etree.XML("""<entry>
          <title>UnExPeCtEd</title>
          <content type="application/vnd.atomfeed+xml">
            <![CDATA[/openmrs/ws/rest/v1/UNKNOWN/0f54fe40-89af-4412-8dd4-5eaebe8684dc]]>
          </content>
        </entry>""")
        with self.assertRaises(ValueError):
            get_encounter_uuid(element)


class ImportEncounterTest(TestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def setUp(self):
        self.case = CaseMock(
            case_id='abcdef',
            name='Randall',
            type='patient',
            owner_id='123456'
        )
        self.connx = ConnectionSettings.objects.create(url='abcd', domain='test_domain')

    def tearDown(self):
        self.connx.delete()

    def setUpRepeater(self):
        observations = [
            {
                "doc_type": "ObservationMapping",
                "concept": "5090AAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "value": {
                    "doc_type": "FormQuestion",
                    "form_question": "/data/height"
                },
                "case_property": "height"
            }
        ]
        diagnoses = [
            {
                "doc_type": "ObservationMapping",
                "concept": "f7e8da66-f9a7-4463-a8ca-99d8aeec17a0",
                "value": {
                    "doc_type": "FormQuestionMap",
                    "direction": "in",
                    "form_question": "[unused when direction == 'in']",
                    "value_map": {
                        "emergency_room_user_id": "Hypothermia",  # Value must match diagnosis name
                    }
                },
                "case_property": "owner_id"
            },
            {
                "doc_type": "ObservationMapping",
                "concept": "f7e8da66-f9a7-4463-a8ca-99d8aeec17a0",
                "value": {
                    "doc_type": "JsonPathCasePropertyMap",
                    "direction": "in",
                    "jsonpath": "codedAnswer.name",
                    "case_property": "[unused when direction == 'in']",
                    "value_map": {
                        "yes": "Hypothermia"
                    }
                },
                "case_property": "hypothermia_diagnosis"
            },
            {
                "doc_type": "ObservationMapping",
                "concept": "f7e8da66-f9a7-4463-a8ca-99d8aeec17a0",
                "value": {
                    "doc_type": "JsonPathCaseProperty",
                    "direction": "in",
                    "jsonpath": "diagnosisDateTime",
                    "case_property": "[unused when direction == 'in']",
                    "commcare_data_type": "cc_date",
                    "external_data_type": "omrs_datetime"
                },
                "case_property": "hypothermia_date"
            }
        ]
        self.repeater = OpenmrsRepeater(**self.get_repeater_dict(observations, diagnoses))

    def setUpRepeaterForExtCase(self):
        observations = [
            {
                "doc_type": "ObservationMapping",
                "concept": "5090AAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "value": {
                    "doc_type": "FormQuestion",
                    "form_question": "/data/height"
                },
                "indexed_case_mapping": {
                    "identifier": "parent",
                    "case_type": "observation",
                    "relationship": "extension",
                    "case_properties": [
                        {
                            "doc_type": "JsonPathCaseProperty",
                            "jsonpath": "concept.name",
                            "case_property": "case_name",
                        },
                        {
                            "doc_type": "JsonPathCaseProperty",
                            "jsonpath": "value",
                            "case_property": "observation_value",
                        }
                    ]
                }
            }
        ]
        diagnoses = [
            {
                "doc_type": "ObservationMapping",
                "concept": "f7e8da66-f9a7-4463-a8ca-99d8aeec17a0",
                "value": {
                    "doc_type": "FormQuestionMap",
                    "form_question": "/data/bahmni_hypothermia",
                    "value_map": {
                        "emergency_room_user_id": "Hypothermia",  # Value must match diagnosis name
                    },
                    "direction": "in",
                },
            },
            {
                "doc_type": "ObservationMapping",
                "concept": "all",  # Import all diagnoses as extension cases
                "value": {
                    "direction": "in",
                    "value": "[unused when direction='in' and ObservationMapping.case_property not set]",
                },
                "indexed_case_mapping": {
                    "identifier": "parent",
                    "case_type": "diagnosis",
                    "relationship": "extension",
                    "case_properties": [
                        {
                            "jsonpath": "codedAnswer.name",
                            "case_property": "case_name",
                        },
                        {
                            "jsonpath": "certainty",
                            "case_property": "certainty",
                        },
                        {
                            "jsonpath": "order",
                            "case_property": "is_primary",
                            "value_map": {
                                "yes": "PRIMARY",
                                "no": "SECONDARY"
                            }
                        },
                        {
                            "jsonpath": "diagnosisDateTime",
                            "case_property": "diagnosis_date",
                            "external_data_type": "omrs_datetime",
                            "commcare_data_type": "cc_date",
                        }
                    ]
                }
            }
        ]
        self.repeater = OpenmrsRepeater(**self.get_repeater_dict(observations, diagnoses))

    def get_repeater_dict(self, observations, diagnoses):
        return {
            "domain": "test_domain",
            "connection_settings": self.connx,
            "white_listed_case_types": ['patient'],
            "openmrs_config": {
                "form_configs": [{
                    "doc_type": "OpenmrsFormConfig",
                    "xmlns": "http://openrosa.org/formdesigner/9481169B-0381-4B27-BA37-A46AB7B4692D",
                    "openmrs_visit_type": "c22a5000-3f10-11e4-adec-0800271c1b75",
                    "openmrs_encounter_type": "81852aee-3f10-11e4-adec-0800271c1b75",
                    "openmrs_start_datetime": {
                        "direction": "in",
                        "case_property": "last_visit_date",
                        "external_data_type": "omrs_datetime",
                        "commcare_data_type": "cc_date",
                        # "jsonpath": "encounterDateTime",  # get_encounter_datetime_value_sources() default value
                    },
                    "openmrs_observations": observations,
                    "bahmni_diagnoses": diagnoses
                }]
            }
        }

    def test_import_encounter(self):
        """
        Importing the given encounter should update the case's "height" property
        """
        response = Mock()
        response.json.return_value = self.get_json('encounter')
        self.setUpRepeater()

        with patch.object(Requests, 'get') as get_patch, \
                patch('corehq.motech.openmrs.atom_feed.submit_case_blocks') as submit_case_blocks_patch, \
                patch('corehq.motech.openmrs.atom_feed.importer_util') as importer_util_patch, \
                patch('corehq.motech.openmrs.repeaters.get_one_commcare_user_at_location'):
            get_patch.return_value = response
            importer_util_patch.lookup_case.return_value = (self.case, None)

            import_encounter(self.repeater, 'c719b87f-d221-493b-bec7-c212aa813f5d')

            case_block_re = """
                <case case_id="abcdef" »
                      date_modified="[\\d\\-T\\:\\.Z]+" »
                      xmlns="http://commcarehq.org/case/transaction/v2">
                  <update>
                    <height>105</height>
                    <last_visit_date>2018-01-18</last_visit_date>
                  </update>
                </case>"""
            case_block_re = ''.join((x.strip() for x in case_block_re.split('\n'))).replace('»', '')
            ([case_block], domain), kwargs = submit_case_blocks_patch.call_args
            self.assertRegex(case_block, case_block_re)
            self.assertEqual(domain, 'test_domain')
            self.assertEqual(kwargs['device_id'], f'openmrs-atomfeed-{self.repeater.id.hex}')
            self.assertEqual(kwargs['xmlns'], 'http://commcarehq.org/openmrs-integration')

    def test_get_case_block_kwargs_from_observations(self):
        self.setUpRepeater()
        encounter = self.get_json('encounter')
        observations = encounter['observations']
        case_block_kwargs, case_blocks = get_case_block_kwargs_from_observations(
            observations,
            get_observation_mappings(self.repeater),
            (None, None, None)
        )
        self.assertEqual(case_block_kwargs, {'update': {'height': 105}})
        self.assertEqual(case_blocks, [])

    def test_get_case_block_kwargs_from_bahmni_diagnoses(self):
        self.setUpRepeater()
        encounter = self.get_json('encounter_with_diagnoses')
        bahmni_diagnoses = encounter['bahmniDiagnoses']
        case_block_kwargs, case_blocks = get_case_block_kwargs_from_bahmni_diagnoses(
            bahmni_diagnoses,
            get_diagnosis_mappings(self.repeater),
            (None, None, None)
        )
        self.assertEqual(case_block_kwargs, {
            'owner_id': 'emergency_room_user_id',
            'update': {
                'hypothermia_diagnosis': 'yes',
                'hypothermia_date': '2019-10-18'
            }
        })
        self.assertEqual(case_blocks, [])

    def test_get_case_blocks_from_observations(self):
        self.setUpRepeaterForExtCase()
        encounter = self.get_json('encounter')
        observations = encounter['observations']
        case_block_kwargs, case_blocks = get_case_block_kwargs_from_observations(
            observations,
            get_observation_mappings(self.repeater),
            ('test-case-id', 'patient', 'default-owner-id')
        )
        self.assertEqual(case_block_kwargs, {'update': {}})
        self.assertEqual(len(case_blocks), 1)
        date_modified = case_blocks[0].date_modified.isoformat() + 'Z'
        case_block = f"""
            <case case_id="{case_blocks[0].case_id}" »
                  date_modified="{date_modified}" »
                  xmlns="http://commcarehq.org/case/transaction/v2">
              <create>
                <case_type>observation</case_type>
                <case_name>HEIGHT</case_name>
                <owner_id>default-owner-id</owner_id>
              </create>
              <update>
                <observation_value>105</observation_value>
              </update>
              <index>
                <parent case_type="patient" relationship="extension">test-case-id</parent>
              </index>
            </case>"""
        case_block = ''.join((x.strip() for x in case_block.split('\n'))).replace('»', '')
        self.assertEqual(case_blocks[0].as_text(), case_block)

    def test_get_case_blocks_from_bahmni_diagnoses(self):
        self.setUpRepeaterForExtCase()
        encounter = self.get_json('encounter_with_diagnoses')
        bahmni_diagnoses = encounter['bahmniDiagnoses']
        case_block_kwargs, case_blocks = get_case_block_kwargs_from_bahmni_diagnoses(
            bahmni_diagnoses,
            get_diagnosis_mappings(self.repeater),
            ('test-case-id', 'patient', 'default-owner-id')
        )
        self.assertEqual(case_block_kwargs, {'update': {}})
        self.assertEqual(len(case_blocks), 1)
        date_modified = case_blocks[0].date_modified.isoformat() + 'Z'
        case_block = f"""
            <case case_id="{case_blocks[0].case_id}" »
                  date_modified="{date_modified}" »
                  xmlns="http://commcarehq.org/case/transaction/v2">
              <create>
                <case_type>diagnosis</case_type>
                <case_name>Hypothermia</case_name>
                <owner_id>default-owner-id</owner_id>
              </create>
              <update>
                <certainty>CONFIRMED</certainty>
                <diagnosis_date>2019-10-18</diagnosis_date>
                <is_primary>yes</is_primary>
              </update>
              <index>
                <parent case_type="patient" relationship="extension">test-case-id</parent>
              </index>
            </case>"""
        case_block = ''.join((x.strip() for x in case_block.split('\n'))).replace('»', '')
        self.assertEqual(case_blocks[0].as_text(), case_block)


def test_get_feed_xml_feed_does_not_exist():
    page = '1000'
    response_url = f'https://example.com/openmrs/ws/atomfeed/patient/{page}'
    response = SimpleNamespace(
        status_code=500,
        url=response_url,
        text=(
            '<!DOCTYPE html>\n'
            '<html><body><h1>HTTP Status 500 - Request processing failed; '
            'nested exception is org.ict4h.atomfeed.server.exceptions'
            '.AtomFeedRuntimeException: feed does not exist</h1></html>'
        ),
    )
    requests = Mock(
        domain_name='test_domain',
        get=lambda url: response,
    )
    with assert_raises(OpenmrsFeedRuntimeException):
        get_feed_xml(requests, ATOM_FEED_NAME_PATIENT, page)
    requests.notify_exception.assert_called_with(
        'Domain "test_domain": Page does not exist in Atom feed '
        f'"{response_url}". Resetting Atom feed status.',
        'This can happen if the IP address of a Repeater is changed to point '
        'to a different server, or if a server has been rebuilt. It can '
        'signal more severe consequences, like attempts to synchronize '
        'CommCare cases with OpenMRS patients that can no longer be found.'
    )


def test_get_feed_xml_feedid_zero():
    page = '0'
    response_url = f'https://example.com/openmrs/ws/atomfeed/patient/{page}'
    response = SimpleNamespace(
        status_code=500,
        url=response_url,
        text=(
            '<!DOCTYPE html>\n'
            '<html><body><h1>HTTP Status 500 - Request processing failed; '
            'nested exception is org.ict4h.atomfeed.server.exceptions'
            '.AtomFeedRuntimeException: feedId must not be null and must be '
            'greater than 0</h1></html>'
        ),
    )
    requests = Mock(
        domain_name='test_domain',
        get=lambda url: response,
    )
    with assert_raises(OpenmrsFeedRuntimeException):
        get_feed_xml(requests, ATOM_FEED_NAME_PATIENT, '0')
    requests.notify_exception.assert_called_with(
        f'Domain "test_domain": Page "{page}" is not valid in Atom feed '
        f'"{response_url}". Resetting Atom feed status.',
        f'It is unclear how Atom feed pagination can lead to page "{page}". '
        'Follow up with OpenMRS system administrator.'
    )


def test_get_feed_xml_500():
    page = 'recent'
    response_url = f'https://example.com/openmrs/ws/atomfeed/patient/{page}'
    response = SimpleNamespace(
        status_code=500,
        url=response_url,
        text='<!DOCTYPE html>\n'
             '<html><body>HTTP Status 500</body></html>',
    )
    requests = Mock(
        domain_name='test_domain',
        get=lambda url: response,
    )
    with assert_raises(OpenmrsException):
        get_feed_xml(requests, ATOM_FEED_NAME_PATIENT, page)
    requests.notify_exception.assert_called_with(
        'Domain "test_domain": Unrecognized error in Atom feed '
        f'"{response_url}".',
        'Response text: \n'
        '<!DOCTYPE html>\n<html><body>HTTP Status 500</body></html>'
    )


def test_get_feed_xml_bad_xml():
    page = 'recent'
    response_url = f'https://example.com/openmrs/ws/atomfeed/patient/{page}'
    response = SimpleNamespace(
        status_code=200,
        url=response_url,
        content='<html><body>Bad XML</html>',
    )
    requests = Mock(
        domain_name='test_domain',
        get=lambda url: response,
    )
    with assert_raises(OpenmrsFeedSyntaxError):
        get_feed_xml(requests, ATOM_FEED_NAME_PATIENT, page)
    requests.notify_exception.assert_called_with(
        'Opening and ending tag mismatch: body line 1 and html, line 1, '
        'column 27 (<string>, line 1)',
        'There is an XML syntax error in the OpenMRS Atom feed at '
        f'"{response_url}".'
    )


def test_get_feed_updates():
    response = SimpleNamespace(
        status_code=200,
        url='https://www.example.com/openmrs/ws/atomfeed/patient/recent',
        content='<html><body>Bad XML</html>',
    )
    requests = SimpleNamespace(
        domain_name='test_domain',
        get=lambda url: response,
        notify_exception=lambda err, msg: None,
    )
    repeater = SimpleNamespace(
        atom_feed_status={},
        requests=requests,
    )
    with patch('corehq.motech.openmrs.atom_feed.get_feed_xml') \
            as get_feed_xml_mock:
        get_feed_xml_mock.side_effect = OpenmrsFeedSyntaxError

        # Assert returns without raising
        get_feed_updates(repeater, ATOM_FEED_NAME_PATIENT)


def test_status_defaults():
    status = AtomFeedStatus()
    assert_is_none(status.last_polled_at)
    assert_equal(status.last_page, 'recent')


def test_doctests():
    results = doctest.testmod(corehq.motech.openmrs.atom_feed)
    assert results.failed == 0


class TestPollOpenmrsAtomFeeds(TestCase, TestFileMixin):

    file_path = ('data',)
    root = os.path.dirname(__file__)

    def setUp(self):
        from corehq.motech.repeaters.tests.data.repeaters import openmrs_repeater
        super().setUp()
        self.conn = ConnectionSettings.objects.create(
            id=1,
            url="http://abc.com",
            name="http://abc.com",
            domain=openmrs_repeater["domain"],
        )
        self.repeater = OpenmrsRepeater(**openmrs_repeater).save()

        self.encounter_feed_xml = inspect.cleandoc(ENCOUNTER_FEED_XML)
        self.encounter_feed_elem = etree.XML(self.encounter_feed_xml.encode('utf-8'))

        self.patient_feed_xml = inspect.cleandoc(PATIENT_FEED_XML)
        self.patient_feed_elem = etree.XML(self.patient_feed_xml.encode('utf-8'))

    @patch('corehq.motech.openmrs.atom_feed.get_feed_xml')
    @patch('corehq.motech.openmrs.atom_feed.get_patient_by_uuid')
    @patch('corehq.motech.openmrs.atom_feed.get_encounter')
    def test_poll_openmrs_atom_feeds(self, get_encounter, get_patient, get_feed_xml):
        get_feed_xml.side_effect = [self.patient_feed_elem, self.encounter_feed_elem]
        get_encounter.return_value = self.get_json('encounter')
        poll_openmrs_atom_feeds('test_openmrs')
