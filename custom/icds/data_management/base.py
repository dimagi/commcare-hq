from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor
from corehq.util.doc_processor.interface import BulkDocProcessor
from corehq.util.doc_processor.sql import SqlDocumentProvider


class DataManagement(object):
    slug = ""
    name = ""
    case_type = None

    def __init__(self, domain):
        self.domain = domain

    def run(self, iteration_key):
        raise NotImplementedError


class SQLBasedDataManagement(DataManagement):
    doc_processor = None

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

    def run(self, iteration_key):
        """
        iterate sql records and update them as and when needed
        """
        record_provider = SqlDocumentProvider(iteration_key, self.case_accessor())
        processor = BulkDocProcessor(record_provider, self.doc_processor(self.domain))
        processor.run()


class ESBasedDataManagement(DataManagement):
    def run(self, iteration_key):
        """
        find records to be updated via ES and then update them
        """
        pass
