import redis
from casexml.apps.case.exceptions import IllegalCaseId
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.backends.sql.update_strategy import SqlCaseUpdateStrategy
from corehq.form_processor.casedb_base import AbstractCaseDbCache
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCaseSQL


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

    def _get_case(self, case_id):
        try:
            if self.lock:
                try:
                    case, lock = CommCareCaseSQL.get_locked_obj(_id=case_id)
                except redis.RedisError:
                    case = CaseAccessorSQL.get_case(case_id)
                else:
                    self.locks.append(lock)
            else:
                case = CaseAccessorSQL.get_case(case_id)
        except CaseNotFound:
            return None

        return case

    def _iter_cases(self, case_ids):
        return CaseAccessorSQL.get_cases(case_ids)

    def get_cases_for_saving(self, now):
        cases = self.get_changed()

        for case in cases:
            if case.is_saved():
                modified = CaseAccessorSQL.case_modified_since(case.case_id, case.server_modified_on)
                assert not modified, (
                    "Aborting because the case has been modified"
                    " by another process. {}".format(case.case_id)
                )
            case.server_modified_on = now
        return cases

    def get_reverse_indexed_cases(self, case_ids):
        return CaseAccessorSQL.get_reverse_indexed_cases(self.domain, case_ids)
