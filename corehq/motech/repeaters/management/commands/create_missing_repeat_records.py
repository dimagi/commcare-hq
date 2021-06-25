from django.core.management.base import BaseCommand

from corehq.apps.es.forms import FormES
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
    missing_records_per_domain = {}
    for domain in domains_with_repeaters:
        form_ids = get_form_ids_in_domain_between_dates(domain, startdate, enddate)
        repeaters_with_form_payloads = (FormRepeater, ShortFormRepeater)
        form_repeaters = [repeater for repeater in get_repeaters_by_domain(domain)
                          if isinstance(repeater, repeaters_with_form_payloads)]
        count_missing = 0
        for form_id in form_ids:
            if detailed_count:
                count_missing += create_missing_repeat_records_for_form(domain, form_repeaters, form_id,
                                                                        should_create)
            else:
                count_missing += count_missing_repeat_records_for_form(domain, form_repeaters, form_id)
        if count_missing > 0:
            missing_records_per_domain[domain] = count_missing

    print(f"Missing records per domain:\n {missing_records_per_domain}")
    return missing_records_per_domain


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
                forms = FormES().form_ids([form_id]).run().hits
                if len(forms) == 1:
                    # will attempt to send now if registered
                    repeater.register(forms[0])
                else:
                    print(f"Error retrieving form for id {form_id}")

    return count_missing


def get_form_ids_in_domain_between_dates(domain, startdate, enddate):
    return FormES().domain(domain).date_range('server_modified_on', gte=startdate, lte=enddate)\
        .values_list('_id', flat=True)


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
