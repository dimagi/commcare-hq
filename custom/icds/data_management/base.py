from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor
from corehq.util.doc_processor.interface import BulkDocProcessor
from corehq.util.doc_processor.sql import SqlDocumentProvider


class DataManagement(object):
    slug = ""
    name = ""
    case_type = None
    doc_processor = None

    def __init__(self, domain, *args, **kwargs):
        self.domain = domain

    def case_accessor(self):
        raise NotImplementedError

    def run(self, iteration_key):
        """
        iterate sql records and update them as and when needed
        """
        record_provider = SqlDocumentProvider(iteration_key, self.case_accessor())
        processor = BulkDocProcessor(record_provider, self.doc_processor(self.domain))
        processor.run()


class SQLBasedDataManagement(DataManagement):
    def __init__(self, domain, db_alias, from_date=None, till_date=None):
        super().__init__(domain)
        self.db_aliases = [db_alias] if db_alias else None
        self.from_date = from_date
        self.till_date = till_date

    def case_accessor(self):
        return CaseReindexAccessor(
            domain=self.domain,
            case_type=self.case_type,
            limit_db_aliases=self.db_aliases,
            start_date=self.from_date,
            end_date=self.till_date
        )


class ESBasedDataManagement(DataManagement):
    def _get_case_ids(self):
        raise NotImplementedError

    def case_accessor(self):
        return CaseReindexAccessor(
            domain=self.domain,
            case_type=self.case_type,
            case_ids=self._get_case_ids()
        )
