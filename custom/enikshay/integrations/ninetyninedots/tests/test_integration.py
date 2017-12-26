from __future__ import absolute_import
import mock
from datetime import datetime
import pytz
from django.test import SimpleTestCase, TestCase, override_settings


from corehq.form_processor.tests.utils import FormProcessorTestUtils

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.integrations.ninetyninedots.views import (
    validate_adherence_values,
    validate_beneficiary_id,
    update_ledger_for_episode,
)
from custom.enikshay.case_utils import get_open_episode_case_from_person
from custom.enikshay.integrations.ninetyninedots.utils import (
    create_adherence_cases,
    update_adherence_confidence_level,
    update_default_confidence_level,
)
from custom.enikshay.integrations.ninetyninedots.exceptions import AdherenceException
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin
from custom.enikshay.ledger_utils import get_episode_adherence_ledger

MOCK_FIXTURE_ITEMS = {
    '99DOTS': {
        'directly_observed_dose': '13',
        'manual': '18',
        'missed_dose': '15',
        'missing_data': '16',
        'self_administered_dose': '17',
        'unobserved_dose': '14'},
    'enikshay': {
        'directly_observed_dose': '1',
        'manual': '6',
        'missed_dose': '3',
        'missing_data': '4',
        'self_administered_dose': '5',
        'unobserved_dose': '2'},
}


class Receiver99DotsTests(SimpleTestCase):
    def test_validate_patient_adherence_data(self):
        with self.assertRaises(AdherenceException) as e:
            validate_beneficiary_id(None)
            self.assertEqual(e.message, "Beneficiary ID is null")

        with self.assertRaises(AdherenceException) as e:
            validate_adherence_values(u'123')
            self.assertEqual(e.message, "Adherences invalid")


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class NinetyNineDotsCaseTests(ENikshayCaseStructureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(NinetyNineDotsCaseTests, cls).setUpClass()
        FormProcessorTestUtils.delete_all_cases()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()

    def test_create_adherence_cases(self):
        self.create_case_structure()
        case_accessor = CaseAccessors(self.domain)
        adherence_values = [
            {
                "timestamp": "2009-03-05T01:00:01-05:00",
                "numberFromWhichPatientDialled": "+910123456789",
                "sharedNumber": False,
                "adherenceSource": "99DOTS",
            },
            {
                "timestamp": "2016-03-05T02:00:01-05:00",
                "numberFromWhichPatientDialled": "+910123456787",
                "sharedNumber": True,
                "adherenceSource": "MERM",
            },
            {
                "timestamp": "2016-03-05T19:00:01-05:00",  # next day in india
                "numberFromWhichPatientDialled": "+910123456787",
                "sharedNumber": True,
            }
        ]
        create_adherence_cases(self.domain, 'person', adherence_values)
        potential_adherence_cases = case_accessor.get_reverse_indexed_cases(['episode'])
        adherence_cases = [case for case in potential_adherence_cases if case.type == 'adherence']
        self.assertEqual(len(adherence_cases), 3)

        self.assertItemsEqual(
            [case.dynamic_case_properties().get('adherence_date') for case in adherence_cases],
            ['2009-03-05', '2016-03-05', '2016-03-06']
        )
        self.assertItemsEqual(
            [case.dynamic_case_properties().get('adherence_source') for case in adherence_cases],
            ['99DOTS', 'MERM', '99DOTS']
        )
        for adherence_case in adherence_cases:
            self.assertEqual(
                adherence_case.dynamic_case_properties().get('adherence_confidence'),
                'high'
            )

    @mock.patch('custom.enikshay.utils.get_id_of_fixture_tagged_adherence_ledger_values', lambda x: '123')
    @mock.patch('custom.enikshay.utils.get_all_fixture_items', lambda x, y: MOCK_FIXTURE_ITEMS)
    def test_update_patient_adherence(self):
        cases = self.create_case_structure()
        episode_case = cases['episode']
        adherence_values = [
            {
                "timestamp": "2009-03-05T01:00:01-05:00",
                "numberFromWhichPatientDialled": "+910123456789",
                "sharedNumber": False,
                "adherenceSource": "99DOTS",
            },
            {
                "timestamp": "2009-03-05T02:00:01-05:00",
                "numberFromWhichPatientDialled": "+910123456789",
                "sharedNumber": False,
                "adherenceSource": "enikshay",
            },
            {
                "timestamp": "2016-03-05T02:00:01-05:00",
                "numberFromWhichPatientDialled": "+910123456787",
                "sharedNumber": True,
                "adherenceSource": "99DOTS",
            },
            {
                "timestamp": "2016-03-05T19:00:01-05:00",  # next day in india
                "numberFromWhichPatientDialled": "+910123456787",
                "sharedNumber": True,
            }
        ]
        create_adherence_cases(self.domain, 'person', adherence_values)

        update_ledger_for_episode(self.domain, episode_case)

        # in case of two doses the relevant one takes over and ledger is updated according to it
        # so balance is 2 for enikshay instead of 14 for 99Dots
        enikshay_adherence_ledger = get_episode_adherence_ledger(self.domain, episode_case.case_id,
                                                                 "date_2009-03-05")
        self.assertEqual(enikshay_adherence_ledger.balance, 2)

        # the only adherence on 2016-03-05
        ninetynine_dots_ledger = get_episode_adherence_ledger(self.domain, episode_case.case_id, "date_2016-03-05")
        ninetynine_dots_ledger.balance = 14

        # the default ledger which had no source mentioned goes to 99dots and is on the next day i.e 2016-03-06
        default_ledger = get_episode_adherence_ledger(self.domain, episode_case.case_id, "date_2016-03-06")
        default_ledger.balance = 14

    def test_update_adherence_confidence(self):
        self.create_case_structure()
        case_accessor = CaseAccessors(self.domain)
        adherence_dates = [
            datetime(2005, 7, 10),
            datetime(2016, 8, 10),
            datetime(2016, 8, 11),
        ]
        adherence_cases = self.create_adherence_cases(adherence_dates)

        update_adherence_confidence_level(
            self.domain,
            self.person_id,
            datetime(2016, 8, 10, tzinfo=pytz.UTC),
            datetime(2016, 8, 11, tzinfo=pytz.UTC),
            "new_confidence_level",
        )
        adherence_case_ids = [adherence_date.strftime("%Y-%m-%d-%H-%M") for adherence_date in adherence_dates]
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

    def test_update_default_confidence_level(self):
        self.create_case_structure()
        confidence_level = "new_confidence_level"
        update_default_confidence_level(self.domain, self.person_id, confidence_level)
        episode = get_open_episode_case_from_person(self.domain, self.person_id)
        self.assertEqual(episode.dynamic_case_properties().get('default_adherence_confidence'), confidence_level)
