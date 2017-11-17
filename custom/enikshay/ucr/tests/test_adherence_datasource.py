from __future__ import absolute_import
import datetime
import mock

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory
from corehq.apps.users.models import CommCareUser
from corehq.apps.userreports.tasks import rebuild_indicators, queue_async_indicators
from corehq.form_processor.tests.utils import FormProcessorTestUtils


from custom.enikshay.data_store import AdherenceDatastore
from custom.enikshay.const import DOSE_UNKNOWN, DOSE_TAKEN_INDICATORS as DTIndicators
from custom.enikshay.tests.utils import (
    get_person_case_structure,
    get_adherence_case_structure,
    get_occurrence_case_structure,
    get_episode_case_structure
)


def _uid(index):
    return "adherence{}".format(index)


class TestAdherenceUCRSource(TestCase):
    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )

    @classmethod
    def setUpClass(cls):
        super(TestAdherenceUCRSource, cls).setUpClass()
        cls._call_center_domain_mock.start()
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

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        cls.user.delete()
        cls.data_store.adapter.drop_table()
        super(TestAdherenceUCRSource, cls).tearDownClass()
        cls._call_center_domain_mock.stop()

    def tearDown(self):
        self.data_store.adapter.clear_table()
        FormProcessorTestUtils.delete_all_cases()

    def create_adherence_cases(self, data):

        factory = CaseFactory(domain=self.domain)
        cases = factory.create_or_update_cases([
            get_adherence_case_structure(
                case_id,
                self.episode_id,
                adherence_date,
                extra_update={
                    "name": adherence_date,
                    "adherence_value": adherence_value,
                    "source": source,
                    "closure_reason": closure_reason
                }
            )
            for (case_id, adherence_date, adherence_value, source, _, closure_reason, _) in data
        ])

        cases_by_id = {c.case_id: c for c in cases}
        for (case_id, _, _, _, should_close, _, modified_on) in data:
            if should_close:
                factory.close_case(case_id)
            if modified_on:
                cases_by_id[case_id].modified_on = modified_on
                cases_by_id[case_id].save()

        rebuild_indicators(self.data_store.datasource._id)
        queue_async_indicators()
        self.data_store.adapter.refresh_table()

    def test_basic(self):
        simple_data = [
            # (case_id, adherence_date, adherence_value, source, closed, closure_reason, modified_on)
            (_uid(1), datetime.date(2016, 1, 21), DTIndicators[0], 'enikshay', False, None, None),
            (_uid(2), datetime.date(2016, 1, 21), DOSE_UNKNOWN, 'enikshay', False, None, None),
            (_uid(3), datetime.date(2016, 1, 22), DTIndicators[0], 'enikshay', False, None, None),
            (_uid(4), datetime.date(2016, 1, 24), DTIndicators[0], 'enikshay', False, None, None),
        ]
        self.create_adherence_cases(simple_data)

        # test latest adhernece date
        result = self.data_store.latest_adherence_date(self.episode_id)
        self.assertEqual(result, datetime.date(2016, 1, 24))

        # 'adherence2' case has DOSE_UNKNOWN so should be excluded
        result = self.data_store.dose_known_adherences(self.episode_id)
        self.assertEqual(
            {r['doc_id'] for r in result},
            {'adherence1', 'adherence3', 'adherence4'}
        )
