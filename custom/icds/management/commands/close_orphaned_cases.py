
from django.core.management import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.apps.es import CaseES
from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL, CommCareCaseIndexSQL
from corehq.util.log import with_progress_bar
import six


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            help="File path for log file",
        )
        parser.add_argument(
            'log_file',
            help="File path for log file",
        )

    def handle(self, domain, log_file, **options):
        total_cases = CaseES().domain(domain).case_type('household').is_closed().count()
        self.case_accessor = CaseAccessors(domain)
        failed_updates = []
        with open(log_file, "w", encoding='utf-8') as fh:
            fh.write('--------Successful Form Ids----------\n')
            for cases in chunked(with_progress_bar(self._get_cases_to_process(domain), total_cases), 100):
                related_cases = self._get_related_cases(cases)
                case_tupes = [(case_id, {}, True) for case_id in related_cases]
                try:
                    xform, cases = bulk_update_cases(
                        domain, case_tupes, self.__module__)
                    fh.write(xform.form_id + '\n')
                except LocalSubmissionError as e:
                    print('submission error')
                    print(six.text_type(e))
                    failed_updates.extend(related_cases)
                except Exception as e:
                    print('unexpected error')
                    print(six.text_type(e))
                    failed_updates.extend(related_cases)
            fh.write('--------Failed Cases--------------\n')
            for case_id in failed_updates:
                fh.write(case_id)
            print('-------------COMPLETE--------------')

    def _get_cases_to_process(self, domain):
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            cases = CommCareCaseSQL.objects.using(db).filter(domain=domain, type='household', closed=True)
            for case in cases:
                yield case.case_id

    def _get_related_cases(self, cases):
        related_cases = {case.case_id for case in self.case_accessor.get_all_reverse_indices_info(list(cases))
                         if case.relationship == CommCareCaseIndexSQL.CHILD}
        related_cases |= {case.case_id for case in
                          self.case_accessor.get_all_reverse_indices_info(list(related_cases))
                         if case.relationship == CommCareCaseIndexSQL.CHILD}
        return related_cases
