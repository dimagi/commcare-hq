
import csv342 as csv
import copy

from django.core.management import BaseCommand

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from corehq.sql_db.util import get_db_aliases_for_partitioned_query

from dimagi.utils.chunked import chunked
from io import open


class Command(BaseCommand):
    """https://manage.dimagi.com/default.asp?265190

    Some ccs_record cases have evidence of a delivery occurring, but do not
    have an associated delivery form. The implications on the case are that an
    add property is not set and the schedule phase is 2.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            help="File path for csv file",
        )

    def handle(self, csv_file, **options):
        self.domain = 'icds-cas'
        self.case_accessor = CaseAccessors(self.domain)
        with open(csv_file, "w", encoding='utf-8') as csv_file:
            field_names = [
                'case_id', 'owner_id', 'modified_on', 'server_modified_on',
                'add', 'edd', 'ccs_phase', 'num_pnc_visits', 'current_schedule_phase'
            ]

            csv_writer = csv.DictWriter(csv_file, field_names, extrasaction='ignore')
            csv_writer.writeheader()

            for ccs_case in self._get_cases():
                properties = copy.deepcopy(ccs_case.case_json)

                if 'add' in properties:
                    continue

                if properties.get('current_schedule_phase') != '2':
                    continue

                properties.update({
                    'case_id': ccs_case.case_id,
                    'owner_id': ccs_case.owner_id,
                    'modified_on': ccs_case.modified_on,
                    'server_modified_on': ccs_case.server_modified_on
                })
                csv_writer.writerow(properties)

    def _get_cases(self):
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            ccs_record_case_ids = (
                CommCareCaseSQL.objects
                .using(db)
                .filter(domain=self.domain, type='ccs_record', closed=False)
                .values_list('case_id', flat=True)
            )

            for case_ids in chunked(ccs_record_case_ids, 100):
                cases = self.case_accessor.get_cases(list(case_ids))
                for case in cases:
                    yield case
