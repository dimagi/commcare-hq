from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
import csv

from django.core.management import BaseCommand

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from dimagi.utils.chunked import chunked
import six


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
        with open(infile, 'r') as f, open(logfile, 'w') as log:
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
                    print(six.text_type(e))
                    failed_updates.extend(u[0] for u in updates)
            log.write('--------Failed Cases--------------\n')
            for case_id in failed_updates:
                log.write(case_id + '\n')
            log.write('--------Logging Complete--------------\n')
            print('-------------COMPLETE--------------')
