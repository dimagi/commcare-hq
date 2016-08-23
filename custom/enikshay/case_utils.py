import pytz
from django.utils.dateparse import parse_datetime

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.exceptions import ENikshayCaseNotFound


def get_open_episode_case_from_person(domain, person_case_id):
    """
    Gets the first open 'episode' case for the person

    Assumes the following case structure:
    Person <--ext-- Occurrence <--ext-- Episode

    """
    case_accessor = CaseAccessors(domain)
    occurrence_cases = case_accessor.get_reverse_indexed_cases([person_case_id])
    open_occurrence_cases = [case for case in occurrence_cases
                             if not case.closed and case.type == "occurrence"]
    if not open_occurrence_cases:
        raise ENikshayCaseNotFound(
            "Person with id: {} exists but has no open occurence cases".format(person_case_id)
        )
    occurence_case = open_occurrence_cases[0]
    episode_cases = case_accessor.get_reverse_indexed_cases([occurence_case.case_id])
    open_episode_cases = [case for case in episode_cases
                          if not case.closed and case.type == "episode" and
                          case.dynamic_case_properties().get('episode_type') == "confirmed_tb"]
    if open_episode_cases:
        return open_episode_cases[0]
    else:
        raise ENikshayCaseNotFound(
            "Person with id: {} exists but has no open episode cases".format(person_case_id)
        )


def get_adherence_cases_between_dates(domain, person_case_id, start_date, end_date):
    case_accessor = CaseAccessors(domain)
    episode = get_open_episode_case_from_person(domain, person_case_id)
    indexed_cases = case_accessor.get_reverse_indexed_cases([episode.case_id])
    open_pertinent_adherence_cases = [
        case for case in indexed_cases
        if not case.closed and case.type == "adherence" and
        (start_date.astimezone(pytz.UTC) <=
         parse_datetime(case.dynamic_case_properties().get('adherence_date')).astimezone(pytz.UTC) <=
         end_date.astimezone(pytz.UTC))
    ]

    return open_pertinent_adherence_cases
