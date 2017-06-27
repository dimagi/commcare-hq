

class WarehouseTable(object):

    @classmethod
    def commit(cls, batch_id):
        '''
        Commits records based on a time frame.

        :param batch_id: The id of the batch being committed

        :returns: True if commit passed validations, False otherwise
        '''
        raise NotImplementedError

    @classmethod
    def dependencies(cls):
        '''Returns a list of slugs that the warehouse table is dependent on'''
        raise NotImplementedError
