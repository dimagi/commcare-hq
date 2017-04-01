from datetime import datetime

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory
from corehq.apps.users.models import CommCareUser
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.form_processor.tests.utils import FormProcessorTestUtils


from custom.enikshay.data_store import AdherenceDatastore
from custom.enikshay.tasks import DOSE_UNKNOWN, DOSE_TAKEN_INDICATORS
from custom.enikshay.tests.utils import (
    get_person_case_structure,
    get_adherence_case_structure,
    get_occurrence_case_structure,
    get_episode_case_structure
)


class TestAdherenceUCRSource(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestAdherenceUCRSource, cls).setUpClass()
        cls.domain = "enikshay"
        cls.data_store = AdherenceDatastore(cls.domain)
        cls.user = CommCareUser.create(
            cls.domain,
            "ad-test@user",
            "123",
        )

        cls._setup_casedata()

    @classmethod
    def _setup_casedata(cls):
        cls.episode_id = "episode"
        factory = CaseFactory(domain=cls.domain)

        person = get_person_case_structure(
            "person",
            cls.user.user_id,
        )

        occurrence = get_occurrence_case_structure(
            "occurence",
            person
        )

        episode_structure = get_episode_case_structure(
            cls.episode_id,
            occurrence
        )

        cases = {case.case_id: case for case in factory.create_or_update_cases([episode_structure])}
        cls.episode = cases[cls.episode_id]

        def uid(index):
            return "adherence{}".format(index)

        adherence_data = [
            (uid(1), datetime(2016, 1, 21, 1), DOSE_TAKEN_INDICATORS[0]),
            (uid(2), datetime(2016, 1, 21, 3), DOSE_UNKNOWN),
            (uid(3), datetime(2016, 1, 22), DOSE_TAKEN_INDICATORS[0]),
            (uid(4), datetime(2016, 1, 24), DOSE_TAKEN_INDICATORS[0]),
        ]
        adherence_cases = factory.create_or_update_cases([
            get_adherence_case_structure(
                case_id,
                cls.episode_id,
                adherence_date,
                extra_update={
                    "name": adherence_date,
                    "adherence_value": adherence_value,
                }
            )
            for (case_id, adherence_date, adherence_value) in adherence_data
        ])

        by_case_id = {c.case_id: c for c in adherence_cases}
        cls.latest_adherence_case = by_case_id[uid(4)]
        cls.valid_adherence_value_cases = [by_case_id[uid(x)] for x in range(1, 4)]
        cls.data = [
            cls.latest_adherence_case
        ] + cls.valid_adherence_value_cases

        rebuild_indicators(cls.data_store.datasource._id)
        cls.data_store.adapter.refresh_table()

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        cls.user.delete()
        cls.data_store.adapter.drop_table()
        super(TestAdherenceUCRSource, cls).tearDownClass()

    def test_max_adherence_date(self):
        result = self.data_store.latest_adherence_date(self.episode_id)
        self.assertEqual(result, datetime(2016, 1, 24))

    def test_daterange(self):
        rows = self.data_store.adherences_between(
            self.episode_id, datetime(2016, 1, 21), datetime(2016, 1, 23)
        )
        # should exclude 1 'DOSE_UNKNOWN' and 1 out of range case
        self.assertEqual(
            {r['doc_id'] for r in rows},
            {'adherence1', 'adherence3'}
        )

    def test_dose_known(self):
        result = self.data_store.dose_known_adherences(self.episode_id)

        # 'adherence2' case has DOSE_UNKNOWN so should be excluded
        self.assertEqual(
            {r['doc_id'] for r in result},
            {'adherence1', 'adherence3', 'adherence4'}
        )
