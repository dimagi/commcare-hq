from django.core.management.base import BaseCommand

from corehq.apps.es.forms import FormES
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.motech.repeaters.dbaccessors import (
    get_domains_that_have_repeat_records,
    get_repeat_records_by_payload_id,
    get_repeaters_by_domain,
)
from corehq.motech.repeaters.models import FormRepeater, ShortFormRepeater
from corehq.util.argparse_types import date_type


def create_missing_repeat_records(startdate, enddate, domain=None, detailed_count=False, should_create=False):
    if domain:
        domains_with_repeaters = [domain]
    else:
        domains_with_repeaters = get_domains_that_have_repeat_records()

    missing_form_records_per_domain = create_missing_repeat_records_for_form_repeaters(
        startdate,
        enddate,
        domains_with_repeaters,
        detailed_count,
        should_create
    )

    return missing_form_records_per_domain


def create_missing_repeat_records_for_form_repeaters(startdate,
                                                     enddate,
                                                     domains,
                                                     detailed_count=False,
                                                     should_create=False):
    missing_records_per_domain = {}
    missing_form_ids = set()
    repeaters_with_form_payloads = (
        FormRepeater,
        ShortFormRepeater,
    )

    for domain in domains:

        form_repeaters = [repeater for repeater in get_repeaters_by_domain(domain)
                          if isinstance(repeater, repeaters_with_form_payloads)]
        total_count_missing = 0
        for form in get_forms_in_domain_between_dates(domain, startdate, enddate):
            # results returned from scroll() are making me do this
            form_id = form['form']['meta']['instanceID']
            if detailed_count:
                count_missing = create_missing_repeat_records_for_form(
                    domain, form_repeaters, form_id, should_create)
                total_count_missing += count_missing
            else:
                count_missing = count_missing_repeat_records_for_form(domain, form_repeaters, form_id)
                total_count_missing += count_missing
            if count_missing > 0:
                missing_form_ids.add(form_id)
        if total_count_missing > 0:
            missing_records_per_domain[domain] = total_count_missing

    print(f"Missing records per domain:\n {missing_records_per_domain}")
    return missing_records_per_domain, missing_form_ids


def count_missing_repeat_records_for_form(domain, repeaters, form_id):
    count_missing = 0
    repeat_records = get_repeat_records_by_payload_id(domain, form_id)
    if len(repeat_records) != len(repeaters):
        count_missing += len(repeaters) - len(repeat_records)
    return count_missing


def create_missing_repeat_records_for_form(domain, repeaters, form_id, should_create):
    count_missing = 0
    repeat_records = get_repeat_records_by_payload_id(domain, form_id)
    for repeater in repeaters:
        for repeat_record in repeat_records:
            if repeat_record.repeater_id == repeater.get_id:
                break
        else:
            count_missing += 1
            if should_create:
                # will attempt to send now if registered
                repeater.register(FormAccessors(domain).get_form(form_id))

    return count_missing


def get_forms_in_domain_between_dates(domain, startdate, enddate):
    return FormES().domain(domain).date_range('server_modified_on', gte=startdate, lte=enddate).scroll()


class Command(BaseCommand):
    help = """
    Find case/form submissions/updates that do not have a corresponding repeat record and create a repeat record
    """

    def add_arguments(self, parser):
        parser.add_argument('-s', '--startdate', default="2021-06-19", type=date_type, help='Format YYYY-MM-DD')
        parser.add_argument('-e', '--enddate', default="2021-06-22", type=date_type, help='Format YYYY-MM-DD')
        parser.add_argument('-d', '--domain', default=None, type=str, help='Run on a specific domain')
        parser.add_argument('-dc', '--detailed-count', action='store_true',
                            help='Count missing repeat records using detailed method')
        parser.add_argument('-c', '--create', action='store_true', help='Create missing repeat records')

    def handle(self, startdate, enddate, domain, detailed_count, create, **options):
        create_missing_repeat_records(startdate, enddate, domain, detailed_count, create)
