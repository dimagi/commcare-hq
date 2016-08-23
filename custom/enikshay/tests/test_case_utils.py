from datetime import datetime
import pytz

from django.test import TestCase
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin
from corehq.form_processor.tests.utils import run_with_all_backends, FormProcessorTestUtils

from custom.enikshay.case_utils import (
    get_open_episode_case_from_person,
    get_adherence_cases_between_dates,
    get_occurrence_case_from_episode,
    get_person_case_from_occurrence,
)


class ENikshayCaseUtilsTests(ENikshayCaseStructureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(ENikshayCaseUtilsTests, cls).setUpClass()
        FormProcessorTestUtils.delete_all_cases()

    def setUp(self):
        super(ENikshayCaseUtilsTests, self).setUp()
        self.cases = self.create_case_structure()

    def tearDown(self):
        super(ENikshayCaseUtilsTests, self).tearDown()
        FormProcessorTestUtils.delete_all_cases()

    @run_with_all_backends
    def test_get_adherence_cases_between_dates(self):
        adherence_dates = [
            datetime(2005, 7, 10),
            datetime(2016, 8, 10),
            datetime(2016, 8, 11),
            datetime(2016, 8, 12),
            datetime(2017, 9, 10),
        ]
        self.create_adherence_cases(adherence_dates)
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
    def test_get_episode(self):
        self.assertEqual(get_open_episode_case_from_person(self.domain, 'person').case_id, 'episode')

    @run_with_all_backends
    def test_get_occurrence_case_from_episode(self):
        self.assertEqual(
            get_occurrence_case_from_episode(self.domain, self.episode_id).case_id,
            self.occurrence_id
        )

    @run_with_all_backends
    def test_get_person_case_from_occurrence(self):
        self.assertEqual(
            get_person_case_from_occurrence(self.domain, self.occurrence_id).case_id,
            self.person_id
        )
