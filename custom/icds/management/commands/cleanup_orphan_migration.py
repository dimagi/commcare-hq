from __future__ import print_function

from django.core.management import BaseCommand

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL

from dimagi.utils.chunked import chunked

from corehq.util.log import with_progress_bar

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'shard',
            help="File path for log file",
        )
        parser.add_argument(
            'log_file',
            help="File path for log file",
        )

    def handle(self, shard, log_file, **options):
        self.domain = 'icds-cas'
        self.db = shard
        self.case_accessor = CaseAccessors(self.domain)
        failed_updates = []
        with open(log_file, "w") as fh:
            fh.write('--------Successful Form Ids----------\n')
            for orphan_case_chunk in self._get_cases():
                case_tupes = [(case_id, {}, True) for case_id in orphan_case_chunk]
                try:
                    xform, cases = bulk_update_cases(self.domain, case_tupes)
                    fh.write(xform.form_id + '\n')
                except LocalSubmissionError as e:
                    print('submission error')
                    print(unicode(e))
                    failed_updates.extend(orphan_case_chunk)
                except Exception as e:
                    print('unexpected error')
                    print(unicode(e))
                    failed_updates.extend(orphan_case_chunk)
            fh.write('--------Failed Cases--------------\n')
            for case_id in failed_updates:
                fh.write(case_id + '\n')
            fh.write('--------Logging Complete--------------\n')
            print('-------------COMPLETE--------------')


    def _get_cases(self):
        hh_cases = CommCareCaseSQL.objects.using(self.db).filter(domain=self.domain,
                                                                 type='household',
                                                                 closed=True).values_list('case_id', flat=True)
        for cases in chunked(hh_cases, 100):
            related_cases = self.case_accessor.get_reverse_indexed_cases(cases)
            ccs_cases = self.case_accessor.get_reverse_indexed_cases(case.case_id for case in related_cases)
            orphan_cases = {case.case_id for case in related_cases if not case.closed and
                            [c for c in case.cached_indices if c.relationship == 'child']}
            orphan_cases |= {case.case_id for case in ccs_cases if not case.closed and
                            [c for c in case.cached_indices if c.relationship == 'child']}
            yield orphan_cases