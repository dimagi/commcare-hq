
import csv
from datetime import datetime
from corehq.form_processor.models.cases import CommCareCase
from corehq.util.argparse_types import date_type
from django.core.management.base import BaseCommand


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--domains', nargs="*",
            help='Domains to check, will include enterprise-controlled child domains.'
        )
        parser.add_argument('--start', type=date_type, help='Start date (inclusive)')
        parser.add_argument('--end', type=date_type, help='End date (inclusive)')

    def handle(self, **options):
        filename = "deleted_cases_pull_{}.csv".format(datetime.utcnow().strftime("%Y-%m-%d_%H.%M.%S"))
        domains = options['domains']

        with open(filename, 'w', encoding='utf-8') as csv_file:
            field_names = ['domain', 'case_id', 'case_type', 'date_of_deletion']
            csv_writer = csv.DictWriter(csv_file, field_names)
            csv_writer.writeheader()
            for domain in domains:
                deleted_case_ids = CommCareCase.objects.get_deleted_case_ids_in_domain(domain)
                deleted_cases = CommCareCase.objects.get_cases(deleted_case_ids)
                for case in deleted_cases:
                    row = {
                        'domain': domain,
                        'case_id': case.case_id,
                        'case_type': case.type,
                        'date_of_deletion': case.deleted_on
                    }
                    csv_writer.writerow(row)
            print(f"Result saved to {filename}")
