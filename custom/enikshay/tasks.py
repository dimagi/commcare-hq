import datetime
from django.utils.dateparse import parse_datetime, parse_date

from .case_utils import get_adherence_cases_between_dates_from_episode


DOMAIN = 'enikshay'
DOSE_TAKEN_INDICATORS = [
    'directly_observed_dose',
    'unobserved_dose',
    'self_administered_dos',
]
DOESES_BY_SCHEDULE_BY_ID = {
    i.schedule_id: i.doses_per_day
    for i in get_lookup_table_items('adherence_schedules')
}
DAILY_SCHEDULE_ID = 'schedule_daily'


def get_open_episode_cases():
    """
    get list of all open 'episode' type cases
    """
    return []


def get_latest_adherence_case_for_episode(episode):
    """
    return open case of type 'adherence' with latest 'adherence_date' property for episode case
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
    return {
        case.adherence_date: parse_date(case.dynamic_case_properties().get('adherence_date'))
        for case in adherence_cases
    }


def update_adherence_properties():
    PURGE_DATE = datetime.today() - 60

    for episode in get_open_episode_cases():
        if episode.adherence_schedule_date_start > PURGE_DATE:
            episode.aggregate_date = episode.adherence_schedule_date_start - 1
            episode.expected = 0
            episode.taken = 0
        else:
            adherence_case = get_latest_adherence_case_for_episode(episode)
            adherence_date = adherence_case.adherence_date
            if adherence_date < PURGE_DATE:
                episode.aggregated_score_date_calculated = adherence_date
            else:
                episode.aggregated_score_date_calculated = PURGE_DATE

            # calculate 'aggregated_score_count_taken'
            adherence_cases = get_adherence_cases_between_dates_from_episode(
                DOMAIN
                episode,
                episode.adherence_schedule_date_start,
                episode.aggregated_score_date_calculated
            )
            adherence_cases_by_date = index_by_date(adherence_cases)
            is_dose_taken_by_date = {}
            for date, cases in adherence_cases_by_date.iteritems():
                is_dose_taken_by_date[date] = any([
                    case.adherence_value in DOSE_TAKEN_INDICATORS
                    for case in cases
                ])
            total_taken_count = is_dose_taken_by_date.values().count(True)
            episode.aggregated_score_count_taken = total_taken_count

            # calculate 'expected' score
            adherence_schedule_id = episode.adherence_schedule_id or DAILY_SCHEDULE_ID
            doses_per_week = DOESES_BY_SCHEDULE_BY_ID[adherence_schedule_id]
            episode.expected = ((aggregated_score_date_calculated - adherence_schedule_date_start) / 7) * doses_per_week
