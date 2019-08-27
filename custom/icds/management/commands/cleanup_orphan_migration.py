
from django.core.management import BaseCommand

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL

from dimagi.utils.chunked import chunked
import six


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'shard',
            help="db shard to query against",
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
        with open(log_file, "w", encoding='utf-8') as fh:
            fh.write('--------Successful Form Ids----------\n')
            chunk_num = 1
            for orphan_case_chunk in self._get_cases():
                print('Currently on chunk {}'.format(chunk_num))
                case_tupes = [(case_id, {}, True) for case_id in orphan_case_chunk]
                try:
                    xform, cases = bulk_update_cases(
                        self.domain, case_tupes, self.__module__)
                    fh.write(xform.form_id + '\n')
                except LocalSubmissionError as e:
                    print('submission error')
                    print(six.text_type(e))
                    failed_updates.extend(orphan_case_chunk)
                except Exception as e:
                    print('unexpected error')
                    print(six.text_type(e))
                    failed_updates.extend(orphan_case_chunk)
                chunk_num += 1
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
            related_cases = self.case_accessor.get_reverse_indexed_cases(list(cases))
            ccs_cases = self.case_accessor.get_reverse_indexed_cases([case.case_id for case in related_cases])
            orphan_cases = {case.case_id for case in related_cases if not case.closed and
                            [c for c in case.cached_indices if c.relationship == 'child']}
            orphan_cases |= {case.case_id for case in ccs_cases if not case.closed and
                            [c for c in case.cached_indices if c.relationship == 'child']}
            yield orphan_cases
