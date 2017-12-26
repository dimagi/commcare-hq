from __future__ import absolute_import
import mock
import datetime
from django.test import TestCase, override_settings

from corehq.apps.fixtures.models import FixtureDataType, FixtureTypeField, \
    FixtureDataItem, FieldList, FixtureItemField
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils

from casexml.apps.case.mock import CaseFactory, CaseStructure
from corehq.apps.users.models import CommCareUser
from corehq.apps.userreports.tasks import rebuild_indicators, queue_async_indicators
from corehq.util.test_utils import update_case

from custom.enikshay.const import (
    DOSE_MISSED,
    DOSE_TAKEN_INDICATORS as DTIndicators,
    DOSE_UNKNOWN,
    DAILY_SCHEDULE_FIXTURE_NAME,
    SCHEDULE_ID_FIXTURE,
    HISTORICAL_CLOSURE_REASON,
)
from custom.enikshay.ledger_utils import get_episode_adherence_ledger
from custom.enikshay.tasks import (
    EpisodeUpdater,
    EpisodeAdherenceUpdate,
    calculate_dose_status_by_day,
    get_datastore,
    update_single_episode,
)
from custom.enikshay.tests.utils import (
    get_person_case_structure,
    get_adherence_case_structure,
    get_occurrence_case_structure,
    get_episode_case_structure
)
import six

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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestAdherenceUpdater(TestCase):
    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )

    @classmethod
    def setUpClass(cls):
        super(TestAdherenceUpdater, cls).setUpClass()
        cls._call_center_domain_mock.start()
        cls.domain = 'enikshay'
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
        self.case_updater = EpisodeUpdater(self.domain)
        self.data_store = get_datastore(self.domain)

    @classmethod
    def setupFixtureData(cls):
        cls.fixture_data = [
            {
                SCHEDULE_ID_FIXTURE: 'schedule1',
                'doses_per_week': '7',
                'dose_count_ip_new_patient': '56',
                'dose_count_ip_recurring_patient': '84',
                'dose_count_cp_new_patient': '112',
                'dose_count_cp_recurring_patient': '140',
                'dose_count_outcome_due_new_patient': '168',
                'dose_count_outcome_due_recurring_patient': '168',
            },
            {
                SCHEDULE_ID_FIXTURE: 'schedule2',
                'doses_per_week': '14',
                'dose_count_ip_new_patient': '24',
                'dose_count_ip_recurring_patient': '36',
                'dose_count_cp_new_patient': '54',
                'dose_count_cp_recurring_patient': '66',
                'dose_count_outcome_due_new_patient': '78',
                'dose_count_outcome_due_recurring_patient': '78',
            },
            {
                SCHEDULE_ID_FIXTURE: 'schedule3',
                'doses_per_week': '21',
                'dose_count_ip_new_patient': '24',
                'dose_count_ip_recurring_patient': '36',
                'dose_count_cp_new_patient': '54',
                'dose_count_cp_recurring_patient': '66',
                'dose_count_outcome_due_new_patient': '78',
                'dose_count_outcome_due_recurring_patient': '78',
            },
        ]
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
        for row in cls.fixture_data:
            data_item = FixtureDataItem(
                domain=cls.domain,
                data_type_id=cls.data_type.get_id,
                fields={
                    column_name: FieldList(
                        field_list=[
                            FixtureItemField(
                                field_value=value,
                            )
                        ]
                    )
                    for column_name, value in six.iteritems(row)
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
        cls._call_center_domain_mock.stop()

    def tearDown(self):
        get_datastore.reset_cache()
        self.data_store.adapter.clear_table()
        FormProcessorTestUtils.delete_all_cases()

    def _create_episode_case(
            self,
            adherence_schedule_date_start=None,
            adherence_schedule_id=None,
            extra_properties=None,
    ):
        person = get_person_case_structure(
            self.person_id,
            self.user.user_id,
        )

        occurrence = get_occurrence_case_structure(
            self.occurrence_id,
            person
        )

        extra_update = {
            'adherence_schedule_date_start': adherence_schedule_date_start,
            'adherence_schedule_id': adherence_schedule_id
        }
        extra_update.update(extra_properties or {})

        episode_structure = get_episode_case_structure(
            self.episode_id,
            occurrence,
            extra_update=extra_update,
        )
        cases = {case.case_id: case for case in self.factory.create_or_update_cases([episode_structure])}
        episode_case = cases[self.episode_id]
        self.case_updater._get_open_episode_cases = mock.MagicMock(return_value=[episode_case])
        return episode_case

    def _create_adherence_cases(self, case_dicts):
        return self.factory.create_or_update_cases([
            get_adherence_case_structure(
                "adherence{}".format(i),
                self.episode_id,
                case['name'],
                extra_update=case
            )
            for i, case in enumerate(case_dicts)
        ])

    def assert_update(self, purge_date, adherence_schedule_date_start,
                      adherence_schedule_id, adherence_cases, episode_properties=None,
                      date_today_in_india=None, output=None):
        adherence_cases = [
            {
                "name": adherence_case[0],
                "adherence_value": adherence_case[1],
                "adherence_source": "enikshay",
                "adherence_report_source": "treatment_supervisor"
            }
            for adherence_case in adherence_cases
        ]
        episode = self.create_episode_case(
            adherence_schedule_date_start, adherence_schedule_id, adherence_cases,
            extra_properties=episode_properties,
        )

        updater = EpisodeAdherenceUpdate(self.domain, episode)
        updater.purge_date = purge_date
        if date_today_in_india is not None:
            updater.date_today_in_india = date_today_in_india

        return self.assert_properties_equal(output, updater.update_json())

    def assert_properties_equal(self, expected, actual):

        self.assertDictContainsSubset(
            # convert values to strings
            {key: str(val) for key, val in six.iteritems(expected)},
            {key: str(actual[key]) for key in expected},
        )

    def _get_updated_episode(self):

        self.case_updater.run()
        return CaseAccessors(self.domain).get_case(self.episode_id)

    def create_episode_case(
            self,
            adherence_schedule_date_start,
            adherence_schedule_id,
            adherence_cases,
            extra_properties=None,
    ):
        episode = self._create_episode_case(adherence_schedule_date_start, adherence_schedule_id, extra_properties)
        adherence_cases = self._create_adherence_cases(adherence_cases)
        self._rebuild_indicators()
        return episode

    def _rebuild_indicators(self):
        # rebuild so that adherence UCR data gets updated
        rebuild_indicators(self.data_store.datasource._id)
        queue_async_indicators()
        self.data_store.adapter.refresh_table()

    def test_invalid_cases(self):
        """Invalid cases shouldn't be triggered
        """
        person = get_person_case_structure(self.person_id, self.user.user_id)

        occurrence = get_occurrence_case_structure(self.occurrence_id, person)

        episode_structure = get_episode_case_structure(self.episode_id, occurrence)
        self.factory.create_or_update_case(episode_structure)

        archived_person = get_person_case_structure("person_2", self.user.user_id, owner_id="_archive_")
        occurrence = get_occurrence_case_structure('occurrence_2', archived_person)
        invalid_episode_structure = get_episode_case_structure('episode_2', occurrence)
        self.factory.create_or_update_case(invalid_episode_structure)

        closed_person = get_person_case_structure("person_3", self.user.user_id)
        occurrence = get_occurrence_case_structure('occurrence_3', closed_person)
        closed_episode_structure = get_episode_case_structure('episode_3', occurrence)
        self.factory.create_or_update_case(closed_episode_structure)
        self.factory.create_or_update_case(CaseStructure(
            case_id="person_3",
            attrs={'close': True}
        ))
        case_ids = [
            item for batch in self.case_updater._get_case_id_batches()
            for item in batch
        ]
        episode_ids = [episode.case_id
                       for episode in self.case_updater._get_open_episode_cases(case_ids)]
        self.assertEqual(episode_ids, [self.episode_id])

    def test_adherence_schedule_date_start_late(self):
        self.assert_update(
            datetime.date(2016, 1, 15), datetime.date(2016, 1, 17), 'schedule1',
            adherence_cases=[],
            output={
                'aggregated_score_date_calculated': datetime.date(2016, 1, 16),
                'expected_doses_taken': 0,
                'aggregated_score_count_taken': 0,
                # 1 day before should be adherence_schedule_date_start,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 16),
                'adherence_total_doses_taken': 0
            }
        )

    def test_no_adherence_schedule_date_start(self):
        # if adherence_schedule_date_start then don't update
        self.assert_update(datetime.date(2016, 1, 17), None, 'schedule1', [], output={})

    def test_no_adherence_cases(self):
        self.assert_update(
            datetime.date(2016, 1, 20), datetime.date(2016, 1, 10), 'schedule1', [],
            output={
                # 1 day before adherence_schedule_date_start
                'aggregated_score_date_calculated': datetime.date(2016, 1, 9),
                # set to zero
                'expected_doses_taken': 0,
                'aggregated_score_count_taken': 0,
                'adherence_total_doses_taken': 0,
                # 1 day before should be adherence_schedule_date_start
                'adherence_latest_date_recorded': datetime.date(2016, 1, 9),
            }
        )

    def test_adherence_date_less_than_purge_date(self):
        purge_date = datetime.date(2016, 1, 20)
        adherence_schedule_start_date = datetime.date(2016, 1, 10)
        latest_adherence_date = datetime.date(2016, 1, 15)
        expected_doses_taken = 6

        self.assert_update(
            purge_date,
            adherence_schedule_start_date,
            'schedule1',
            # if adherence_date less than purge_date
            [(latest_adherence_date, DTIndicators[0])],
            output={
                # set to latest adherence_date
                'aggregated_score_date_calculated': datetime.date(2016, 1, 15),
                # co-efficient (aggregated_score_date_calculated - adherence_schedule_date_start)
                'expected_doses_taken': expected_doses_taken,
                'aggregated_score_count_taken': 1,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 15),
                'adherence_total_doses_taken': 1
            }
        )

    def test_adherence_date_greater_than_purge_date(self):
        purge_date = datetime.date(2016, 1, 31)
        adherence_schedule_start_date = datetime.date(2016, 1, 1)
        expected_doses_taken = 31

        self.assert_update(
            purge_date,
            adherence_schedule_start_date,
            'schedule1',
            # if adherence_date is later than adherence_schedule_date_start
            [(datetime.date(2016, 2, 22), DTIndicators[0])],
            output={
                'aggregated_score_date_calculated': purge_date,
                'expected_doses_taken': expected_doses_taken,
                # no doses taken before purge_date
                'aggregated_score_count_taken': 0,
                # latest adherence taken date
                'adherence_latest_date_recorded': datetime.date(2016, 2, 22),
                'adherence_total_doses_taken': 1
            }
        )

    def test_multiple_adherence_cases_all_greater(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 10), 'schedule1',
            [
                # same day, different time
                (datetime.date(2016, 1, 21), DTIndicators[0]),
                (datetime.date(2016, 1, 21), DOSE_UNKNOWN),
                (datetime.date(2016, 1, 22), DTIndicators[0]),
                (datetime.date(2016, 1, 24), DTIndicators[0]),
            ],
            output={   # should be purge_date
                'aggregated_score_date_calculated': datetime.date(2016, 1, 20),
                # co-efficient (aggregated_score_date_calculated - adherence_schedule_date_start)
                'expected_doses_taken': int((11.0 / 7) * int(self.fixture_data[0]['doses_per_week'])),
                # no dose taken before aggregated_score_date_calculated
                'aggregated_score_count_taken': 0,
                # latest recorded
                'adherence_latest_date_recorded': datetime.date(2016, 1, 24),
                # total 3 taken, unknown is not counted
                'adherence_total_doses_taken': 3
            }
        )

    def _generate_doses_taken(self, start_date, num_days, dose_status=None):
        return [
            (start_date + datetime.timedelta(days=i), dose_status or DTIndicators[0])
            for i in range(num_days)
        ]

    def test_ip_date_followup_blank_schedule1(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 20), 'schedule1',
            self._generate_doses_taken(datetime.date(2016, 1, 20), 5),
            output={
                'adherence_total_doses_taken': 5,
                'adherence_ip_date_followup_test_expected': '',
                'adherence_ip_date_threshold_crossed': '',
            },
        )

    def test_ip_date_followup_set_schedule1(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 20), 'schedule1',
            self._generate_doses_taken(datetime.date(2016, 1, 20), 100),
            output={
                'adherence_total_doses_taken': 100,
                'adherence_ip_date_followup_test_expected': '2016-04-12',
                'adherence_ip_date_threshold_crossed': '2016-04-05',
            },
        )

    def test_cp_date_followup_blank_schedule1(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 20), 'schedule1',
            self._generate_doses_taken(datetime.date(2016, 1, 20), 5),
            output={
                'adherence_total_doses_taken': 5,
                'adherence_cp_date_followup_test_expected': '',
                'adherence_cp_date_threshold_crossed': '',
            },
        )

    def test_cp_date_followup_set_schedule1(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 20), 'schedule1',
            self._generate_doses_taken(datetime.date(2016, 1, 20), 200),
            output={
                'adherence_total_doses_taken': 200,
                'adherence_cp_date_followup_test_expected': '2016-06-07',
                'adherence_cp_date_threshold_crossed': '2016-05-31',
            },
        )

    def test_outcome_due_blank_schedule1(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 20), 'schedule1',
            self._generate_doses_taken(datetime.date(2016, 1, 20), 5),
            output={
                'adherence_total_doses_taken': 5,
                'adherence_date_outcome_due': '',
            },
        )

    def test_outcome_due_set_schedule1(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 20), 'schedule1',
            self._generate_doses_taken(datetime.date(2016, 1, 20), 200),
            output={
                'adherence_total_doses_taken': 200,
                'adherence_date_outcome_due': '2016-07-05',
            },
        )

    def test_ip_date_followup_blank_schedule1_new_patient(self):
        update_case(self.domain, self.episode_id, {'patient_type_choice': 'new'})
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 20), 'schedule1',
            self._generate_doses_taken(datetime.date(2016, 1, 20), 5),
            output={
                'adherence_total_doses_taken': 5,
                'adherence_ip_date_followup_test_expected': '',
                'adherence_ip_date_threshold_crossed': '',
            },
        )

    def test_ip_date_followup_set_schedule1_new_patient(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 20), 'schedule1',
            self._generate_doses_taken(datetime.date(2016, 1, 20), 200),
            episode_properties={'patient_type_choice': 'new'},
            output={
                'adherence_total_doses_taken': 200,
                'adherence_ip_date_followup_test_expected': '2016-03-15',
                'adherence_ip_date_threshold_crossed': '2016-03-08',
            },
        )

    def test_ip_date_followup_blank_schedule2(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 20), 'schedule2',
            self._generate_doses_taken(datetime.date(2016, 1, 20), 5),
            output={
                'adherence_total_doses_taken': 5,
                'adherence_ip_date_followup_test_expected': '',
                'adherence_ip_date_threshold_crossed': '',
            },
        )

    def test_ip_date_followup_set_schedule2(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 20), 'schedule2',
            self._generate_doses_taken(datetime.date(2016, 1, 20), 200),
            output={
                'adherence_total_doses_taken': 200,
                'adherence_ip_date_followup_test_expected': '2016-02-17',
                'adherence_ip_date_threshold_crossed': '2016-02-10',
            },
        )

    def test_ip_date_followup_blank_doses_missed(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 20), 'schedule1',
            self._generate_doses_taken(datetime.date(2016, 1, 20), 200, dose_status=DOSE_MISSED),
            output={
                'adherence_total_doses_taken': 0,
                'adherence_ip_date_followup_test_expected': '',
                'adherence_ip_date_threshold_crossed': '',
            },
        )

    def test_multiple_adherence_cases_all_less(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 10), 'schedule1',
            [
                # same day, different time. Set hours different so that case-id becomes different
                (datetime.date(2016, 1, 11), DTIndicators[0]),
                (datetime.date(2016, 1, 11), DOSE_UNKNOWN),
                (datetime.date(2016, 1, 12), DTIndicators[0]),
                (datetime.date(2016, 1, 14), DOSE_UNKNOWN),
            ],
            output={   # set to latest adherence_date, exclude 14th because its unknown
                'aggregated_score_date_calculated': datetime.date(2016, 1, 12),
                'expected_doses_taken': int((3.0 / 7) * int(self.fixture_data[0]['doses_per_week'])),
                'aggregated_score_count_taken': 2,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 12),
                'adherence_total_doses_taken': 2
            }
        )

    def test_unknown_adherence_data_less_and_greater(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 10), 'schedule1',
            [
                (datetime.date(2016, 1, 11), DTIndicators[0]),
                (datetime.date(2016, 1, 12), DTIndicators[0]),
                (datetime.date(2016, 1, 14), DOSE_UNKNOWN),
                (datetime.date(2016, 1, 21), DOSE_UNKNOWN)
            ],
            output={
                'aggregated_score_date_calculated': datetime.date(2016, 1, 12),
                'expected_doses_taken': int((3.0 / 7) * int(self.fixture_data[0]['doses_per_week'])),
                'aggregated_score_count_taken': 2,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 12),
                'adherence_total_doses_taken': 2
            }
        )

    def test_missed_adherence_dose(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 10), 'schedule1',
            [
                (datetime.date(2016, 1, 11), DTIndicators[0]),
                (datetime.date(2016, 1, 12), DTIndicators[0]),
                (datetime.date(2016, 1, 14), DOSE_UNKNOWN),
                (datetime.date(2016, 1, 21), DOSE_MISSED)  # dose missed
            ],
            output={
                'aggregated_score_date_calculated': datetime.date(2016, 1, 20),
                'expected_doses_taken': int((11.0 / 7) * int(self.fixture_data[0]['doses_per_week'])),
                'aggregated_score_count_taken': 2,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 21),
                'adherence_total_doses_taken': 2
            }
        )

    def test_two_doses_on_same_day(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 10), 'schedule1',
            [
                # same day, different time
                (datetime.date(2016, 1, 11), DTIndicators[0]),
                (datetime.date(2016, 1, 11), DTIndicators[0]),
            ],
            output={
                'aggregated_score_date_calculated': datetime.date(2016, 1, 11),
                'expected_doses_taken': int((2.0 / 7) * int(self.fixture_data[0]['doses_per_week'])),
                'aggregated_score_count_taken': 1,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 11),
                'adherence_total_doses_taken': 1
            }
        )

    def test_two_doses_on_same_day_different_values(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 10), 'schedule1',
            [
                (datetime.date(2016, 1, 11), DTIndicators[0]),
                (datetime.date(2016, 1, 11), DTIndicators[2]),
            ],
            output={
                'aggregated_score_date_calculated': datetime.date(2016, 1, 11),
                'expected_doses_taken': int((2.0 / 7) * int(self.fixture_data[0]['doses_per_week'])),
                'aggregated_score_count_taken': 1,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 11),
                'adherence_total_doses_taken': 1
            }
        )

    def test_dose_unknown_less(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 10), 'schedule1',
            [
                (datetime.date(2016, 1, 11), DOSE_UNKNOWN),
            ],
            output={
                'aggregated_score_date_calculated': datetime.date(2016, 1, 9),
                'expected_doses_taken': 0,
                'aggregated_score_count_taken': 0,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 9),
                'adherence_total_doses_taken': 0
            }
        )

    def test_dose_missed_less(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 10), 'schedule1',
            [
                (datetime.date(2016, 1, 11), DOSE_MISSED),
            ],
            output={
                'aggregated_score_date_calculated': datetime.date(2016, 1, 11),
                'expected_doses_taken': int((2.0 / 7) * int(self.fixture_data[0]['doses_per_week'])),
                'aggregated_score_count_taken': 0,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 11),
                'adherence_total_doses_taken': 0
            }
        )

    def test_dose_unknown_greater(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 10), 'schedule1',
            [
                (datetime.date(2016, 1, 22), DOSE_UNKNOWN),
            ],
            output={
                'aggregated_score_date_calculated': datetime.date(2016, 1, 9),
                'expected_doses_taken': 0,
                'aggregated_score_count_taken': 0,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 9),
                'adherence_total_doses_taken': 0
            }
        )

    def test_dose_missed_greater(self):
        self.assert_update(
            datetime.date(2016, 1, 20),
            datetime.date(2016, 1, 10), 'schedule1',
            [
                (datetime.date(2016, 1, 22), DOSE_MISSED),
            ],
            output={
                'aggregated_score_date_calculated': datetime.date(2016, 1, 20),
                'expected_doses_taken': int((11.0 / 7) * int(self.fixture_data[0]['doses_per_week'])),
                'aggregated_score_count_taken': 0,
                'adherence_latest_date_recorded': datetime.date(2016, 1, 22),
                'adherence_total_doses_taken': 0
            }
        )

    def test_count_doses_taken_by_source(self):
        adherence_cases = [
            {
                "name": 'Bad source shouldnt show up',
                "adherence_source": "enikshay",
                "adherence_report_source": "Bad source",
                "adherence_value": 'unobserved_dose',
                "adherence_date": datetime.date(2017, 8, 14),
            },
            {
                "name": '1',
                "adherence_source": "99DOTS",
                "adherence_value": 'unobserved_dose',
                "adherence_date": datetime.date(2017, 8, 15),
            },
            {
                "name": '2',
                "adherence_source": "99DOTS",
                "adherence_value": 'unobserved_dose',
                "adherence_date": datetime.date(2017, 8, 16),
            },
            {
                "name": '3',
                "adherence_source": "99DOTS",
                "adherence_value": 'unobserved_dose',
                "adherence_date": datetime.date(2017, 8, 17),
            },
            {
                "name": '4',
                "adherence_source": "MERM",
                "adherence_value": 'unobserved_dose',
                "adherence_date": datetime.date(2017, 8, 18),
            },
            {
                "name": 'overwrites 99DOTS case',
                "adherence_source": "enikshay",
                "adherence_value": 'unobserved_dose',
                "adherence_report_source": "treatment_supervisor",
                "adherence_date": datetime.date(2017, 8, 16),  # overwrites the 99DOTS case of this date
            }
        ]
        episode = self.create_episode_case(
            adherence_schedule_date_start=datetime.date(2017, 8, 12),
            adherence_schedule_id='schedule1',
            adherence_cases=adherence_cases,
        )

        updater = EpisodeAdherenceUpdate(self.domain, episode)
        updater.purge_date = datetime.date(2017, 8, 10),
        dose_status_by_day = calculate_dose_status_by_day(updater.get_valid_adherence_cases())
        self.assertDictEqual(
            {
                '99DOTS': 2,
                'MERM': 1,
                'treatment_supervisor': 1,
            },
            EpisodeAdherenceUpdate.count_doses_taken_by_source(dose_status_by_day)
        )

        self.assertDictEqual(
            {
                '99DOTS': 1,
                'MERM': 1,
            },
            EpisodeAdherenceUpdate.count_doses_taken_by_source(
                dose_status_by_day,
                start_date=datetime.date(2017, 8, 17),
                end_date=datetime.date(2017, 8, 18)
            )
        )

    def test_count_taken_by_day(self):
        episode = self.create_episode_case(
            adherence_schedule_date_start=datetime.date(2016, 1, 10),
            adherence_schedule_id='schedule1',
            adherence_cases=[]
        )
        episode_update = EpisodeAdherenceUpdate(self.domain, episode)
        episode_update.purge_date = datetime.date(2016, 1, 20)

        def dose_source_by_day(cases, day):
            # cases a list of tuples
            # (case_id, adherence_date, modified_on, adherence_value, source, closed, closure_reason)
            return calculate_dose_status_by_day(
                [
                    {
                        'adherence_source': source,
                        'adherence_date': str(dose_date),  # the code expects string format
                        'adherence_value': dose_value,
                        'closed': closed,
                        'adherence_closure_reason': closure_reason,
                        'modified_on': modified_on,
                    }
                    for (_, dose_date, modified_on, dose_value, source, closed, closure_reason) in cases
                ]
            )[day].source

        ## test enikshay only source, open cases
        # not-taken - latest_modified_on case says no dose taken
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 21), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', False, None),
                ('some_id', datetime.date(2016, 1, 21), datetime.date(2016, 2, 22),
                 DOSE_UNKNOWN, 'enikshay', False, None),
            ], datetime.date(2016, 1, 21)),
            False
        )
        # taken - latest_modified_on case says dose taken
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 22), datetime.date(2016, 2, 22),
                 DTIndicators[0], 'enikshay', False, None),
                ('some_id', datetime.date(2016, 1, 22), datetime.date(2016, 2, 21),
                 DOSE_UNKNOWN, 'enikshay', False, None),
            ], datetime.date(2016, 1, 22)),
            'enikshay'
        )

        ## test enikshay only source, closed/closure_reason cases
        # not taken - as 1st case is not relevant because closed, closure_reason. 2nd case says no dose taken
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 23), datetime.date(2016, 2, 22),
                 DTIndicators[0], 'enikshay', True, None),
                ('some_id', datetime.date(2016, 1, 23), datetime.date(2016, 2, 21),
                 DOSE_UNKNOWN, 'enikshay', False, None),
            ], datetime.date(2016, 1, 23)),
            False
        )
        # taken - as 1st case is not relevant because closed, closure_reason. 2nd case says dose taken
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 24), datetime.date(2016, 2, 22),
                 DOSE_UNKNOWN, 'enikshay', True, None),
                ('some_id', datetime.date(2016, 1, 24), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', False, None),
            ], datetime.date(2016, 1, 24)),
            'enikshay'
        )
        # not taken - as 1st case is relevent case with latest_modified_on and says dose not taken
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 25), datetime.date(2016, 2, 22),
                 DOSE_UNKNOWN, 'enikshay', True, HISTORICAL_CLOSURE_REASON),
                ('some_id', datetime.date(2016, 1, 25), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', False, None),
            ], datetime.date(2016, 1, 25)),
            False
        )
        # taken - as 1st case is relevent case with latest_modified_on and says dose is taken
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 26), datetime.date(2016, 2, 22),
                 DTIndicators[0], 'enikshay', True, HISTORICAL_CLOSURE_REASON),
                ('some_id', datetime.date(2016, 1, 26), datetime.date(2016, 2, 21),
                 DOSE_UNKNOWN, 'enikshay', False, None),
            ], datetime.date(2016, 1, 26)),
            'enikshay'
        )

        ## test non-enikshay source only cases
        # not taken - non-enikshay source, so consider latest_modified_on
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 27), datetime.date(2016, 2, 22),
                 DOSE_UNKNOWN, 'non-enikshay', True, 'a'),
                ('some_id', datetime.date(2016, 1, 27), datetime.date(2016, 2, 21),
                 DTIndicators[0], '99dots', False, None),
            ], datetime.date(2016, 1, 27)),
            False
        )
        # taken - non-enikshay source, so consider latest_modified_on
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 28), datetime.date(2016, 2, 22),
                 DTIndicators[0], '99DOTS', True, 'a'),
                ('some_id', datetime.date(2016, 1, 28), datetime.date(2016, 2, 21),
                 DOSE_UNKNOWN, '99DOTS', False, None),
            ], datetime.date(2016, 1, 28)),
            '99DOTS'
        )

        ## test mix of enikshay, non-enikshay sources
        # taken - as enikshay source case says taken
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 29), datetime.date(2016, 2, 22),
                 DTIndicators[0], '99', True, 'a'),
                ('some_id', datetime.date(2016, 1, 29), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', False, None),
            ], datetime.date(2016, 1, 29)),
            'enikshay'
        )
        # not taken - as enikshay source case says not taken
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 1), datetime.date(2016, 2, 22),
                 DTIndicators[0], '99', True, 'a'),
                ('some_id', datetime.date(2016, 1, 1), datetime.date(2016, 2, 21),
                 DOSE_UNKNOWN, 'enikshay', False, None),
            ], datetime.date(2016, 1, 1)),
            False
        )
        # not taken - as the only enikshay source case is closed without valid-reason
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 2), datetime.date(2016, 2, 22),
                 DTIndicators[0], '99', True, 'a'),
                ('some_id', datetime.date(2016, 1, 2), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', True, None),
            ], datetime.date(2016, 1, 2)),
            False
        )
        # taken - as the only enikshay source case is closed with right closure_reason
        self.assertEqual(
            dose_source_by_day([
                ('some_id', datetime.date(2016, 1, 3), datetime.date(2016, 2, 22),
                 DOSE_UNKNOWN, '99', True, 'a'),
                ('some_id', datetime.date(2016, 1, 3), datetime.date(2016, 2, 21),
                 DTIndicators[0], 'enikshay', True, HISTORICAL_CLOSURE_REASON),
            ], datetime.date(2016, 1, 3)),
            'enikshay'
        )

    def test_update_by_person(self):
        expected_update = {
            'aggregated_score_date_calculated': datetime.date(2016, 1, 16),
            'expected_doses_taken': 0,
            'aggregated_score_count_taken': 0,
            # 1 day before should be adherence_schedule_date_start,
            'adherence_latest_date_recorded': datetime.date(2016, 1, 16),
            'adherence_total_doses_taken': 0
        }

        episode = self.create_episode_case(
            datetime.date(2016, 1, 17),
            'schedule1',
            []
        )
        update_single_episode(self.domain, episode)

        episode = CaseAccessors(self.domain).get_case(episode.case_id)
        self.assertDictEqual(
            {key: episode.dynamic_case_properties()[key] for key in expected_update},
            {key: str(val) for key, val in six.iteritems(expected_update)}  # convert values to strings
        )

    def test_adherence_score_start_date_month(self):
        # If the start date is more than a month ago, calculate the last month's scores
        self.assert_update(
            datetime.date(2016, 1, 30),
            datetime.date(2015, 12, 31), 'schedule1',
            [
                (datetime.date(2015, 12, 31), DTIndicators[0]),
                (datetime.date(2016, 1, 15), DTIndicators[0]),
                (datetime.date(2016, 1, 17), DTIndicators[0]),
                (datetime.date(2016, 1, 20), DTIndicators[0]),
                (datetime.date(2016, 1, 30), DTIndicators[0]),
            ],
            output={
                'three_day_score_count_taken': 1,
                'one_week_score_count_taken': 1,
                'two_week_score_count_taken': 3,
                'month_score_count_taken': 4,
                'three_day_adherence_score': 33.33,
                'one_week_adherence_score': 14.29,
                'two_week_adherence_score': 21.43,
                'month_adherence_score': 13.33,
            },
            date_today_in_india=datetime.date(2016, 1, 31)
        )

    def test_adherence_score_start_date_week(self):
        # If the start date is only a week ago, don't send 2 week or month scores
        self.assert_update(
            datetime.date(2016, 1, 30),
            datetime.date(2016, 1, 24), 'schedule1',
            [
                (datetime.date(2015, 12, 31), DTIndicators[0]),
                (datetime.date(2016, 1, 15), DTIndicators[0]),
                (datetime.date(2016, 1, 17), DTIndicators[0]),
                (datetime.date(2016, 1, 20), DTIndicators[0]),
                (datetime.date(2016, 1, 30), DTIndicators[0]),
            ],
            output={
                'three_day_score_count_taken': 1,
                'one_week_score_count_taken': 1,
                'two_week_score_count_taken': 0,
                'month_score_count_taken': 0,
                'three_day_adherence_score': 33.33,
                'one_week_adherence_score': 14.29,
                'two_week_adherence_score': 0.0,
                'month_adherence_score': 0.0,
            },
            date_today_in_india=datetime.date(2016, 1, 31),
        )

    def test_adherence_score_by_source(self):
        adherence_cases = [
            {
                "name": '1',
                "adherence_source": "99DOTS",
                "adherence_value": 'unobserved_dose',
                "adherence_date": datetime.date(2015, 12, 31),
            },
            {
                "name": '2',
                "adherence_source": "99DOTS",
                "adherence_value": 'unobserved_dose',
                "adherence_date": datetime.date(2016, 1, 15),
            },
            {
                "name": '5',
                "adherence_source": "enikshay",
                "adherence_report_source": "other",
                "adherence_value": 'unobserved_dose',
                "adherence_date": datetime.date(2016, 1, 17),
            },
            {
                "name": '3',
                "adherence_source": "99DOTS",
                "adherence_value": 'unobserved_dose',
                "adherence_date": datetime.date(2016, 1, 20),
            },
            {
                "name": '4',
                "adherence_source": "MERM",
                "adherence_value": 'unobserved_dose',
                "adherence_date": datetime.date(2016, 1, 30),
            },
        ]
        episode = self.create_episode_case(
            adherence_schedule_date_start=datetime.date(2015, 12, 1),
            adherence_schedule_id='schedule1',
            adherence_cases=adherence_cases,
        )
        updater = EpisodeAdherenceUpdate(self.domain, episode)
        updater.date_today_in_india = datetime.date(2016, 1, 31)
        expected = {
            'three_day_score_count_taken_99DOTS': 0,
            'one_week_score_count_taken_99DOTS': 0,
            'two_week_score_count_taken_99DOTS': 1,
            'month_score_count_taken_99DOTS': 2,
            'three_day_adherence_score_99DOTS': 0.0,
            'one_week_adherence_score_99DOTS': 0.0,
            'two_week_adherence_score_99DOTS': 7.14,
            'month_adherence_score_99DOTS': 6.67,

            'three_day_score_count_taken_MERM': 1,
            'one_week_score_count_taken_MERM': 1,
            'two_week_score_count_taken_MERM': 1,
            'month_score_count_taken_MERM': 1,
            'three_day_adherence_score_MERM': 33.33,
            'one_week_adherence_score_MERM': 14.29,
            'two_week_adherence_score_MERM': 7.14,
            'month_adherence_score_MERM': 3.33,

            'three_day_score_count_taken_other': 0,
            'one_week_score_count_taken_other': 0,
            'two_week_score_count_taken_other': 1,
            'month_score_count_taken_other': 1,
            'three_day_adherence_score_other': 0.0,
            'one_week_adherence_score_other': 0.0,
            'two_week_adherence_score_other': 7.14,
            'month_adherence_score_other': 3.33,

            'three_day_score_count_taken_treatment_supervisor': 0,
            'one_week_score_count_taken_treatment_supervisor': 0,
            'two_week_score_count_taken_treatment_supervisor': 0,
            'month_score_count_taken_treatment_supervisor': 0,
            'three_day_adherence_score_treatment_supervisor': 0.0,
            'one_week_adherence_score_treatment_supervisor': 0.0,
            'two_week_adherence_score_treatment_supervisor': 0.0,
            'month_adherence_score_treatment_supervisor': 0.0,
        }

        self.assert_properties_equal(expected, updater.update_json())

    @mock.patch('custom.enikshay.ledger_utils._adherence_values_fixture_id', lambda x: '123')
    @mock.patch('custom.enikshay.ledger_utils._get_all_fixture_items', lambda x, y: MOCK_FIXTURE_ITEMS)
    def test_ledger_updates(self):
        adherence_cases = [
            {
                "name": '1',
                "adherence_date": datetime.datetime(2009, 3, 5, 2, 0, 1),
                "adherence_value": 'unobserved_dose',
                "adherence_source": "enikshay",
            },
            {
                "name": '2',
                "adherence_date": datetime.datetime(2009, 3, 5, 1, 0, 1),
                "adherence_value": 'unobserved_dose',
                "adherence_source": "99DOTS",
            },
            {
                "name": '3',
                "adherence_date": datetime.datetime(2016, 3, 5, 2, 0, 1),
                "adherence_value": 'unobserved_dose',
                "adherence_source": "MERM",
            },
            {
                "name": '4',
                "adherence_date": datetime.datetime(2016, 3, 5, 19, 0, 1),  # next day in india
                "adherence_value": 'unobserved_dose',
                "adherence_source": "99DOTS",
            }
        ]
        episode = self.create_episode_case(
            adherence_schedule_date_start=datetime.date(2015, 12, 1),
            adherence_schedule_id='schedule1',
            adherence_cases=adherence_cases,
        )
        self.case_updater.run()
        # in case of two doses the relevant one takes over and ledger is updated according to it
        # so balance is 2 for enikshay instead of 14 for 99Dots
        enikshay_adherence_ledger = get_episode_adherence_ledger(self.domain, episode.case_id,
                                                                 "date_2009-03-05")
        self.assertEqual(enikshay_adherence_ledger.balance, 2)

        # the only adherence on 2016-03-05
        ninetynine_dots_ledger = get_episode_adherence_ledger(self.domain, episode.case_id, "date_2016-03-05")
        ninetynine_dots_ledger.balance = 14

    def test_missed_and_unknown_doses(self):
        adherence_cases = [{
            "name": str(i),
            "adherence_source": "enikshay",
            "adherence_value": adherence_value,
            "adherence_date": date,
        } for i, (adherence_value, date) in enumerate([
            # one month
            (DOSE_MISSED, datetime.date(2016, 1, 13)),
            ('unobserved_dose', datetime.date(2016, 1, 15)),
            # two weeks
            ('directly_observed_dose', datetime.date(2016, 1, 17)),
            (DOSE_UNKNOWN, datetime.date(2016, 1, 18)),
            # one week
            ('directly_observed_dose', datetime.date(2016, 1, 26)),
            # three days
            ('directly_observed_dose', datetime.date(2016, 1, 29)),
            (DOSE_MISSED, datetime.date(2016, 1, 31)),
            ('', datetime.date(2016, 1, 30)),  # blank should be treated as unknown
        ])]

        episode = self.create_episode_case(
            adherence_schedule_date_start=datetime.date(2015, 12, 1),
            adherence_schedule_id='schedule1',
            adherence_cases=adherence_cases,
        )
        updater = EpisodeAdherenceUpdate(self.domain, episode)
        updater.date_today_in_india = datetime.date(2016, 1, 31)
        expected = {
            'three_day_score_count_taken': 1,
            'one_week_score_count_taken': 2,
            'two_week_score_count_taken': 3,
            'month_score_count_taken': 4,

            'three_day_unknown_count': 3 - 2,
            'one_week_unknown_count': 7 - 3,
            'two_week_unknown_count': 14 - 4,
            'month_unknown_count': 30 - 6,

            'three_day_missed_count': 1,
            'one_week_missed_count': 1,
            'two_week_missed_count': 1,
            'month_missed_count': 2,

            'three_day_unknown_score': 33.33,
            'one_week_unknown_score': 57.14,
            'two_week_unknown_score': 71.43,
            'month_unknown_score': 80.0,

            'three_day_missed_score': 33.33,
            'one_week_missed_score': 14.29,
            'two_week_missed_score': 7.14,
            'month_missed_score': 6.67,
        }
        actual = updater.update_json()
        self.assert_properties_equal(expected, actual)

        readable_day_names = {
            3: 'three_day',
            7: 'one_week',
            14: 'two_week',
            30: 'month',
        }
        for days, period in readable_day_names.items():
            self.assertEqual(
                days,
                (actual["{}_score_count_taken".format(period)]
                 + actual["{}_unknown_count".format(period)]
                 + actual["{}_missed_count".format(period)])
            )
            self.assertAlmostEqual(
                100,
                (actual["{}_adherence_score".format(period)]
                 + actual["{}_unknown_score".format(period)]
                 + actual["{}_missed_score".format(period)]),
                places=1
            )
