from __future__ import absolute_import
from __future__ import unicode_literals
import redis
from casexml.apps.case.exceptions import IllegalCaseId
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.backends.sql.update_strategy import SqlCaseUpdateStrategy
from corehq.form_processor.casedb_base import AbstractCaseDbCache
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCaseSQL
from corehq import toggles

class CaseDbCacheSQL(AbstractCaseDbCache):
    case_model_classes = (CommCareCaseSQL,)
    case_update_strategy = SqlCaseUpdateStrategy

    def __init__(self, domain=None, strip_history=False, deleted_ok=False,
                 lock=False, wrap=True, initial=None, xforms=None):
        super(CaseDbCacheSQL, self).__init__(domain, strip_history, deleted_ok, lock, wrap, initial, xforms)
        if not self.wrap:
            raise ValueError('CaseDbCacheSQL does not support unwrapped models')

    def _validate_case(self, case):
        if self.domain and case.domain != self.domain:
            raise IllegalCaseId("Bad case id")
        elif case.is_deleted:
            if not self.deleted_ok:
                raise IllegalCaseId("Case [%s] is deleted " % case.case_id)

    def _iter_cases(self, case_ids):
        return iter(CaseAccessorSQL.get_cases(case_ids))

    def get_cases_for_saving(self, now):
        cases = self.get_changed()

        saved_case_ids = [case.case_id for case in cases if case.is_saved()]
        cases_modified_on = CaseAccessorSQL.get_last_modified_dates(self.domain, saved_case_ids)
        for case in cases:
            if case.is_saved():
                modified_on = cases_modified_on.get(case.case_id, None)
                assert case.server_modified_on == modified_on, (
                    "Aborting because the case has been modified by another process: "
                    "case={}, {} != {}".format(case.case_id, case.server_modified_on, modified_on)
                )
            case.server_modified_on = now
        return cases

    def get_reverse_indexed_cases(self, case_ids, case_types=None, is_closed=None):
        return CaseAccessorSQL.get_reverse_indexed_cases(self.domain, case_ids,
                                                         case_types=case_types, is_closed=is_closed)

    def filter_closed_extensions(self, extensions_to_close):
        # noop for SQL since the filtering already happened when we fetched the IDs
        return extensions_to_close

    def post_process_case(self, case, xform):
        if toggles.SORT_OUT_OF_ORDER_FORM_SUBMISSIONS_SQL.enabled(case.domain, toggles.NAMESPACE_DOMAIN):
            self.case_update_strategy(case).reconcile_transactions_if_necessary()
