from collections import defaultdict
import time
from datetime import datetime

from django.core.management.base import BaseCommand
from pip._internal.exceptions import CommandError

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
    UpdateCaseRepeater, RepeatRecord
from corehq.util.argparse_types import date_type

from dimagi.utils.parsing import string_to_utc_datetime

from corehq.util.metrics import metrics_counter

REPEATERS_WITH_FORM_PAYLOADS = (
    FormRepeater,
    ShortFormRepeater,
)

REPEATERS_WITH_CASE_PAYLOADS = (
    CaseRepeater,
)

CASES = 'cases'
FORMS = 'forms'
ALL = 'all'
COMMAND_CHOICES = [CASES, FORMS, ALL]
EXPECTED_REPEAT_RECOUNT_COUNT = 'expected_repeat_record_count'  # Total count of expected repeat records
ACTUAL_REPEAT_RECORD_COUNT = 'actual_repeat_record_count'  # Total count of found repeat records
MISSING_REPEAT_RECORD_COUNT = 'missing_repeat_record_count'  # Total count of missing repeat records
MISSING_CREATE_CASE_RECORD_COUNT = 'missing_create_case_record_count'  # Specifically for CreateCaseRepeater
MISSING_UPDATE_CASE_RECORD_COUNT = 'missing_update_case_record_count'  # Specifically for UpdateCaseRepeater
PCT_MISSING = 'percentage_missing'  # Percentage of repeat records missing relative to expected over the date range
TIME_TO_RUN = 'time_to_run'


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
    for index, domain in enumerate(domains):
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
            pct_missing = f'{round((total_missing_count / total_count) * 100, 2)}%'
            rounded_time = f'{round(time_to_run, 0)} seconds'
            stats_per_domain[domain] = {
                FORMS: {
                    MISSING_REPEAT_RECORD_COUNT: total_missing_count,
                    PCT_MISSING: pct_missing,
                    TIME_TO_RUN: rounded_time,
                }
            }

            print(f'{domain} complete. Found {total_missing_count}" missing repeat records in {rounded_time}. '
                  f'This accounts for {pct_missing} of all repeat records in the specified date range'
                  )

        if index % 10 == 0:
            print(f"{(index+1)}/{len(domains)} domains complete.")

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
            total_missing_all_count = 0
            total_missing_create_count = 0
            total_missing_update_count = 0
            total_count = 0
            case_repeaters_in_domain = get_case_repeaters_in_domain(domain)

            case_ids = [c['_id'] for c in get_case_ids_in_domain_since_date(domain, startdate)]
            cases = CaseAccessors(domain).get_cases(case_ids)
            for case in cases:
                stats_for_case = obtain_missing_case_repeat_records_in_domain(
                    domain, case_repeaters_in_domain, case, startdate, enddate, should_create
                )

                total_missing_all_count += stats_for_case[MISSING_REPEAT_RECORD_COUNT]
                total_missing_create_count += stats_for_case[MISSING_CREATE_CASE_RECORD_COUNT]
                total_missing_update_count += stats_for_case[MISSING_UPDATE_CASE_RECORD_COUNT]
                total_count += stats_for_case[EXPECTED_REPEAT_RECOUNT_COUNT]

            total_missing_count = total_missing_update_count + total_missing_create_count + total_missing_all_count
            t1 = time.time()
            time_to_run = t1 - t0

            if total_missing_count > 0:
                pct_missing = f'{round((total_missing_count / total_count) * 100, 2)}%'
                rounded_time = f'{round(time_to_run, 0)} seconds'
                stats_per_domain[domain] = {
                    CASES: {
                        MISSING_REPEAT_RECORD_COUNT: total_missing_all_count,
                        MISSING_CREATE_CASE_RECORD_COUNT: total_missing_create_count,
                        MISSING_UPDATE_CASE_RECORD_COUNT: total_missing_update_count,
                        PCT_MISSING: pct_missing,
                        TIME_TO_RUN: rounded_time,
                    }
                }
                print(f'{domain} complete. Found {total_missing_count}" missing case repeat records in '
                      f'{rounded_time}. This accounts for {pct_missing} of all case repeat records in the '
                      f'specified date range'
                      )
            if index % 10 == 0:
                print(f"{(index + 1)}/{len(domains)} domains complete.")

        except Exception as e:
            print(f"Encountered error with {domain}: {e}")

    return stats_per_domain


def obtain_missing_case_repeat_records_in_domain(domain, repeaters, case, startdate, enddate, should_create):
    successful_count = missing_all_count = missing_create_count = missing_update_count = 0
    calls_to_register_count = 0

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
            print(f"Missing case {case.get_id} for repeater {repeater.get_id}")
            calls_to_register_count += 1
            if should_create:
                if isinstance(repeater, CreateCaseRepeater) and len(case.transactions) > 1:
                    create_case_repeater_register(repeater, domain, case)
                else:
                    repeater.register(case)

        missing_all_count += missing_count
        if isinstance(repeater, CreateCaseRepeater):
            missing_create_count += missing_count
        elif isinstance(repeater, UpdateCaseRepeater):
            missing_update_count += missing_count

        successful_count += actual_record_count

    return {
        MISSING_REPEAT_RECORD_COUNT: missing_all_count,
        MISSING_CREATE_CASE_RECORD_COUNT: missing_create_count,
        MISSING_UPDATE_CASE_RECORD_COUNT: missing_update_count,
        ACTUAL_REPEAT_RECORD_COUNT: successful_count,
        EXPECTED_REPEAT_RECOUNT_COUNT: missing_all_count + successful_count,
    }


def expected_number_of_repeat_records_fired_for_case(case, repeater, startdate, enddate):
    """
    Based on a case's transactions, and the number of repeat records
    """
    filtered_transactions = []
    if isinstance(repeater, CreateCaseRepeater):
        # to avoid modifying CreateCaseRepeater's allowed_to_forward method
        if create_case_repeater_allowed_to_forward(repeater, case):
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


def create_case_repeater_allowed_to_forward(repeater, case):
    """
    Use this instead of CreateCaseRepeater.allowed_to_forward to get around len(case.transactions) > 1 check
    """
    return repeater._allowed_case_type(case) and repeater._allowed_user(case)


def create_case_repeater_register(repeater, domain, payload):
    """
    Only useful in a very specific edge case for CreateCaseRepeater
    If a CreateCaseRepeater has a missing repeat record, but the case now contains update transactions
    This can be used to properly trigger the missing repeat record.
    """
    if not isinstance(repeater, CreateCaseRepeater):
        print(f"Error - cannot call create_case_repeater_register on repeater type f{type(repeater)}")
        return

    if not create_case_repeater_allowed_to_forward(repeater, payload):
        return

    now = datetime.utcnow()
    repeat_record = RepeatRecord(
        repeater_id=repeater.get_id,
        repeater_type=repeater.doc_type,
        domain=domain,
        registered_on=now,
        next_check=now,
        payload_id=payload.get_id
    )
    metrics_counter('commcare.repeaters.new_record', tags={
        'domain': domain,
        'doc_type': repeater.doc_type
    })
    repeat_record.save()
    repeat_record.attempt_forward_now()
    return repeat_record


class Command(BaseCommand):
    help = """
    Find case/form submissions/updates that do not have a corresponding repeat record and create a repeat record
    """

    def add_arguments(self, parser):
        parser.add_argument('command', choices=COMMAND_CHOICES)
        parser.add_argument('-s', '--startdate', type=date_type, help='Format YYYY-MM-DD')
        parser.add_argument('-e', '--enddate', type=date_type, help='Format YYYY-MM-DD')
        parser.add_argument('-d', '--domain', default=None, type=str, help='Run on a specific domain')
        parser.add_argument('-c', '--create', action='store_true', help='Create missing repeat records')

    def handle(self, command, startdate, enddate, domain, create, **options):
        if not startdate:
            raise CommandError("Must specify a startdate in the format YYYY-MM-DD")

        if not enddate:
            enddate = datetime.utcnow().date()

        if domain:
            domains_to_inspect = [domain]
        else:
            domains_to_inspect = get_domains_that_have_repeat_records()

        if command == 'cases':
            _ = obtain_missing_case_repeat_records(startdate, enddate, domains_to_inspect, create)
        elif command == 'forms':
            _ = obtain_missing_form_repeat_records(startdate, enddate, domains_to_inspect, create)
