import csv

from django.core.management import BaseCommand

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar
from custom.enikshay.case_utils import get_open_referral_case_from_person
from custom.enikshay.exceptions import ENikshayException


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('log_file_name')
        parser.add_argument('case_ids', nargs='*')

    def handle(self, domain, log_file_name, case_ids, **options):
        case_accessor = CaseAccessors(domain)
        if not case_ids:
            case_ids = case_accessor.get_case_ids_in_domain(type='person')

        with open(log_file_name, "w") as log_file:
            writer = csv.writer(log_file)

            for person_case_id in with_progress_bar(case_ids):
                try:
                    get_open_referral_case_from_person(domain, person_case_id)
                except ENikshayException:
                    writer.writerow([person_case_id])
