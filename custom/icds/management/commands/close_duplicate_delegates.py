from __future__ import print_function

from django.core.management import BaseCommand

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL

from dimagi.utils.chunked import chunked

import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """See https://docs.google.com/document/d/10DCw7kAeuHIYoWaIpe1Ei5VYMFw3UZcmevyMXW05yyg/edit#"""
    help = "Find duplicate tech_issue_delegat cases and close them"

    def add_arguments(self, parser):
        parser.add_argument(
            'log_file',
            help="File path for log file",
        )

    def handle(self, log_file, **options):
        self.domain = 'icds-cas'
        self.case_accessor = CaseAccessors(self.domain)
        failed_updates = []
        with open(log_file, "w") as fh:
            fh.write('--------Successful Form Ids----------\n')
            for delegate_case_ids in chunked(self._get_cases_to_close(), 100):
                case_tupes = [(case_id, {}, True) for case_id in delegate_case_ids]
                try:
                    xform, cases = bulk_update_cases(self.domain, case_tupes, self.__module__)
                    fh.write(xform.form_id + '\n')
                except LocalSubmissionError as e:
                    print('submission error')
                    print(unicode(e))
                    failed_updates.extend(delegate_case_ids)
                except Exception as e:
                    print('unexpected error')
                    print(unicode(e))
                    failed_updates.extend(delegate_case_ids)
            fh.write('--------Failed Cases--------------\n')
            for case_id in failed_updates:
                fh.write(case_id + '\n')
            fh.write('--------Logging Complete--------------\n')
            print('-------------COMPLETE--------------')

    def _get_cases_to_close(self):
        ids = self._get_issue_case_ids()
        for cases in chunked(ids, 100):
            related_cases = self.case_accessor.get_reverse_indexed_cases(list(cases))
            latest_cases = {}
            for case in related_cases:
                if case.type == 'tech_issue_delegate' and not case.closed:
                    tech_issue_case = [c for c in case.cached_indices if c.referenced_type == 'tech_issue'][0]
                    last_case = latest_cases.get(tech_issue_case.referenced_id)
                    if last_case:
                        if case.modified_on < last_case.modified_on:
                            yield case.case_id
                        else:
                            latest_cases[tech_issue_case.referenced_id] = case
                            yield last_case.case_id
                    else:
                        latest_cases[tech_issue_case.referenced_id] = case


    def _get_issue_case_ids(self):
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            print('Starting db: {}'.format(db))
            cases = CommCareCaseSQL.objects.using(db).filter(domain=self.domain, type='tech_issue', closed=False)
            for case in cases:
                yield case.case_id
