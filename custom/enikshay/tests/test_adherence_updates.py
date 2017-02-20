from custom.enikshay.tasks import EpisodeUpdate
from django.test import SimpleTestCase


class TestAdherenceUpdater(SimpleTestCase):
    def setUp(self):
        fixture_data = [
            {'schedule1': 7},
            {'schedule2': 14},
            {'schedule3': 21},
        ]

    def tearDown(self):
        pass

    def assert_update(self, input, output):
        update = self.get_episode_update(input)
        self.assertDictsEqual(
            update.update_json(),
            output
        )

    def get_episode_update(self, input):
        self.case_updater.purge_date = input[0]
        # setup episode and adherence cases
        adherence_schedule_date_start, adherence_schedule_id = input[1]
        adherence_cases = input[2]
        episode = self._create_episode_case(adherence_schedule_date_start, adherence_schedule_id)
        self._create_adherence_cases(episode, adherence_cases)

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
                'aggregated_score_date_calculated': datetime(2016, 1, 16)
                'expected_doses_taken': 0
                'aggregated_score_count_taken': 0
            }
        )

    def test_no_adherence_schedule_date_start(self):
        self.assert_update(
            (
                None,
                (datetime(2016, 1, 17), 'schedule1'),
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
            {
                'aggregated_score_date_calculated': datetime(2016, 1, 20)
                'expected_doses_taken': (10 / 7) * self.fixture_data['schedule1']
                'aggregated_score_count_taken': 0
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
                'aggregated_score_date_calculated': datetime(2016, 1, 15)
                'expected_doses_taken': (5 / 7) * self.fixture_data['schedule1']
                'aggregated_score_count_taken': 1
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
                'aggregated_score_date_calculated': datetime(2016, 1, 20)
                'expected_doses_taken': (10 / 7) * self.fixture_data['schedule1']
                'aggregated_score_count_taken': 0
            }
        )

    def test_multiple_adherence_cases_all_greater(self):
        self.assert_update(
            (
                datetime(2016, 1, 20),
                (datetime(2016, 1, 10), 'schedule1'),
                [
                    (datetime(2016, 1, 21), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 22), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 24), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 21), 'unknown')
                ]
            ),
            {
                'aggregated_score_date_calculated': datetime(2016, 1, 20)
                'expected_doses_taken': (10 / 7) * self.fixture_data['schedule1']
                'aggregated_score_count_taken': 0
            }
        )

    def test_multiple_adherence_cases_all_less(self):
        self.assert_update(
            (
                datetime(2016, 1, 20),
                (datetime(2016, 1, 10), 'schedule1'),
                [
                    (datetime(2016, 1, 11), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 12), DOSE_TAKEN_INDICATORS[0]),
                    (datetime(2016, 1, 14), 'unknown'),
                    (datetime(2016, 1, 11), 'unknown')
                ]
            ),
            {
                'aggregated_score_date_calculated': datetime(2016, 1, 14)
                'expected_doses_taken': (4 / 7) * self.fixture_data['schedule1']
                'aggregated_score_count_taken': 2
            }
        )

    def test_multiple_adherence_cases_less_and_greater(self):
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
                'aggregated_score_date_calculated': datetime(2016, 1, 14)
                'expected_doses_taken': (4 / 7) * self.fixture_data['schedule1']
                'aggregated_score_count_taken': 2
            }
        )
