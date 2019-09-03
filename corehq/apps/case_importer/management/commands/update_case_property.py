from django.core.management import BaseCommand

import csv

from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class Command(BaseCommand):
    help = """updates a single case property for a list of cases in a two column csv format.
    the first column must be the case_ids and the header of the second column must be the case
    property you are changing. arguments are <domain> <path_to_input_csv> <path_to_logfile>"""

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('infile')
        parser.add_argument('logfile')

    def handle(self, domain, infile, logfile, *args, **options):
        self.domain = domain
        self.case_accessor = CaseAccessors(self.domain)
        with open(infile, 'r', encoding='utf-8') as f, open(logfile, 'w', encoding='utf-8') as log:
            reader = csv.reader(f)
            _, case_prop_name = next(reader)
            log.write('--------Successful Form Ids----------\n')
            failed_updates = []
            for rows in chunked(reader, 100):
                updates = [(case_id, {case_prop_name: prop}, False) for case_id, prop in rows]
                try:
                    xform, cases = bulk_update_cases(
                        self.domain, updates, self.__module__)
                    log.write(xform.form_id + '\n')
                except Exception as e:
                    print('error')
                    print(str(e))
                    failed_updates.extend(u[0] for u in updates)
            log.write('--------Failed Cases--------------\n')
            for case_id in failed_updates:
                log.write(case_id + '\n')
            log.write('--------Logging Complete--------------\n')
            print('-------------COMPLETE--------------')
