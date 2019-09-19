from django.db import transaction

from corehq.sql_db.routers import db_for_read_write
from corehq.util.test_utils import unit_testing_only
from corehq.warehouse.utils import truncate_records_for_cls


class BaseLoader(object):
    model_cls = None

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
