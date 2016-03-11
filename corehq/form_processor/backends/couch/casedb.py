import logging
from couchdbkit import ResourceNotFound
import redis
from casexml.apps.case.dbaccessors.related import get_reverse_indexed_cases
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import iter_cases
from corehq.form_processor.backends.couch.update_strategy import CouchCaseUpdateStrategy
from corehq.form_processor.casedb_base import AbstractCaseDbCache
from corehq.form_processor.exceptions import CouchSaveAborted


class CaseDbCacheCouch(AbstractCaseDbCache):
    case_model_classes = (dict, CommCareCase)
    case_update_strategy = CouchCaseUpdateStrategy

    def _validate_case(self, doc):
        if self.domain and doc['domain'] != self.domain:
            raise IllegalCaseId("Bad case id")
        elif doc['doc_type'] == 'CommCareCase-Deleted':
            if not self.deleted_ok:
                raise IllegalCaseId("Case [%s] is deleted " % doc['_id'])
        elif doc['doc_type'] != 'CommCareCase':
            raise IllegalCaseId(
                'Bad case doc type! '
                'This usually means you are using a bad value for case_id.'
                'The offending ID is {}'.format(doc['_id'])
            )

    def _get_case(self, case_id):
        try:
            if self.strip_history:
                case_doc = CommCareCase.get_lite(case_id, wrap=self.wrap)
            elif self.lock:
                try:
                    case_doc, lock = CommCareCase.get_locked_obj(_id=case_id)
                except redis.RedisError:
                    case_doc = CommCareCase.get(case_id)
                else:
                    self.locks.append(lock)
            else:
                if self.wrap:
                    case_doc = CommCareCase.get(case_id)
                else:
                    case_doc = CommCareCase.get_db().get(case_id)
        except ResourceNotFound:
            return None

        return case_doc

    def _iter_cases(self, case_ids):
        for case in iter_cases(case_ids, self.strip_history, self.wrap):
            yield case

    def get_cases_for_saving(self, now):
        cases = self.get_changed()

        for case in cases:
            # in saving the cases, we have to do all the things
            # done in CommCareCase.save()
            case.initial_processing_complete = True
            case.server_modified_on = now
            try:
                rev = CommCareCase.get_db().get_rev(case.case_id)
            except ResourceNotFound:
                pass
            else:
                if rev != case.get_rev:
                    raise CouchSaveAborted(
                        "Aborting because there would have been "
                        "a document update conflict. {} {} {}".format(
                            case.get_id, case.get_rev, rev
                        )
                    )
        return cases

    def post_process_case(self, case, xform):
        self.case_update_strategy(case).reconcile_actions_if_necessary(xform)

        action_xforms = {action.xform_id for action in case.actions if action.xform_id}
        mismatched_forms = action_xforms ^ set(case.xform_ids)
        if mismatched_forms:
            logging.warning(
                "CASE XFORM MISMATCH /a/{},{}".format(
                    xform.domain,
                    case.case_id
                )
            )

    def get_reverse_indexed_cases(self, case_ids):
        return get_reverse_indexed_cases(self.domain, case_ids)
