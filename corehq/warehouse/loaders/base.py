from django.db import transaction

from corehq.sql_db.routers import db_for_read_write
from corehq.util.test_utils import unit_testing_only
from corehq.warehouse.models.shared import WarehouseTable
from corehq.warehouse.utils import truncate_records_for_cls


class BaseStagingLoader(WarehouseTable):
    @classmethod
    def commit(cls, batch):
        cls.clear_records()
        cls.load(batch)
        return True

    @classmethod
    def clear_records(cls):
        truncate_records_for_cls(cls.model_cls, cascade=False)

    def load(self):
        raise NotImplementedError


class BaseDimLoader(WarehouseTable):
    @classmethod
    def commit(cls, batch):
        with transaction.atomic(using=db_for_read_write(cls.model_cls)):
            cls.load(batch)
        return True

    @classmethod
    @unit_testing_only
    def clear_records(cls):
        truncate_records_for_cls(cls.model_cls, cascade=True)

    def load(self):
        raise NotImplementedError
