from datetime import datetime
from django.test import SimpleTestCase, TestCase
from django.utils.dateparse import parse_datetime

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.form_processor.tests.utils import run_with_all_backends, FormProcessorTestUtils

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.integrations.ninetyninedots.views import (
    validate_adherence_values,
    validate_beneficiary_id
)
from custom.enikshay.integrations.ninetyninedots.utils import (
    create_adherence_cases,
    get_open_episode_case,
    get_adherence_cases_between_dates,
)
from custom.enikshay.integrations.ninetyninedots.exceptions import AdherenceException


class Receiver99DotsTests(SimpleTestCase):
    def test_validate_patient_adherence_data(self):
        with self.assertRaises(AdherenceException) as e:
            validate_beneficiary_id(None)
            self.assertEqual(e.message, "Beneficiary ID is null")

        with self.assertRaises(AdherenceException) as e:
            validate_adherence_values(u'123')
            self.assertEqual(e.message, "Adherences invalid")


class NinetyNineDotsCaseTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super(NinetyNineDotsCaseTests, cls).setUpClass()
        FormProcessorTestUtils.delete_all_cases()
        cls.domain = 'enikshay-test'
        cls.factory = CaseFactory(domain=cls.domain)
        cls.person_id = "person"
        cls.occurrence_id = "occurrence"
        cls.episode_id = "episode"

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()

    def _create_case_structure(self):
        person = CaseStructure(
            case_id=self.person_id,
            attrs={
                "case_type": "person",
                "create": True,
                "update": dict(
                    default_adherence_confidence="high"
                )
            },
        )
        occurrence = CaseStructure(
            case_id=self.occurrence_id,
            attrs={
                'create': True,
                'case_type': 'occurrence',
                "update": dict(
                    person_id=self.person_id
                )
            },
            indices=[CaseIndex(
                person,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=person.attrs['case_type'],
            )],
        )
        episode = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'create': True,
                'case_type': 'episode',
                "update": dict(
                    person_name="Ramsey Bolton",
                    person_id=self.person_id,
                    opened_on=datetime(1989, 6, 11, 0, 0),
                    patient_type="new",
                    hiv_status="reactive",
                    episode_type="confirmed_tb",
                )
            },
            indices=[CaseIndex(
                occurrence,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=occurrence.attrs['case_type'],
            )],
        )
        self.factory.create_or_update_cases([episode])

    @run_with_all_backends
    def test_get_episode(self):
        self._create_case_structure()
        self.assertEqual(get_open_episode_case(self.domain, 'person').case_id, 'episode')

    @run_with_all_backends
    def test_create_adherence_cases(self):
        self._create_case_structure()
        case_accessor = CaseAccessors(self.domain)
        adherence_values = [
            {
                "timestamp": "2009-03-05T01:00:01-05:00",
                "numberFromWhichPatientDialled": "+910123456789",
                "sharedNumber": False,
            },
            {
                "timestamp": "2016-03-05T02:00:01-05:00",
                "numberFromWhichPatientDialled": "+910123456787",
                "sharedNumber": True,
            }
        ]
        create_adherence_cases(self.domain, 'person', adherence_values, adherence_source="99DOTS")
        potential_adherence_cases = case_accessor.get_reverse_indexed_cases(['episode'])
        adherence_cases = [case for case in potential_adherence_cases if case.type == 'adherence']
        self.assertEqual(len(adherence_cases), 2)
        adherence_times = [case.dynamic_case_properties().get('adherence_date')
                           for case in adherence_cases]

        self.assertItemsEqual(
            [parse_datetime(adherence_time) for adherence_time in adherence_times],
            [parse_datetime(adherence_value['timestamp']) for adherence_value in adherence_values]
        )

        for adherence_case in adherence_cases:
            self.assertEqual(
                adherence_case.dynamic_case_properties().get('adherence_confidence'),
                'high'
             )
