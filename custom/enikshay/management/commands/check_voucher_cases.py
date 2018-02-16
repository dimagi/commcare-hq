from __future__ import absolute_import
from __future__ import print_function
import csv

from django.core.management.base import BaseCommand

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar
from custom.enikshay.case_utils import get_person_case_from_voucher, CASE_TYPE_VOUCHER
from custom.enikshay.const import PERSON_FIRST_NAME, PERSON_LAST_NAME


class Command(BaseCommand):
    help = """
    Check all enikshay voucher cases to see which ones have been set to "paid"
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        accessor = CaseAccessors(domain)
        voucher_ids = accessor.get_case_ids_in_domain(CASE_TYPE_VOUCHER)
        rows = [['voucher_id', 'state', 'comments', 'person_id', 'person_name']]
        for voucher in with_progress_bar(accessor.iter_cases(voucher_ids), len(voucher_ids)):
            if voucher.get_case_property('state') in ('paid', 'rejected'):
                person = get_person_case_from_voucher(domain, voucher.case_id)
                rows.append([
                    voucher.case_id,
                    voucher.get_case_property('state'),
                    voucher.get_case_property('comments'),
                    person.case_id,
                    "{} {}".format(person.get_case_property(PERSON_FIRST_NAME),
                                   person.get_case_property(PERSON_LAST_NAME)),
                ])

        filename = 'voucher_statuses.csv'
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        print ('{} cases have a status of paid or rejected.  Details written to {}'
               .format(len(rows) - 1, filename))
