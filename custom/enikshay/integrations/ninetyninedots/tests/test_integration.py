from datetime import datetime
import pytz
from django.test import SimpleTestCase, TestCase
from django.utils.dateparse import parse_datetime

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseStructure, CaseIndex
from corehq.form_processor.tests.utils import run_with_all_backends, FormProcessorTestUtils

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.integrations.ninetyninedots.views import (
    validate_adherence_values,
    validate_beneficiary_id
)
from custom.enikshay.case_utils import (
    get_open_episode_case_from_person,
    get_adherence_cases_between_dates,
)
from custom.enikshay.integrations.ninetyninedots.utils import (
    create_adherence_cases,
    update_adherence_confidence_level,
    update_default_confidence_level,
)
from custom.enikshay.integrations.ninetyninedots.exceptions import AdherenceException
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin


class Receiver99DotsTests(SimpleTestCase):
    def test_validate_patient_adherence_data(self):
        with self.assertRaises(AdherenceException) as e:
            validate_beneficiary_id(None)
            self.assertEqual(e.message, "Beneficiary ID is null")

        with self.assertRaises(AdherenceException) as e:
            validate_adherence_values(u'123')
            self.assertEqual(e.message, "Adherences invalid")


class NinetyNineDotsCaseTests(ENikshayCaseStructureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(NinetyNineDotsCaseTests, cls).setUpClass()
        FormProcessorTestUtils.delete_all_cases()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()

    def _create_adherence_cases(self, adherence_dates):
        return self.factory.create_or_update_cases([
            CaseStructure(
                case_id=adherence_date.strftime('%Y-%m-%d'),
                attrs={
                    "case_type": "adherence",
                    "create": True,
                    "update": {
                        "name": adherence_date,
                        "adherence_value": "unobserved_dose",
                        "adherence_source": "99DOTS",
                        "adherence_date": adherence_date,
                        "person_name": "Pippin",
                        "adherence_confidence": "medium",
                        "shared_number_99_dots": False,
                    },
                },
                indices=[CaseIndex(
                    CaseStructure(case_id=self.episode_id, attrs={"create": False}),
                    identifier='host',
                    relationship=CASE_INDEX_EXTENSION,
                    related_type='episode',
                )],
                walk_related=False,
            )
            for adherence_date in adherence_dates
        ])

    @run_with_all_backends
    def test_get_episode(self):
        self.create_case_structure()
        self.assertEqual(get_open_episode_case_from_person(self.domain, 'person').case_id, 'episode')

    @run_with_all_backends
    def test_create_adherence_cases(self):
        self.create_case_structure()
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

    @run_with_all_backends
    def test_get_adherence_cases_between_dates(self):
        self.create_case_structure()
        adherence_dates = [
            datetime(2005, 7, 10),
            datetime(2016, 8, 10),
            datetime(2016, 8, 11),
            datetime(2016, 8, 12),
            datetime(2017, 9, 10),
        ]
        self._create_adherence_cases(adherence_dates)
        fetched_cases = get_adherence_cases_between_dates(
            self.domain,
            self.person_id,
            start_date=datetime(2016, 7, 1, tzinfo=pytz.UTC),
            end_date=datetime(2016, 8, 13, tzinfo=pytz.UTC),
        )
        self.assertEqual(len(fetched_cases), 3)
        self.assertItemsEqual(
            ["2016-08-10", "2016-08-11", "2016-08-12"],
            [case.case_id for case in fetched_cases]
        )

        fetched_cases = get_adherence_cases_between_dates(
            self.domain,
            self.person_id,
            start_date=datetime(2010, 7, 1, tzinfo=pytz.UTC),
            end_date=datetime(2010, 8, 13, tzinfo=pytz.UTC),
        )
        self.assertEqual(len(fetched_cases), 0)

        fetched_cases = get_adherence_cases_between_dates(
            self.domain,
            self.person_id,
            start_date=datetime(2016, 8, 10, tzinfo=pytz.UTC),
            end_date=datetime(2016, 8, 10, tzinfo=pytz.UTC),
        )
        self.assertEqual(len(fetched_cases), 1)
        self.assertEqual(
            "2016-08-10",
            fetched_cases[0].case_id,
        )

    @run_with_all_backends
    def test_update_adherence_confidence(self):
        self.create_case_structure()
        case_accessor = CaseAccessors(self.domain)
        adherence_dates = [
            datetime(2005, 7, 10),
            datetime(2016, 8, 10),
            datetime(2016, 8, 11),
        ]
        adherence_cases = self._create_adherence_cases(adherence_dates)

        update_adherence_confidence_level(
            self.domain,
            self.person_id,
            datetime(2016, 8, 10, tzinfo=pytz.UTC),
            datetime(2016, 8, 11, tzinfo=pytz.UTC),
            "new_confidence_level",
        )
        adherence_case_ids = [adherence_date.strftime("%Y-%m-%d") for adherence_date in adherence_dates]
        adherence_cases = {case.case_id: case for case in case_accessor.get_cases(adherence_case_ids)}

        self.assertEqual(
            adherence_cases[adherence_case_ids[0]].dynamic_case_properties()['adherence_confidence'],
            'medium',
        )
        self.assertEqual(
            adherence_cases[adherence_case_ids[1]].dynamic_case_properties()['adherence_confidence'],
            'new_confidence_level',
        )
        self.assertEqual(
            adherence_cases[adherence_case_ids[2]].dynamic_case_properties()['adherence_confidence'],
            'new_confidence_level',
        )

    @run_with_all_backends
    def test_update_default_confidence_level(self):
        self.create_case_structure()
        confidence_level = "new_confidence_level"
        update_default_confidence_level(self.domain, self.person_id, confidence_level)
        episode = get_open_episode_case_from_person(self.domain, self.person_id)
        self.assertEqual(episode.dynamic_case_properties().get('default_adherence_confidence'), confidence_level)
