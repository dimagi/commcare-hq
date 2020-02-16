import logging

from corehq.util.doc_processor.progress import ProcessorProgressLogger


class DataManagementProgressLogger(ProcessorProgressLogger):
    def __init__(self, iteration_key):
        self.success_logger = logging.getLogger(iteration_key + 'success')
        self.success_logger.setLevel(logging.INFO)
        self.success_logger.addHandler(logging.FileHandler(f"success-{iteration_key}.log"))

        self.failure_logger = logging.getLogger(iteration_key + 'failure')
        self.failure_logger.setLevel(logging.INFO)
        self.failure_logger.addHandler(logging.FileHandler(f"failure-{iteration_key}.log"))

    def _doc_id(self, obj):
        raise NotImplementedError

    def documents_failed(self, doc_processor):

    def documents_processed(self, doc_processor):
        for case_id in doc_processor.updates:
            self.failure_logger.info(case_id)


class SQLBasedProgressLogger(DataManagementProgressLogger):
    def _doc_id(self, doc_dict):
        return doc_dict['_id']


class ESBasedProgressLogger(DataManagementProgressLogger):
    def _doc_id(self, case_id):
        return case_id
