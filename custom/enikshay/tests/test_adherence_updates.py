import pytz
from datetime import date
from django.test import TestCase

from corehq.apps.fixtures.models import FixtureDataType, FixtureTypeField, \
    FixtureDataItem, FieldList, FixtureItemField
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from custom.enikshay.tasks import *
from .utils import *


class TestAdherenceUpdater(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestAdherenceUpdater, cls).setUpClass()
        cls.domain = 'adherence-enikshay-test'
        cls.user = CommCareUser.create(
            cls.domain,
            "jon-snow@user",
            "123",
        )
        cls.setupFixtureData()

    def setUp(self):
        super(TestAdherenceUpdater, self).setUp()
        self.factory = CaseFactory(domain=self.domain)
        self.person_id = u"person"
        self.occurrence_id = u"occurrence"
        self.episode_id = u"episode"
        FormProcessorTestUtils.delete_all_cases()
        self.case_updater = EpisodeAdherenceUpdater(self.domain)

    @classmethod
    def setupFixtureData(cls):
        cls.fixture_data = {
            'schedule1': '7',
            'schedule2': '14',
            'schedule3': '21',
        }
        cls.data_type = FixtureDataType(
            domain=cls.domain,
            tag=DAILY_SCHEDULE_FIXTURE_NAME,
            name=DAILY_SCHEDULE_FIXTURE_NAME,
            fields=[
                FixtureTypeField(
                    field_name=SCHEDULE_ID_FIXTURE,
                    properties=[]
                ),
                FixtureTypeField(
                    field_name="doses_per_week",
                    properties=[]
                ),
            ],
            item_attributes=[],
        )
        cls.data_type.save()
        cls.data_items = []
        for _id, value in cls.fixture_data.iteritems():
            data_item = FixtureDataItem(
                domain=cls.domain,
                data_type_id=cls.data_type.get_id,
                fields={
                    SCHEDULE_ID_FIXTURE: FieldList(
                        field_list=[
                            FixtureItemField(
                                field_value=_id,
                            )
                        ]
                    ),
                    "doses_per_week": FieldList(
                        field_list=[
                            FixtureItemField(
                                field_value=value,
                            )
                        ]
                    )
                },
                item_attributes={},
            )
            data_item.save()
            cls.data_items.append(data_item)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.data_type.delete()
        for data_item in cls.data_items:
            data_item.delete()
        super(TestAdherenceUpdater, cls).tearDownClass()

    def _create_episode_case(self, adherence_schedule_date_start, adherence_schedule_id):
        person = get_person_case_structure(
            self.person_id,
            self.user.user_id,
        )

        occurrence = get_occurrence_case_structure(
            self.occurrence_id,
            person
        )

        episode_structure = get_episode_case_structure(
            self.episode_id,
            occurrence,
            extra_update={
                'adherence_schedule_date_start': adherence_schedule_date_start,
                'adherence_schedule_id': adherence_schedule_id
            }
        )
        cases = {case.case_id: case for case in self.factory.create_or_update_cases([episode_structure])}
        return cases[self.episode_id]

    def _create_adherence_cases(self, adherence_cases):
        return self.factory.create_or_update_cases([
            get_adherence_case_structure(
                self.episode_id,
                adherence_date,
                extra_update={
                    "name": adherence_date,
                    "adherence_value": adherence_value,
                }
            )
            for (adherence_date, adherence_value) in adherence_cases
        ])

    def assert_update(self, input, output):
        update = self.calculate_adherence_update(input)
        self.assertDictEqual(
            update.update_json(),
            output
        )

    def calculate_adherence_update(self, input):
        self.case_updater.purge_date = pytz.UTC.localize(input[0])
        # setup episode and adherence cases
        adherence_schedule_date_start, adherence_schedule_id = input[1]
        adherence_cases = input[2]
        episode = self._create_episode_case(adherence_schedule_date_start, adherence_schedule_id)
        self._create_adherence_cases(adherence_cases)

        return EpisodeUpdate(episode, self.case_updater)

    def test_adherence_schedule_date_start_late(self):
        #   Sample test case
        #   [
        #       (
        #           purge_date,
        #           (adherence_schedule_date_start, adherence_schedule_id),
        #           [
        #               (adherence_date, adherence_value),
        #               (adherence_date, adherence_value),
        #               ...
        #           ],
        #           {
        #               'aggregated_score_date_calculated': value
        #               'expected_doses_taken': value
        #               'aggregated_score_count_taken': value
        #           }
        #       ),
        #       ...
        #   ]

        self.assert_update(
            (
                datetime(2016, 1, 15),
                (datetime(2016, 1, 17), 'schedule1'),
                []
            ),
            {
                'aggregated_score_date_calculated': date(2016, 1, 16),
                'expected_doses_taken': 0,
                'aggregated_score_count_taken': 0,
                # 1 day before should be adherence_schedule_date_start,
                'adherence_latest_date_recorded': date(2016, 1, 16),
                'adherence_total_doses_taken': 0
            }
        )

    def test_no_adherence_schedule_date_start(self):
        self.assert_update(
            (
                datetime(2016, 1, 17),
                (None, 'schedule1'),
                []
            ),
            {
            }
        )

    def test_no_adherence_cases(self):
        self.assert_update(
            (
                datetime(2016, 1, 20),
                (datetime(2016, 1, 10), 'schedule1'),
                []
            ),
            {   # change
                'aggregated_score_date_calculated': date(2016, 1, 20),
                'expected_doses_taken': (10.0 / 7) * int(self.fixture_data['schedule1']),
                'aggregated_score_count_taken': 0,
                # 1 day before should be schedule-date-start
                'adherence_latest_date_recorded': date(2016, 1, 9),
                'adherence_total_doses_taken': 0
            }
        )

    def test_adherence_date_less_than_purge_date(self):
        self.assert_update(
            (
                datetime(2016, 1, 20),
                (datetime(2016, 1, 10), 'schedule1'),
                [(datetime(2016, 1, 15), DOSE_TAKEN_INDICATORS[0])]
            ),
            {
                'aggregated_score_date_calculated': date(2016, 1, 15),
                'expected_doses_taken': (5.0 / 7) * int(self.fixture_data['schedule1']),
                'aggregated_score_count_taken': 1,
                'adherence_latest_date_recorded': date(2016, 1, 15),
                'adherence_total_doses_taken': 1
            }
        )

    def test_adherence_date_greater_than_purge_date(self):
        self.assert_update(
            (
                datetime(2016, 1, 20),
                (datetime(2016, 1, 10), 'schedule1'),
                [(datetime(2016, 1, 22), DOSE_TAKEN_INDICATORS[0])]
            ),
            {
                'aggregated_score_date_calculated': date(2016, 1, 20),
                'expected_doses_taken': (10.0 / 7) * int(self.fixture_data['schedule1']),
                'aggregated_score_count_taken': 0,
                'adherence_latest_date_recorded': date(2016, 1, 22),
                'adherence_total_doses_taken': 1
            }
        )

    def test_multiple_adherence_cases_all_greater(self):
        self.assert_update(
            (
                datetime(2016, 1, 20),
                (datetime(2016, 1, 10), 'schedule1'),
                [
                    # same day, different time
                    (datetime(2016, 1, 21, 1), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 21, 3), 'unknown'),
                    (datetime(2016, 1, 22), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 24), DOSE_TAKEN_INDICATORS[0]),
                ]
            ),
            {
                'aggregated_score_date_calculated': date(2016, 1, 20),
                'expected_doses_taken': (10.0 / 7) * int(self.fixture_data['schedule1']),
                'aggregated_score_count_taken': 0,
                'adherence_latest_date_recorded': date(2016, 1, 24),
                'adherence_total_doses_taken': 3
            }
        )

    def test_multiple_adherence_cases_all_less(self):
        self.assert_update(
            (
                datetime(2016, 1, 20),
                (datetime(2016, 1, 10), 'schedule1'),
                [
                    # same day, different time. Set hours different so that case-id becomes different
                    (datetime(2016, 1, 11, 1), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 11, 3), 'unknown'),
                    (datetime(2016, 1, 12), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 14), 'unknown'),
                ]
            ),
            {   # set it to 12, because that's latest known
                'aggregated_score_date_calculated': date(2016, 1, 12),
                'expected_doses_taken': (2.0 / 7) * int(self.fixture_data['schedule1']),
                'aggregated_score_count_taken': 2,
                'adherence_latest_date_recorded': date(2016, 1, 12),
                'adherence_total_doses_taken': 2
            }
        )

    def test_unknown_adherence_data_less_and_greater(self):
        self.assert_update(
            (
                datetime(2016, 1, 20),
                (datetime(2016, 1, 10), 'schedule1'),
                [
                    (datetime(2016, 1, 11), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 12), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 14), 'unknown'),
                    (datetime(2016, 1, 21), 'unknown')
                ]
            ),
            {
                'aggregated_score_date_calculated': date(2016, 1, 12),
                'expected_doses_taken': (2.0 / 7) * int(self.fixture_data['schedule1']),
                'aggregated_score_count_taken': 2,
                'adherence_latest_date_recorded': date(2016, 1, 12),
                'adherence_total_doses_taken': 2
            }
        )

    def test_missed_adherence_dose(self):
        self.assert_update(
            (
                datetime(2016, 1, 20),
                (datetime(2016, 1, 10), 'schedule1'),
                [
                    (datetime(2016, 1, 11), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 12), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 14), 'unknown'),
                    (datetime(2016, 1, 21), DOSE_TAKEN_INDICATORS[3])  # dose missed
                ]
            ),
            {
                'aggregated_score_date_calculated': date(2016, 1, 20),
                'expected_doses_taken': (10.0 / 7) * int(self.fixture_data['schedule1']),
                # ask clayton
                'aggregated_score_count_taken': 2,
                'adherence_latest_date_recorded': date(2016, 1, 21),
                'adherence_total_doses_taken': 3
            }
        )

    def test_two_doses_on_same_day(self):
        self.assert_update(
            (
                datetime(2016, 1, 20),
                (datetime(2016, 1, 10), 'schedule1'),
                [
                    # same day, different time
                    (datetime(2016, 1, 11, 1), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 11, 3), DOSE_TAKEN_INDICATORS[0]),
                ]
            ),
            {
                'aggregated_score_date_calculated': date(2016, 1, 11),
                'expected_doses_taken': (1.0 / 7) * int(self.fixture_data['schedule1']),
                'aggregated_score_count_taken': 1,
                'adherence_latest_date_recorded': date(2016, 1, 11),
                'adherence_total_doses_taken': 1
            }
        )

    def test_two_doses_on_same_day_one_missed(self):
        self.assert_update(
            (
                datetime(2016, 1, 20),
                (datetime(2016, 1, 10), 'schedule1'),
                [
                    (datetime(2016, 1, 11), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 11), DOSE_TAKEN_INDICATORS[3]),
                ]
            ),
            {
                'aggregated_score_date_calculated': date(2016, 1, 11),
                'expected_doses_taken': (1.0 / 7) * int(self.fixture_data['schedule1']),
                'aggregated_score_count_taken': 1,
                'adherence_latest_date_recorded': date(2016, 1, 11),
                'adherence_total_doses_taken': 1
            }
        )
