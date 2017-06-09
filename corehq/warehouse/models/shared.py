from django.db import transaction


class WarehouseTableMixin(object):

    @classmethod
    @transaction.atomic
    def commit(cls, start_datetime, end_datetime):
        raise NotImplementedError

    @classmethod
    def dependencies(cls):
        '''Returns a list of slugs that the warehouse table is dependent on'''
        raise NotImplementedError
