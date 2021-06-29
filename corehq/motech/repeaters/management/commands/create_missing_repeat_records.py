from collections import defaultdict
import time

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

CASES = 'cases'
FORMS = 'forms'
TIME_TO_RUN = 'time_to_run'
TOTAL_COUNT = 'total_count'
SUCCESSFUL_COUNT = 'successful_count'
MISSING_COUNT = 'missing_count'
MISSING_ALL_COUNT = 'missing_all_count'  # CaseRepeater
MISSING_CREATE_COUNT = 'missing_create_count'  # CreateCaseRepeater
MISSING_UPDATE_COUNT = 'missing_update_count'  # UpdateCaseRepeater
CALLS_TO_REGISTER_COUNT = 'calls_to_register_count'
PCT_MISSING = 'percentage_missing'
CAN_REGISTER_CREATE = 'can_register_create'
CANNOT_REGISTER_CREATE = 'cannot_register_create'


def obtain_missing_form_repeat_records(startdate,
                                       enddate,
                                       domains,
                                       should_create=False):
    """
    :param startdate: search for missing form repeat records after this date
    :param enddate: search for missing form repeat records before this date
    :param domains: list of domains to check
    :param should_create: if  True, missing repeat records that are discovered will be registered with the repeater
    :return: a dictionary containing stats about the missing repeat records and metadata
    """
    stats_per_domain = {}
    for domain in domains:
        t0 = time.time()
        total_missing_count = 0
        total_count = 0
        form_repeaters_in_domain = get_form_repeaters_in_domain(domain)

        form_ids = [f['_id'] for f in get_form_ids_in_domain_between_dates(domain, startdate, enddate)]
        forms = FormAccessors(domain).get_forms(form_ids)
        for form in forms:
            missing_count, successful_count = obtain_missing_form_repeat_records_in_domain(
                domain, form_repeaters_in_domain, form, enddate, should_create
            )
            total_missing_count += missing_count
            total_count += missing_count + successful_count

        t1 = time.time()
        time_to_run = t1 - t0
        if total_missing_count > 0:
            stats_per_domain[domain] = {
                FORMS: {
                    MISSING_COUNT: total_missing_count,
                    PCT_MISSING: f'{round((total_missing_count / total_count) * 100, 2)}%',
                    TIME_TO_RUN: f'{round(time_to_run, 2)} seconds',
                }
            }

    return stats_per_domain


def obtain_missing_form_repeat_records_in_domain(domain, repeaters, form, enddate, should_create):
    if form.is_duplicate:
        return 0, 0

    missing_count = 0
    successful_count = 0
    repeat_records = get_repeat_records_by_payload_id(domain, form.get_id)
    triggered_repeater_ids = [record.repeater_id for record in repeat_records]
    for repeater in repeaters:
        if not repeater.allowed_to_forward(form):
            continue

        if repeater.started_at.date() >= enddate:
            # don't count a repeater that was created after the window we care about
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


def obtain_missing_case_repeat_records(startdate,
                                       enddate,
                                       domains,
                                       should_create=False):
    """
    :param startdate: search for missing case repeat records after this date
    :param enddate: search for missing case repeat records before this date
    :param domains: list of domains to check
    :param should_create: if  True, missing repeat records that are discovered will be registered with the repeater
    :return: a dictionary containing stats about the missing repeat records and metadata
    """
    stats_per_domain = {}
    for index, domain in enumerate(domains):
        t0 = time.time()
        try:
            total_register_count = 0
            total_missing_all_count = 0
            total_missing_create_count = 0
            total_missing_update_count = 0
            total_count = 0
            total_can_call_register_on_create = total_cannot_call_register_on_create = 0
            case_repeaters_in_domain = get_case_repeaters_in_domain(domain)

            case_ids = [c['_id'] for c in get_case_ids_in_domain_since_date(domain, startdate)]
            cases = CaseAccessors(domain).get_cases(case_ids)
            for case in cases:
                stats_for_case = obtain_missing_case_repeat_records_in_domain(
                    domain, case_repeaters_in_domain, case, startdate, enddate, should_create
                )

                total_register_count += stats_for_case[CALLS_TO_REGISTER_COUNT]
                total_missing_create_count += stats_for_case[MISSING_CREATE_COUNT]
                total_missing_update_count += stats_for_case[MISSING_UPDATE_COUNT]
                total_missing_all_count += stats_for_case[MISSING_ALL_COUNT]
                total_count += stats_for_case[TOTAL_COUNT]
                total_can_call_register_on_create += stats_for_case[CAN_REGISTER_CREATE]
                total_cannot_call_register_on_create += stats_for_case[CANNOT_REGISTER_CREATE]

            total_missing_count = total_missing_update_count + total_missing_create_count + total_missing_all_count
            t1 = time.time()
            time_to_run = t1 - t0

            if total_missing_count > 0:
                stats_per_domain[domain] = {
                    CASES: {
                        CALLS_TO_REGISTER_COUNT: total_register_count,
                        MISSING_COUNT: total_missing_count,
                        MISSING_ALL_COUNT: total_missing_all_count,
                        MISSING_CREATE_COUNT: total_missing_create_count,
                        MISSING_UPDATE_COUNT: total_missing_update_count,
                        PCT_MISSING: f'{round((total_missing_count / total_count) * 100, 2)}%',
                        TIME_TO_RUN: f'{round(time_to_run, 2)} seconds',
                        CAN_REGISTER_CREATE: total_can_call_register_on_create,
                        CANNOT_REGISTER_CREATE: total_cannot_call_register_on_create,
                    }
                }
                print(f'{domain} complete!\n{stats_per_domain[domain][CASES]}')

            print(f"{len(domains) - (index + 1)} domains left")

        except Exception as e:
            print(f"Encountered error with {domain}: {e}")

    return stats_per_domain


def obtain_missing_case_repeat_records_in_domain(domain, repeaters, case, startdate, enddate, should_create):
    successful_count = missing_all_count = missing_create_count = missing_update_count = 0
    calls_to_register_count = create_calls_to_register_count = cannot_call_register_on_create = 0

    repeat_records = get_repeat_records_by_payload_id(domain, case.get_id)
    # grab repeat records that were registered during the outage
    records_during_outage = [record for record in repeat_records
                             if startdate <= record.registered_on.date() <= enddate]
    fired_repeater_ids_and_counts_during_outage = defaultdict(int)
    for record in records_during_outage:
        fired_repeater_ids_and_counts_during_outage[record.repeater_id] += 1

    # grab repeat records that were registered after the outage
    records_after_outage = [record for record in repeat_records if record.registered_on.date() >= enddate]
    fired_repeater_ids_and_counts_after_outage = defaultdict(int)
    for record in records_after_outage:
        fired_repeater_ids_and_counts_after_outage[record.repeater_id] += 1

    for repeater in repeaters:
        repeaters_to_ignore = (Dhis2EntityRepeater, OpenmrsRepeater)
        if isinstance(repeater, repeaters_to_ignore):
            # not dealing with these right now because their expected payload appears to be a form?
            continue

        if repeater.started_at.date() >= enddate:
            # don't count a repeater that was created after the outage
            continue

        if fired_repeater_ids_and_counts_after_outage.get(repeater.get_id, 0) > 0:
            # no need to trigger a repeater if it has fired since the outage ended
            continue

        expected_record_count = expected_number_of_repeat_records_fired_for_case(
            case, repeater, startdate, enddate
        )
        actual_record_count = fired_repeater_ids_and_counts_during_outage.get(repeater.get_id, 0)

        missing_count = expected_record_count - actual_record_count
        if missing_count < 0:
            print(f"""
                ERROR: negative count\nExpected: {expected_record_count} Actual: {actual_record_count}
                Case: {case.get_id}
            """)
            missing_count = 0

        if missing_count > 0:
            calls_to_register_count += 1
            if isinstance(repeater, CreateCaseRepeater):
                if len(case.transactions) > 1:
                    cannot_call_register_on_create += 1
                    print(f"""
                        Cannot trigger create case repeat record for repeater {repeater.get_id} and case
                        {case.get_id}
                    """)
                else:
                    create_calls_to_register_count += 1
            elif should_create:
                repeater.register(case)

        # just using this to count up each type
        if isinstance(repeater, CreateCaseRepeater):
            missing_create_count += missing_count
        elif isinstance(repeater, UpdateCaseRepeater):
            missing_update_count += missing_count
        else:
            missing_all_count += missing_count

        successful_count += actual_record_count

    return {
        CALLS_TO_REGISTER_COUNT: calls_to_register_count,
        MISSING_CREATE_COUNT: missing_create_count,
        MISSING_UPDATE_COUNT: missing_update_count,
        MISSING_ALL_COUNT: missing_all_count,
        SUCCESSFUL_COUNT: successful_count,
        TOTAL_COUNT: missing_create_count + missing_update_count + missing_all_count + successful_count,
        CAN_REGISTER_CREATE: create_calls_to_register_count,
        CANNOT_REGISTER_CREATE: cannot_call_register_on_create,
    }


def expected_number_of_repeat_records_fired_for_case(case, repeater, startdate, enddate):
    """
    Based on a case's transactions, and the number of repeat records
    """
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
