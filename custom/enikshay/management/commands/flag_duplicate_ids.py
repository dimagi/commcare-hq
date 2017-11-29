from __future__ import absolute_import
from __future__ import print_function
import csv
import datetime
from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar

from custom.enikshay.duplicate_ids import get_cases_with_duplicate_ids


class Command(BaseCommand):
    help = """
    Finds cases with duplicate IDs and marks all but one of each ID as a duplicate
    """
    already_seen = set()

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
        )

    def handle(self, domain, case_type, **options):
        self.domain = domain
        self.case_type = case_type
        commit = options['commit']

        filename = '{}-{}.csv'.format(self.__module__,
                                      datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S'))
        print("Logging actions to {}".format(filename))
        with open(filename, 'w') as f:
            logfile = csv.writer(f)
            logfile.writerow(['case_id', 'marked_as_duplicate'])
            for chunk in chunked(self.get_updates(logfile), 100):
                if commit:
                    bulk_update_cases(self.domain, chunk, self.__module__)

    def get_updates(self, logfile):
        accessor = CaseAccessors(self.domain)
        case_ids = accessor.get_case_ids_in_domain(self.case_type)
        bad_cases = get_cases_with_duplicate_ids(self.domain, self.case_type, case_ids)
        # bad_case_ids = [case['case_id'] for case in bad_cases]
        # for case in with_progress_bar(accessor.iter_cases(bad_case_ids), len(bad_case_ids)):
        for case in with_progress_bar(bad_cases):
            if case['case_id'] in self.already_seen:
                yield (case['case_id'], {'has_duplicate_id': 'yes'}, False)
                logfile.writerow([case['case_id'], True])
            else:
                # Don't mark this one
                self.already_seen.add(case['case_id'])
                logfile.writerow([case['case_id'], False])
