from couchdbkit.ext.django.schema import StringProperty, ListProperty

from casexml.apps.case.models import CommCareCase
from dimagi.ext.couchdbkit import Document
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.undo import UndoableDocument, DeleteDocRecord


class CommCareCaseGroup(UndoableDocument):
    """
        This is a group of CommCareCases. Useful for managing cases in larger projects.
    """
    name = StringProperty()
    domain = StringProperty()
    cases = ListProperty()
    timezone = StringProperty()

    def get_time_zone(self):
        # Necessary for the CommCareCaseGroup to interact with CommConnect, as if using the CommCareMobileContactMixin
        # However, the entire mixin is not necessary.
        return self.timezone

    def get_cases(self, limit=None, skip=None):
        case_ids = self.cases
        if skip is not None:
            case_ids = case_ids[skip:]
        if limit is not None:
            case_ids = case_ids[:limit]
        for case_doc in iter_docs(CommCareCase.get_db(), case_ids):
            # don't let CommCareCase-Deleted get through
            if case_doc['doc_type'] == 'CommCareCase':
                yield CommCareCase.wrap(case_doc)

    def get_total_cases(self, clean_list=False):
        if clean_list:
            self.clean_cases()
        return len(self.cases)

    def clean_cases(self):
        cleaned_list = []
        for case_doc in iter_docs(CommCareCase.get_db(), self.cases):
            # don't let CommCareCase-Deleted get through
            if case_doc['doc_type'] == 'CommCareCase':
                cleaned_list.append(case_doc['_id'])
        if len(self.cases) != len(cleaned_list):
            self.cases = cleaned_list
            self.save()

    def create_delete_record(self, *args, **kwargs):
        return DeleteCaseGroupRecord(*args, **kwargs)


class DeleteCaseGroupRecord(DeleteDocRecord):
    def get_doc(self):
        return CommCareCaseGroup.get(self.doc_id)
