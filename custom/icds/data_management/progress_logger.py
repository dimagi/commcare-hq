import logging

from corehq.util.doc_processor.progress import ProcessorProgressLogger


class DataManagementProgressLogger(ProcessorProgressLogger):
    def __init__(self, iteration_key):
        self.success_logger = logging.getLogger(iteration_key + 'success')
        self.success_logger.setLevel(logging.INFO)
        success_log = f"success-{iteration_key}.log"
        self.success_logger.addHandler(logging.FileHandler(success_log))
        self.logs = {success_log: self.success_logger.handlers[0].baseFilename}


class SQLBasedProgressLogger(DataManagementProgressLogger):
    def __init__(self, iteration_key):
        super().__init__(iteration_key)
        self.failure_logger = logging.getLogger(iteration_key + 'failure')
        self.failure_logger.setLevel(logging.INFO)
        failure_log = f"failure-{iteration_key}.log"
        self.failure_logger.addHandler(logging.FileHandler(failure_log))
        self.logs[failure_log] = self.failure_logger.handlers[0].baseFilename

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
