from memoized import memoized

from corehq.apps.data_cleaning.models import BulkEditRecord
from corehq.apps.hqwebapp.tables.elasticsearch.records import CaseSearchElasticRecord


class EditableCaseSearchElasticRecord(CaseSearchElasticRecord):
    def __init__(self, record, request, session=None, **kwargs):
        super().__init__(record, request, **kwargs)
        self.session = session

    @property
    @memoized
    def edited_record(self):
        try:
            return self.session.records.get(doc_id=self.record.case.case_id)
        except BulkEditRecord.DoesNotExist:
            return None

    @property
    def is_selected(self):
        if self.edited_record:
            return self.edited_record.is_selected
        return False

    @property
    @memoized
    def edited_properties(self):
        if self.edited_record:
            return self.edited_record.get_edited_case_properties(self.record.case)
        return {}

    def __getitem__(self, item):
        return super().__getitem__(item)
