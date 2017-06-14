

class WarehouseTable(object):

    @classmethod
    def commit(cls, start_datetime, end_datetime):
        raise NotImplementedError

    @classmethod
    def dependencies(cls):
        '''Returns a list of slugs that the warehouse table is dependent on'''
        raise NotImplementedError
