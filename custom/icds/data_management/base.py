from dimagi.utils.chunked import chunked

from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.doc_processor.interface import BulkDocProcessor
from corehq.util.doc_processor.sql import SqlDocumentProvider
from custom.icds.data_management.progress_logger import (
    ESBasedProgressLogger,
    SQLBasedProgressLogger,
)


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
        raise NotImplementedError


class SQLBasedDataManagement(DataManagement):
    def __init__(self, domain, db_alias, start_date=None, end_date=None):
        super().__init__(domain)
        self.db_aliases = [db_alias] if db_alias else None
        self.start_date = start_date
        self.end_date = end_date

    def case_accessor(self):
        return CaseReindexAccessor(
            domain=self.domain,
            case_type=self.case_type,
            limit_db_aliases=self.db_aliases,
            start_date=self.start_date,
            end_date=self.end_date
        )

    def run(self, iteration_key):
        """
        iterate sql records and update them as and when needed
        """
        record_provider = SqlDocumentProvider(iteration_key, self.case_accessor())
        logger = SQLBasedProgressLogger(iteration_key)
        processor = BulkDocProcessor(record_provider, self.doc_processor(self.domain),
                                     progress_logger=logger)
        processed, skipped = processor.run()
        return processed, skipped, logger.logs


class ESBasedDataManagement(DataManagement):
    def _get_case_ids(self):
        raise NotImplementedError

    def run(self, iteration_key):
        progress_logger = ESBasedProgressLogger(iteration_key)
        case_ids = self._get_case_ids()
        doc_processor = self.doc_processor(self.domain)
        for chunk in chunked(case_ids, 100):
            case_accessor = CaseAccessors(self.domain)
            doc_processor.process_bulk_docs(case_accessor.get_cases(list(chunk)), progress_logger)
        return len(case_ids), 0, progress_logger.logs
