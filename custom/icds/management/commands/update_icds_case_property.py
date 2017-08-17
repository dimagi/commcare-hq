from __future__ import print_function

import csv

from django.core.management import BaseCommand

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from dimagi.utils.chunked import chunked


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_arugment('infile')
        parser.add_arugment('logfile')

    def handle(self, infile, logfile, *args, **options):
        self.domain = 'icds-cas'
        self.case_accessor = CaseAccessors(self.domain)
        with open(infile, 'r') as f, open(logfile, 'w') as log:
            reader = csv.reader(f)
            _, case_prop_name = reader.next()
            log.write('--------Successful Form Ids----------\n')
            failed_updates = []
            for rows in chunked(reader, 100):
                updates = [(case_id, {case_prop_name: prop}, False) for case_id, prop in rows]
                try:
                    xform, cases = bulk_update_cases(self.domain, updates)
                    log.write(xform.form_id + '\n')
                except Exception as e:
                    print('error')
                    print(unicode(e))
                    failed_updates.extend(u[0] for u in updates)
            log.write('--------Failed Cases--------------\n')
            for case_id in failed_updates:
                log.write(case_id + '\n')
            log.write('--------Logging Complete--------------\n')
            print('-------------COMPLETE--------------')
