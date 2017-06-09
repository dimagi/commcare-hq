from django.db import transaction


class WarehouseTableMixin(object):

    @classmethod
    @transaction.atomic
    def commit(cls, start_datetime, end_datetime):
        raise NotImplementedError
