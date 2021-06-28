from django.core.management.base import BaseCommand

from corehq.apps.es import CaseES, FormES
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.motech.repeaters.dbaccessors import (
    get_domains_that_have_repeat_records,
    get_repeat_records_by_payload_id,
    get_repeaters_by_domain,
)
from corehq.motech.repeaters.models import FormRepeater, ShortFormRepeater, CaseRepeater
from corehq.util.argparse_types import date_type

REPEATERS_WITH_FORM_PAYLOADS = (
    FormRepeater,
    ShortFormRepeater,
)

REPEATERS_WITH_CASE_PAYLOADS = (
    CaseRepeater,
)


def obtain_missing_form_repeat_records(startdate,
                                       enddate,
                                       domains,
                                       should_create=False):
    """
    :param startdate: filter out forms with a server_modified_on prior to this date
    :param enddate: filter out forms with a server_modified_on after this date
    :param domains: list of domains to check
    :param should_create: if  True, missing repeat records that are discovered will be registered with the repeater
    :return: a dictionary containing stats about number of missing records, impacted form_ids, percentage missing
    """
    stats_per_domain = {}
    for domain in domains:
        missing_form_ids = set()
        total_missing_count = 0
        total_count = 0
        form_repeaters_in_domain = get_form_repeaters_in_domain(domain)

        for form in get_forms_in_domain_between_dates(domain, startdate, enddate):
            # results returned from scroll() do not include '_id'
            try:
                form_id = form['form']['meta']['instanceID']
            except KeyError:
                print(f"KeyError - instanceID not found for form:\n{form}\n")
                continue
            missing_count, successful_count = obtain_missing_form_repeat_records_in_domain(
                domain, form_repeaters_in_domain, form_id, should_create
            )
            total_missing_count += missing_count
            total_count += missing_count + successful_count
            if missing_count > 0:
                missing_form_ids.add(form_id)

        if total_missing_count > 0:
            stats_per_domain[domain] = {
                'forms': {
                    'missing_count': total_missing_count,
                    'percentage_missing': f'{round((total_missing_count / total_count) * 100, 2)}%',
                }
            }

    return stats_per_domain


def obtain_missing_form_repeat_records_in_domain(domain, repeaters, form_id, should_create):
    missing_count = 0
    successful_count = 0
    repeat_records = get_repeat_records_by_payload_id(domain, form_id)
    found_repeater_ids = [record.repeater_id for record in repeat_records]
    for repeater in repeaters:
        # for each repeater, make sure a repeat record exists
        if repeater.get_id in found_repeater_ids:
            successful_count += 1
        else:
            # did not find a matching repeat record for the payload
            missing_count += 1
            if should_create:
                # will attempt to send now
                repeater.register(FormAccessors(domain).get_form(form_id))

    return missing_count, successful_count


def get_forms_in_domain_between_dates(domain, startdate, enddate):
    return FormES().domain(domain).date_range('server_modified_on', gte=startdate, lte=enddate).scroll()


def obtain_missing_case_repeat_records(startdate,
                                       domains,
                                       should_create=False):
    stats_per_domain = {}
    for domain in domains:
        total_missing_count = 0
        total_count = 0
        case_repeaters_in_domain = get_case_repeaters_in_domain(domain)

        for case in get_cases_in_domain_since_date(domain, startdate):
            case_id = case['case_id']
            missing_count, successful_count = obtain_missing_case_repeat_records_in_domain(
                domain, case_repeaters_in_domain, case_id, should_create
            )
            total_missing_count += missing_count
            total_count += missing_count + successful_count

        if total_missing_count > 0:
            stats_per_domain[domain] = {
                'cases': {
                    'missing_count': total_missing_count,
                    'percentage_missing': f'{round((total_missing_count / total_count) * 100, 2)}%',
                }
            }


def obtain_missing_case_repeat_records_in_domain(domain, repeaters, case_id, should_create):
    missing_count = 0
    successful_count = 0

    return missing_count, successful_count


def get_cases_in_domain_since_date(domain, startdate):
    """
    Can only search for cases modified since a date
    """
    return CaseES().domain(domain).server_modified_range(gte=startdate).scroll()


def get_form_repeaters_in_domain(domain):
    return [repeater for repeater in get_repeaters_by_domain(domain)
            if isinstance(repeater, REPEATERS_WITH_FORM_PAYLOADS)]


def get_case_repeaters_in_domain(domain):
    return [repeater for repeater in get_repeaters_by_domain(domain)
            if isinstance(repeater, REPEATERS_WITH_CASE_PAYLOADS)]


class Command(BaseCommand):
    help = """
    Find case/form submissions/updates that do not have a corresponding repeat record and create a repeat record
    """

    def add_arguments(self, parser):
        parser.add_argument('-s', '--startdate', default="2021-06-19", type=date_type, help='Format YYYY-MM-DD')
        parser.add_argument('-e', '--enddate', default="2021-06-23", type=date_type, help='Format YYYY-MM-DD')
        parser.add_argument('-d', '--domain', default=None, type=str, help='Run on a specific domain')
        parser.add_argument('-c', '--create', action='store_true', help='Create missing repeat records')

    def handle(self, startdate, enddate, domain, create, **options):
        if domain:
            domains_with_repeaters = [domain]
        else:
            domains_with_repeaters = get_domains_that_have_repeat_records()

        _ = obtain_missing_form_repeat_records(startdate, enddate, domains_with_repeaters, create)
