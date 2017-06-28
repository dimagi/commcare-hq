

class WarehouseTable(object):

    @classmethod
    def commit(cls, batch_record):
        '''
        Commits records based on a time frame.

        :param batch_record: The BatchRecord of the batch being committed

        :returns: True if commit passed validations, False otherwise
        '''
        raise NotImplementedError

    @classmethod
    def dependencies(cls):
        '''Returns a list of slugs that the warehouse table is dependent on'''
        raise NotImplementedError
