import logging

from django.db import transaction

from corehq.sql_db.routers import db_for_read_write
from corehq.util.test_utils import unit_testing_only
from corehq.warehouse.utils import truncate_records_for_cls

logger = logging.getLogger('warehouse')


class ProgressLogger(object):

    def __init__(self, prefix, log_frequency=1000):
        self.prefix = prefix
        self.log_frequency = log_frequency
        self._progress_counter = 0

    def report_progress(self, count=1):
        self._progress_counter += count
        if self._progress_counter % self.log_frequency:
            logger.info('%s progress: %s', self.prefix, self._progress_counter)

    def complete(self):
        logger.info('%s complete: %s', self.prefix, self._progress_counter)


class BaseLoader(object):
    slug = None
    model_cls = None
    log_frequency = 1000

    def __init__(self, verbose=False):
        self.progress_logger = None
        if verbose:
            self.progress_logger = ProgressLogger(
                f'[{self.slug}]', self.log_frequency
            )

    def dependant_slugs(self):
        return []

    def commit(self, batch):
        """
        Commits records based on a time frame.

        :param batch: The Batch of the batch being committed

        :returns: True if commit passed validations, False otherwise
        """
        with transaction.atomic(using=db_for_read_write(self.model_cls)):
            self.load(batch)
        return True

    def load(self, batch):
        raise NotImplementedError

    @unit_testing_only
    def clear_records(self):
        truncate_records_for_cls(self.model_cls, cascade=True)

    def target_table(self):
        return self.model_cls._meta.db_table

    def validate(self):
        return True


class BaseStagingLoader(BaseLoader):

    def commit(self, batch):
        self.clear_records()
        self.load(batch)
        return True

    def clear_records(self):
        truncate_records_for_cls(self.model_cls, cascade=False)
