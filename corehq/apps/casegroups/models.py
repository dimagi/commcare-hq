from couchdbkit.ext.django.schema import StringProperty, ListProperty

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
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
        for case in CaseAccessors(self.domain).iter_cases(case_ids):
            if not case.is_deleted:
                yield case

    def get_total_cases(self, clean_list=False):
        if clean_list:
            self.clean_cases()
        return len(self.cases)

    def clean_cases(self):
        cleaned_list = []
        changed = False
        for case in CaseAccessors(self.domain).iter_cases(self.cases):
            if not case.is_deleted:
                cleaned_list.append(case.case_id)
            else:
                changed = True
        if changed:
            self.cases = cleaned_list
            self.save()

    def create_delete_record(self, *args, **kwargs):
        return DeleteCaseGroupRecord(*args, **kwargs)


class DeleteCaseGroupRecord(DeleteDocRecord):

    def get_doc(self):
        return CommCareCaseGroup.get(self.doc_id)
