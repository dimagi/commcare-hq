import doctest
import inspect
import os
import re
from datetime import datetime

from django.test import SimpleTestCase

from dateutil.tz import tzoffset, tzutc
from lxml import etree
from mock import Mock, patch

import corehq.motech.openmrs.atom_feed
from corehq.motech.openmrs.atom_feed import (
    get_case_block_kwargs_from_bahmni_diagnoses,
    get_case_block_kwargs_from_observations,
    get_encounter_uuid,
    get_patient_uuid,
    get_timestamp,
    import_encounter,
)
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.util.test_utils import TestFileMixin


class CaseMock(dict):

    @property
    def get_id(self):
        return self.get('_id')


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


class ImportEncounterTest(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def setUp(self):
        self.case = CaseMock(
            name='Randall',
            type='patient',
            _id='abcdef',
        )
        self.repeater = OpenmrsRepeater.wrap({
            "_id": "123456",
            "domain": "test_domain",
            "username": "foo",
            "password": "bar",
            "white_listed_case_types": ['patient'],
            "openmrs_config": {
                "form_configs": [{
                    "doc_type": "OpenmrsFormConfig",
                    "xmlns": "http://openrosa.org/formdesigner/9481169B-0381-4B27-BA37-A46AB7B4692D",
                    "openmrs_visit_type": "c22a5000-3f10-11e4-adec-0800271c1b75",
                    "openmrs_encounter_type": "81852aee-3f10-11e4-adec-0800271c1b75",
                    "openmrs_observations": [
                        {
                            "doc_type": "ObservationMapping",
                            "concept": "5090AAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                            "value": {
                                "doc_type": "FormQuestion",
                                "form_question": "/data/height"
                            },
                            "case_property": "height"
                        },
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
                            "case_property": "owner_id"
                        }
                    ]
                }]
            }
        })

    def test_import_encounter(self):
        """
        Importing the given encounter should update the case's "height" property
        """
        response = Mock()
        response.json.return_value = self.get_json('encounter')
        self.repeater.requests  # Initialise cached value
        self.repeater.__dict__["requests"] = Mock()
        self.repeater.requests.get.return_value = response

        with patch('corehq.motech.openmrs.atom_feed.submit_case_blocks') as submit_case_blocks_patch, \
                patch('corehq.motech.openmrs.atom_feed.importer_util') as importer_util_patch, \
                patch('corehq.motech.openmrs.repeaters.get_one_commcare_user_at_location'):
            importer_util_patch.lookup_case.return_value = (self.case, None)

            import_encounter(self.repeater, 'c719b87f-d221-493b-bec7-c212aa813f5d')

            case_block_re = """
                <case case_id="abcdef" »
                      date_modified="[\\d\\-T\\:\\.Z]+" »
                      xmlns="http://commcarehq.org/case/transaction/v2">
                  <update>
                    <height>105</height>
                  </update>
                </case>"""
            case_block_re = ''.join((l.strip() for l in case_block_re.split('\n'))).replace('»', '')
            ([case_block], domain), kwargs = submit_case_blocks_patch.call_args
            self.assertRegex(case_block, case_block_re)
            self.assertEqual(domain, 'test_domain')
            self.assertEqual(kwargs['device_id'], 'openmrs-atomfeed-123456')
            self.assertEqual(kwargs['xmlns'], 'http://commcarehq.org/openmrs-integration')

    def test_get_case_block_kwargs_from_observations(self):
        encounter = self.get_json('encounter')
        observations = encounter['observations']
        case_block_kwargs, case_blocks = get_case_block_kwargs_from_observations(
            observations,
            self.repeater.observation_mappings,
            None, None, None
        )
        self.assertEqual(case_block_kwargs, {'update': {'height': 105}})
        self.assertEqual(case_blocks, [])

    def test_get_case_block_kwargs_from_bahmni_diagnoses(self):
        encounter = self.get_json('encounter_with_diagnoses')
        bahmni_diagnoses = encounter['bahmniDiagnoses']
        case_block_kwargs, case_blocks = get_case_block_kwargs_from_bahmni_diagnoses(
            bahmni_diagnoses,
            self.repeater.observation_mappings,
            None, None, None
        )
        self.assertEqual(case_block_kwargs, {'owner_id': 'emergency_room_user_id', 'update': {}})
        self.assertEqual(case_blocks, [])


def test_doctests():
    results = doctest.testmod(corehq.motech.openmrs.atom_feed)
    assert results.failed == 0
