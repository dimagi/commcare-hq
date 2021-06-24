from datetime import datetime

from django.core.management.base import BaseCommand

from corehq.apps.es.forms import FormES
from corehq.motech.repeaters.dbaccessors import (
    get_domains_that_have_repeat_records,
    get_repeaters_by_domain, get_repeat_records_by_payload_id,
)


def create_missing_repeat_records():
    startdate = datetime(2021, 6, 19)
    enddate = datetime(2021, 6, 21)
    domains_with_repeaters = get_domains_that_have_repeat_records()
    num_of_missing_records = 0
    for domain in domains_with_repeaters:
        forms = get_forms_in_domain_between_dates(domain, startdate, enddate)
        repeaters = get_repeaters_by_domain(domain)
        for form in forms:
            count_missing = check_repeat_records_for_submission(domain, repeaters, form, create=False)
            num_of_missing_records += count_missing

    print(f"{num_of_missing_records} repeat records are missing.")


def check_repeat_records_for_submission(domain, repeaters, form, create=False):
    count_missing = 0
    repeat_records = get_repeat_records_by_payload_id(domain, form['_id'])
    for repeater in repeaters:
        found = False
        for repeat_record in repeat_records:
            if repeat_record.repeater_id == repeater.get_id:
                found = True
                break

        if not found:
            count_missing += 1
            # print(f"COULD NOT FIND PAYLOAD {form.form_id} FOR REPEATER {repeater.get_id}.\nSHOULD CREATE")
            if create:
                # will attempt to send now if registered
                repeater.register(form)

    return count_missing


def get_forms_in_domain_between_dates(domain, startdate, enddate):
    return FormES().domain(domain).date_range('server_modified_on', gte=startdate, lte=enddate).run().hits


class Command(BaseCommand):
    help = """
    Find case/form submissions/updates that do not have a corresponding repeat record and create a repeat record
    """

    def handle(self, *args, **options):
        create_missing_repeat_records()
