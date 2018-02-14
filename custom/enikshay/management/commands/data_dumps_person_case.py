from __future__ import absolute_import
from __future__ import print_function
import csv
from datetime import datetime
from django.core.management.base import BaseCommand
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.es import queries

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    get_all_occurrence_cases_from_person,
)
from custom.enikshay.const import ENROLLED_IN_PRIVATE

DOMAIN = "enikshay"


class Command(BaseCommand):
    """
    data dumps for person cases
    """
    def add_arguments(self, parser):
        parser.add_argument('file_name')
        parser.add_argument('case_type')

    def setup_result_file_name(self):
        result_file_name = "data_dumps_{case_type}_{timestamp}.csv".format(
            case_type=self.case_type,
            timestamp=datetime.now().strftime("%Y-%m-%d--%H-%M-%S"),
        )
        return result_file_name

    def handle(self, case_type, file_name, *args, **options):
        report = {}
        result_file_headers = []
        with open(file_name, 'rU') as input_file:
            reader = csv.DictReader(input_file)
            for row in reader:
                report[row['Column Name']] = {
                    row['Case Reference']: row['Calculation']
                }
                result_file_headers.append(row['Column Name'])

        result_file_name = self.setup_result_file_name()

        with open(result_file_name, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=result_file_headers)
            writer.writeheader()
            for case in get_cases(case_type):
                last_episode_case = None
                case_row = {}
                for column_name, details in report.items():
                    for case_reference, calculation in details.items():
                        if case_reference == "N/A":
                            case_row[column_name] = "N/A"
                        elif case_reference == 'self':
                            if calculation == 'caseid':
                                case_row[column_name] = case.case_id
                            else:
                                case_row[column_name] = case.get_case_property(calculation)
                        elif case_reference == 'last_episode':
                            try:
                                last_episode_case = last_episode_case or get_last_episode(case)
                                case_row[column_name] = last_episode_case.get_case_property(calculation)
                            except Exception as e:
                                case_row[column_name] = str(e)
                        elif case_reference == 'custom':
                            if column_name == 'Reason for "Remove a Person" / Closure':
                                if case.closed:
                                    case_row[column_name] = "closed"
                                elif case.owner_id == "_invalid_":
                                    case_row[column_name] = "removed"
                                elif case.owner_id == '_archive_':
                                    case_row[column_name] = "archived"
                                else:
                                    case_row[column_name] = "active"
                            elif column_name == 'Latest Episode - Date Closed (If any)':
                                try:
                                    last_episode_case = last_episode_case or get_last_episode(case)
                                    if last_episode_case.closed:
                                        case_row[column_name] = "closed"
                                    else:
                                        case_row[column_name] = "open"
                                except Exception as e:
                                    case_row[column_name] = str(e)
                writer.writerow(case_row)


def get_cases(case_type):
    case_accessor = CaseAccessors(DOMAIN)
    for case_id in get_case_ids(case_type):
        yield case_accessor.get_case(case_id)


def get_case_ids(case_type):
    return (CaseSearchES()
            .domain(DOMAIN)
            .case_type(case_type)
            .case_property_query(ENROLLED_IN_PRIVATE, 'true', clause=queries.MUST_NOT)
            .case_property_query("dataset", 'real')
            .get_ids()[0:10])


def get_recently_closed_case(all_cases):
    recently_closed_case = None
    recently_closed_time = None
    for case in all_cases:
        case_closed_time = case.closed_on
        if case_closed_time:
            if recently_closed_time is None:
                recently_closed_time = case_closed_time
                recently_closed_case = case
            elif recently_closed_time and recently_closed_time < case_closed_time:
                recently_closed_time = case_closed_time
                recently_closed_case = case
            elif recently_closed_time and recently_closed_time == case_closed_time:
                raise Exception("This looks like a super edge case that can be looked at. "
                                "Not blocking as of now. Case id: {case_id}".format(case_id=case.case_id))

    return recently_closed_case


def get_all_episode_cases_from_person(domain, person_case_id):
    occurrence_cases = get_all_occurrence_cases_from_person(domain, person_case_id)
    return [
        case for case in CaseAccessors(domain).get_reverse_indexed_cases(
            [c.case_id for c in occurrence_cases], case_types=[CASE_TYPE_EPISODE])
    ]


def get_last_episode(person_case):
    episode_cases = get_all_episode_cases_from_person(person_case.domain, person_case.case_id)
    open_episode_cases = [
        episode_case for episode_case in episode_cases
        if not episode_case.closed
    ]
    active_open_episode_cases = [
        episode_case for episode_case in open_episode_cases
        if episode_case.get_case_property('is_active') == 'yes'
    ]
    if len(active_open_episode_cases) == 1:
        return active_open_episode_cases[0]
    elif len(active_open_episode_cases) > 1:
        raise Exception("Multiple active open episode cases found for %s" % person_case.case_id)
    elif len(open_episode_cases) > 0:
        if len(open_episode_cases) == 1:
            return open_episode_cases[0]
        elif len(open_episode_cases) > 1:
            raise Exception("Multiple open episode cases found for %s" % person_case.case_id)
    else:
        return get_recently_closed_case(episode_cases)
