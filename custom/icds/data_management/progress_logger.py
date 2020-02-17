import logging

from corehq.util.doc_processor.progress import ProcessorProgressLogger


class DataManagementProgressLogger(ProcessorProgressLogger):
    def __init__(self, iteration_key):
        self.success_logger = logging.getLogger(iteration_key + 'success')
        self.success_logger.setLevel(logging.INFO)
        self.success_logger.addHandler(logging.FileHandler(f"success-{iteration_key}.log"))


class SQLBasedProgressLogger(DataManagementProgressLogger):
    def __init__(self, iteration_key):
        super().__init__(iteration_key)
        self.failure_logger = logging.getLogger(iteration_key + 'failure')
        self.failure_logger.setLevel(logging.INFO)
        self.failure_logger.addHandler(logging.FileHandler(f"failure-{iteration_key}.log"))

    def document_skipped(self, doc_dict):
        super().document_skipped(doc_dict)
        self.failure_logger.info(doc_dict['_id'])

    def document_processed(self, doc_dict, case_updates):
        super().document_processed(doc_dict, case_updates)
        self.success_logger.info(doc_dict['_id'])


class ESBasedProgressLogger(DataManagementProgressLogger):
    def document_processed(self, case, case_updates):
        super().document_processed(case, case_updates)
        self.success_logger.info(case.case_id)
