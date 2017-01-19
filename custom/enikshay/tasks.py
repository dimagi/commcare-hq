import datetime
from collections import defaultdict
from django.utils.dateparse import parse_datetime, parse_date

from .case_utils import get_adherence_cases_between_dates_from_episode
from corehq.apps.fixtures.models import FixtureDataItem


DOMAIN = 'enikshay'
DOSE_TAKEN_INDICATORS = [
    'directly_observed_dose',
    'unobserved_dose',
    'self_administered_dose',
]
DAILY_SCHEDULE_FIXTURE_NAME = 'adherence_schedules'
SCHEDULE_ID_FIXTURE = 'id'
CASE_TYPE_EPISODE = 'episode'


def get_doses_data():
    # return 'doses_per_week' by 'schedule_id' from the Fixture data
    fixtures = FixtureDataItem.get_indexed_items(DOMAIN, DAILY_SCHEDULE_FIXTURE_NAME, SCHEDULE_ID_FIXTURE)
    return dict((k, int(fixture['doses_per_week'])) for k, fixture in fixtures.items())


def get_open_episode_cases():
    """
    get list of all open 'episode' type cases
    """
    case_accessor = CaseAccessors(DOMAIN)
    case_ids = get_open_case_ids_in_domain_by_type(CASE_TYPE_EPISODE)
    return case_accessor.iter_cases(case_ids)


def get_latest_adherence_case_for_episode(episode):
    """
    return open case of type 'adherence' reversed-indexed to episode and
        with latest 'adherence_date' property
    """
    case_accessor = CaseAccessors(DOMAIN)
    indexed_cases = case_accessor.get_reverse_indexed_cases([episode.case_id])
    latest_date = 0
    latest_case = None
    for case in indexed_cases:
        adherence_date = parse_datetime(case.dynamic_case_properties().get('adherence_date'))
        if (not case.closed and
           case.type == CASE_TYPE_ADHERENCE and
           adherence_date > latest_date):
            latest_date = adherence_date
            latest_case = adherence_date
    return latest_case


def index_by_adherence_date(adherence_cases):
    """
    inde
    """
    by_date = defaultdict(list)
    for case in adherence_cases:
        adherance_date = parse_date(case.dynamic_case_properties().get('adherence_date'))
        by_date[adherance_date].append(case)
    return by_date


def get_adherence_schedule_date_start(episode_case):
    return parse_datetime(case.dynamic_case_properties().get('adherence_schedule_date_start'))


def update_adherence_properties():
    # edge cases around datetime
    PURGE_DATE = datetime.datetime.today() - datetime.timedelta(days=60)

    for episode in get_open_episode_cases():
        adherence_schedule_date_start = get_adherence_schedule_date_start(episode)
        # Todo: What if adherence_schedule_date_start is None
        if adherence_schedule_date_start > PURGE_DATE:
            episode.aggregated_score_date_calculated = adherence_schedule_date_start - 1
            episode.expected = 0
            episode.aggregated_score_count_taken = 0
        else:
            adherence_case = get_latest_adherence_case_for_episode(episode)
            # ToDo: what if adherence_case doesn't exist?
            adherence_date = parse_datetime(adherence_case.dynamic_case_properties().get('adherence_date'))
            if adherence_date < PURGE_DATE:
                episode.aggregated_score_date_calculated = adherence_date
            else:
                episode.aggregated_score_date_calculated = PURGE_DATE

            # calculate 'aggregated_score_count_taken'
            adherence_cases = get_adherence_cases_between_dates_from_episode(
                DOMAIN
                episode,
                adherence_schedule_date_start,
                episode.aggregated_score_date_calculated
            )
            adherence_cases_by_date = index_by_adherence_date(adherence_cases)
            is_dose_taken_by_date = {}
            for date, cases in adherence_cases_by_date.iteritems():
                is_dose_taken_by_date[date] = any([
                    case.adherence_value in DOSE_TAKEN_INDICATORS
                    for case in cases
                ])
            total_taken_count = is_dose_taken_by_date.values().count(True)
            episode.aggregated_score_count_taken = total_taken_count

            # calculate 'expected' score
            dose_data = get_doses_data()
            adherence_schedule_id = episode.adherence_schedule_id or DAILY_SCHEDULE_ID
            # Todo: what if 'adherence_schedule_id' doesn't exist in fixtures
            doses_per_week = dose_data.get(adherence_schedule_id)
            episode.expected = ((aggregated_score_date_calculated - adherence_schedule_date_start) / 7) * doses_per_week
