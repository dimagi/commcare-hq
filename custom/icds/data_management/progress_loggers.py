import logging

from corehq.util.doc_processor.progress import ProcessorProgressLogger


class SQLBasedProgressLogger(ProcessorProgressLogger):
    def __init__(self, iteration_key):
        self.success_logger = logging.getLogger(iteration_key + 'success')
        self.success_logger.setLevel(logging.INFO)
        self.success_logger.addHandler(logging.FileHandler(f"success-{iteration_key}.log"))

        self.failure_logger = logging.getLogger(iteration_key + 'failure')
        self.failure_logger.setLevel(logging.INFO)
        self.failure_logger.addHandler(logging.FileHandler(f"failure-{iteration_key}.log"))

    def document_skipped(self, doc_dict):
        super().document_processed(doc_dict)
        self.failure_logger.info(doc_dict['_id'])

    def document_processed(self, doc_dict):
        super().document_processed(doc_dict)
        self.success_logger.info(doc_dict['_id'])
