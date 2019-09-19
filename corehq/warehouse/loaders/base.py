from django.db import transaction

from corehq.sql_db.routers import db_for_read_write
from corehq.util.test_utils import unit_testing_only
from corehq.warehouse.utils import truncate_records_for_cls


class BaseLoader(object):
    model_cls = None

    @classmethod
    def commit(cls, batch):
        """
        Commits records based on a time frame.

        :param batch: The Batch of the batch being committed

        :returns: True if commit passed validations, False otherwise
        """
        with transaction.atomic(using=db_for_read_write(cls.model_cls)):
            cls.load(batch)
        return True

    @classmethod
    def load(cls, batch):
        raise NotImplementedError

    @classmethod
    def dependencies(cls):
        """Returns a list of slugs that the warehouse table is dependent on"""
        raise NotImplementedError

    @classmethod
    @unit_testing_only
    def clear_records(cls):
        truncate_records_for_cls(cls.model_cls, cascade=True)

    @classmethod
    def target_table(cls):
        return cls.model_cls._meta.db_table

    def validate(self):
        return True


class BaseStagingLoader(BaseLoader):
    @classmethod
    def commit(cls, batch):
        cls.clear_records()
        cls.load(batch)
        return True

    @classmethod
    def clear_records(cls):
        truncate_records_for_cls(cls.model_cls, cascade=False)
