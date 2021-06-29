
from django.core.management.base import BaseCommand

from corehq.apps.es import CaseES, FormES
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.motech.dhis2.repeaters import Dhis2EntityRepeater
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.motech.repeaters.dbaccessors import (
    get_domains_that_have_repeat_records,
    get_repeat_records_by_payload_id,
    get_repeaters_by_domain,
)
from corehq.motech.repeaters.models import FormRepeater, ShortFormRepeater, CaseRepeater, CreateCaseRepeater, \
    UpdateCaseRepeater
from corehq.util.argparse_types import date_type

from dimagi.utils.parsing import string_to_utc_datetime

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
        total_missing_count = 0
        total_count = 0
        form_repeaters_in_domain = get_form_repeaters_in_domain(domain)

        form_ids = [f['_id'] for f in get_form_ids_in_domain_between_dates(domain, startdate, enddate)]
        forms = FormAccessors(domain).get_forms(form_ids)
        for form in forms:
            missing_count, successful_count = obtain_missing_form_repeat_records_in_domain(
                domain, form_repeaters_in_domain, form, should_create
            )
            total_missing_count += missing_count
            total_count += missing_count + successful_count

        if total_missing_count > 0:
            stats_per_domain[domain] = {
                'forms': {
                    'missing_count': total_missing_count,
                    'percentage_missing': f'{round((total_missing_count / total_count) * 100, 2)}%',
                }
            }

    return stats_per_domain


def obtain_missing_form_repeat_records_in_domain(domain, repeaters, form, should_create):
    if form.is_duplicate:
        return 0, 0

    missing_count = 0
    successful_count = 0
    repeat_records = get_repeat_records_by_payload_id(domain, form.get_id)
    triggered_repeater_ids = [record.repeater_id for record in repeat_records]
    for repeater in repeaters:
        if not repeater.allowed_to_forward(form):
            continue

        if repeater.get_id in triggered_repeater_ids:
            successful_count += 1
        else:
            missing_count += 1
            if should_create:
                # will attempt to send now
                repeater.register(form)

    return missing_count, successful_count


def get_form_ids_in_domain_between_dates(domain, startdate, enddate):
    return FormES(es_instance_alias='export').domain(domain)\
        .date_range('server_modified_on', gte=startdate, lte=enddate).source(['_id']).run().hits


def obtain_missing_case_repeat_records(startdate, enddate, domains):
    stats_per_domain = {}
    for domain in domains:
        total_missing_count = 0
        total_count = 0
        case_repeaters_in_domain = get_case_repeaters_in_domain(domain)

        case_ids = [c['_id'] for c in get_case_ids_in_domain_since_date(domain, startdate)]
        cases = CaseAccessors(domain).get_cases(case_ids)
        for case in cases:
            missing_count, successful_count = obtain_missing_case_repeat_records_in_domain(
                domain, case_repeaters_in_domain, case, startdate, enddate
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

    return stats_per_domain


def obtain_missing_case_repeat_records_in_domain(domain, repeaters, case, startdate, enddate):
    successful_count = 0
    missing_count = 0

    repeat_records = get_repeat_records_by_payload_id(domain, case.get_id)
    records_in_daterange = [record for record in repeat_records
                            if startdate <= record.registered_on.date() <= enddate]

    triggered_repeater_ids_and_counts = {}
    for record in records_in_daterange:
        current_count = triggered_repeater_ids_and_counts.get(record.repeater_id, 0)
        if current_count > 0:
            triggered_repeater_ids_and_counts[record.repeater_id] += 1
        else:
            triggered_repeater_ids_and_counts[record.repeater_id] = 1

    for repeater in repeaters:
        repeaters_to_ignore = (Dhis2EntityRepeater, OpenmrsRepeater)
        if isinstance(repeater, repeaters_to_ignore):
            # not dealing with these right now
            continue

        if repeater.started_at.date() >= enddate:
            # don't count a repeater that was created after the window we care about
            continue
        expected_record_count = number_of_repeat_records_triggered_by_case(case, repeater, startdate, enddate)
        actual_record_count = triggered_repeater_ids_and_counts.get(repeater.get_id, 0)

        # worry about specifying create vs update vs normal later
        temp_missing_count = expected_record_count - actual_record_count
        missing_count += temp_missing_count if temp_missing_count > 0 else 0
        successful_count += actual_record_count

    return missing_count, successful_count


def number_of_repeat_records_triggered_by_case(case, repeater, startdate, enddate):
    filtered_transactions = []
    if isinstance(repeater, CreateCaseRepeater):
        # to avoid modifying CreateCaseRepeater's allowed_to_forward method
        if repeater._allowed_case_type(case) and repeater._allowed_user(case):
            filtered_transactions = case.transactions[0:1]
    elif isinstance(repeater, UpdateCaseRepeater):
        if repeater.allowed_to_forward(case):
            filtered_transactions = case.transactions[1:]
    else:
        if repeater.allowed_to_forward(case):
            filtered_transactions = case.transactions

    transactions_in_daterange = [transaction for transaction in filtered_transactions
                                 if startdate <= get_transaction_date(transaction) <= enddate]

    return len(transactions_in_daterange)


def get_transaction_date(transaction):
    return string_to_utc_datetime(transaction.server_date).date()


def get_case_ids_in_domain_since_date(domain, startdate):
    """
    Can only search for cases modified since a date
    """
    return CaseES(es_instance_alias='export').domain(domain).server_modified_range(gte=startdate)\
        .source(['_id']).run().hits


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
